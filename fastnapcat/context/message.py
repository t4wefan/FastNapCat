"""Message context objects for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from typing import Self

from PIL import Image
from fastevents import RuntimeEvent, dependency
from pydantic import Field

from fastnapcat.api.responses import APIResponse, SendMessageResponse
from fastnapcat.message.builder import message_builder
from fastnapcat.models.base import BaseModel
from fastnapcat.adapter.coerce import coerce_message_event
from fastnapcat.models.events import GroupMessage, PrivateFriendMessage, PrivateGroupMessage
from fastnapcat.models.outbound import OutboundMessageIntent
from fastnapcat.models.segments import (
    ReceiveImage,
    ReceiveImageAsset,
    ReceiveImages,
    SendMessageSegment,
)
from fastnapcat.runtime.bridge import RuntimeBridge
from fastnapcat.runtime.registry import bridge_from_event


class SentMessage(BaseModel):
    message_id: int = Field(..., alias="message_id")
    raw_response: APIResponse | None = None


MessageEvent = PrivateFriendMessage | PrivateGroupMessage | GroupMessage
MessageContent = (
    str
    | Image.Image
    | ReceiveImage
    | ReceiveImageAsset
    | ReceiveImages
    | list[SendMessageSegment | Image.Image | str | ReceiveImage]
)


class MessageContext:
    """High-frequency message operations bound to one inbound message event."""

    @classmethod
    def _provider(cls):
        @dependency
        def _message_context(event: RuntimeEvent) -> Self:
            return cls(coerce_message_event(event.payload), bridge_from_event(event))

        return _message_context

    def __init__(self, event: MessageEvent, bridge: RuntimeBridge) -> None:
        self.event = event
        self.bridge: RuntimeBridge = bridge

    @property
    def user_id(self) -> int:
        return self.event.user_id

    @property
    def group_id(self) -> int | None:
        return getattr(self.event, "group_id", None)

    @property
    def message_id(self) -> int:
        return self.event.message_id

    @property
    def text(self) -> str:
        return self.event.raw_message

    @property
    def segments(self):
        return self.event.message

    @property
    def is_private(self) -> bool:
        return self.event.message_type == "private"

    @property
    def is_group(self) -> bool:
        return self.event.message_type == "group"

    async def send(
        self, content: MessageContent, auto_escape: bool = False
    ) -> SentMessage:
        normalized = _normalize_content(content)
        if self.is_group and self.group_id is not None:
            response = await self.bridge.send_message(
                OutboundMessageIntent(
                    target_type="group",
                    group_id=self.group_id,
                    message=normalized,
                    auto_escape=auto_escape,
                )
            )
        else:
            response = await self.bridge.send_message(
                OutboundMessageIntent(
                    target_type="private",
                    user_id=self.user_id,
                    message=normalized,
                    auto_escape=auto_escape,
                )
            )
        return _sent_message_from_response(response)

    async def reply(
        self, content: MessageContent, auto_escape: bool = False
    ) -> SentMessage:
        segments = _normalize_content(content)
        reply_segment = message_builder.reply(self.message_id)
        return await self.send([reply_segment, *segments], auto_escape=auto_escape)

    async def at_sender(self, content: str) -> SentMessage:
        segments = [message_builder.at(self.user_id), message_builder.text(content)]
        return await self.send(segments)

    async def ban_user(self, duration: int = 30 * 60) -> APIResponse:
        if not self.is_group or self.group_id is None:
            raise ValueError("ban_user() is only available for group messages")
        api = self.bridge.api
        if api is None:
            raise RuntimeError("API dependency is not available")
        return await api.set_group_ban(
            self.group_id, self.user_id, duration=duration
        )

    async def prompt(self, timeout: float | None = None) -> Self:
        payload = await self.bridge.wait_for_message(
            lambda candidate: _is_followup_message(self.event, candidate),
            timeout=timeout,
            consume=True,
        )
        return type(self)(coerce_message_event(payload), self.bridge)


def _normalize_content(content: MessageContent) -> list[SendMessageSegment]:
    if isinstance(content, str):
        return [message_builder.text(content)]
    if isinstance(content, Image.Image):
        return [_image_segment_from_pil(content)]
    if isinstance(content, ReceiveImage):
        return [_image_segment_from_receive(content)]
    if isinstance(content, ReceiveImageAsset):
        return [_image_segment_from_receive(content.image)]
    if isinstance(content, ReceiveImages):
        return [_image_segment_from_receive(item.image) for item in content.images]

    segments: list[SendMessageSegment] = []
    for item in content:
        if isinstance(item, str):
            segments.append(message_builder.text(item))
            continue
        if isinstance(item, Image.Image):
            segments.append(_image_segment_from_pil(item))
            continue
        if isinstance(item, ReceiveImage):
            segments.append(_image_segment_from_receive(item))
            continue
        if isinstance(item, ReceiveImageAsset):
            segments.append(_image_segment_from_receive(item.image))
            continue
        segments.append(item)
    return segments


def _image_segment_from_pil(image: Image.Image) -> SendMessageSegment:
    import base64
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return message_builder.image(f"base64://{encoded}")


def _image_segment_from_receive(segment: ReceiveImage) -> SendMessageSegment:
    data = segment.data
    if data.file:
        return message_builder.image(
            file=data.file,
            summary=data.summary,
            sub_type=str(data.sub_type) if data.sub_type is not None else None,
        )
    if data.url:
        return message_builder.image(
            file=data.url,
            summary=data.summary,
            sub_type=str(data.sub_type) if data.sub_type is not None else None,
        )
    raise ValueError("receive image segment does not contain file or url")


def _sent_message_from_response(response: APIResponse) -> SentMessage:
    if isinstance(response, SendMessageResponse):
        response_data = response.data
        if response_data is None:
            raise RuntimeError("send message response does not contain data")
        return SentMessage(message_id=response_data.message_id, raw_response=response)

    data = response.data or {}
    message_id = data.get("message_id")
    if not isinstance(message_id, int):
        raise RuntimeError("API response does not contain a valid message_id")
    return SentMessage(message_id=message_id, raw_response=response)


def _is_followup_message(current: MessageEvent, candidate: object) -> bool:
    try:
        message = coerce_message_event(candidate)
    except TypeError:
        return False
    if message.message_id == current.message_id:
        return False
    if current.message_type != message.message_type:
        return False
    if current.message_type == "private":
        return message.user_id == current.user_id
    current_group_id = getattr(current, "group_id", None)
    candidate_group_id = getattr(message, "group_id", None)
    return current_group_id == candidate_group_id and message.user_id == current.user_id
