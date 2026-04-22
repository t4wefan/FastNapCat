"""API extension for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from fastnapcat.api.builder import api_builder
from fastnapcat.api.requests import APIRequest, APIRequestUnion
from fastnapcat.api.responses import APIResponse
from fastnapcat.models.outbound import OutboundApiIntent, OutboundMessageIntent
from fastnapcat.runtime.bridge import RuntimeBridge


class APIExtension:
    """High-level API caller built on top of outbound intents and runtime transport."""

    def __init__(self, bridge: RuntimeBridge) -> None:
        self.bridge = bridge

    async def call(
        self, request: APIRequest | APIRequestUnion, timeout: float | None = None
    ) -> APIResponse:
        return await self.bridge.call_api(request, timeout=timeout)

    async def send_private_message(
        self,
        user_id: int,
        message,
        auto_escape: bool = False,
        echo: str = "",
        timeout: float | None = None,
    ) -> APIResponse:
        intent = OutboundMessageIntent(
            target_type="private",
            user_id=user_id,
            message=message,
            auto_escape=auto_escape,
            echo=echo,
            await_response=True,
            source="api_extension",
        )
        return await self.bridge.send_message(intent)

    async def send_group_message(
        self,
        group_id: int,
        message,
        auto_escape: bool = False,
        echo: str = "",
        timeout: float | None = None,
    ) -> APIResponse:
        intent = OutboundMessageIntent(
            target_type="group",
            group_id=group_id,
            message=message,
            auto_escape=auto_escape,
            echo=echo,
            await_response=True,
            source="api_extension",
        )
        return await self.bridge.send_message(intent)

    async def delete_message(
        self, message_id: int, echo: str = "", timeout: float | None = None
    ) -> APIResponse:
        request = api_builder.delete_message(message_id=message_id, echo=echo)
        return await self.call(request, timeout=timeout)

    async def get_group_member_info(
        self,
        group_id: int,
        user_id: int,
        no_cache: bool = False,
        echo: str = "",
        timeout: float | None = None,
    ) -> APIResponse:
        request = api_builder.get_group_member_info(
            group_id=group_id, user_id=user_id, no_cache=no_cache, echo=echo
        )
        return await self.call(request, timeout=timeout)

    async def set_group_ban(
        self,
        group_id: int,
        user_id: int,
        duration: int = 30 * 60,
        echo: str = "",
        timeout: float | None = None,
    ) -> APIResponse:
        request = api_builder.set_group_ban(
            group_id=group_id, user_id=user_id, duration=duration, echo=echo
        )
        return await self.call(request, timeout=timeout)
