"""Dependency providers for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

import inspect
from fastevents import RuntimeEvent, dependency

from fastnapcat.models.outbound import OutboundLogIntent
from fastnapcat.models.segments import ReceiveImage, ReceiveImageAsset, ReceiveImages
from fastnapcat.context.message import _coerce_message_event


@dependency
def message_text(event: RuntimeEvent) -> str:
    try:
        payload = _coerce_message_event(event.payload)
    except TypeError:
        return ""
    return payload.raw_message


@dependency
def images(event: RuntimeEvent) -> ReceiveImages:
    payload = event.payload
    if isinstance(payload, dict):
        raw_segments = payload.get("message", [])
        if not isinstance(raw_segments, list):
            return ReceiveImages(images=[])
        normalized_images: list[ReceiveImageAsset] = []
        for segment in raw_segments:
            if isinstance(segment, ReceiveImage):
                normalized_images.append(ReceiveImageAsset(segment))
                continue
            if isinstance(segment, dict) and segment.get("type") == "image":
                normalized_images.append(
                    ReceiveImageAsset(ReceiveImage.model_validate(segment))
                )
        return ReceiveImages(images=normalized_images)

    try:
        message_event = _coerce_message_event(payload)
    except TypeError:
        return ReceiveImages(images=[])

    return ReceiveImages(
        images=[
            ReceiveImageAsset(segment)
            for segment in message_event.message
            if isinstance(segment, ReceiveImage)
        ]
    )
class LoggerProxy:
    def __init__(self, runtime_event: RuntimeEvent, source: str | None = None) -> None:
        self.runtime_event = runtime_event
        self.source = source or _derive_log_source()

    async def log(self, level: str, message: object) -> None:
        await self.runtime_event.ctx.publish(
            tags=("napcat", "outbound", "outbound_log"),
            payload=OutboundLogIntent(
                level=level,
                message=str(message),
                source=self.source,
            ),
        )

    async def debug(self, message: object) -> None:
        await self.log("debug", message)

    async def info(self, message: object) -> None:
        await self.log("info", message)

    async def warning(self, message: object) -> None:
        await self.log("warning", message)

    async def error(self, message: object) -> None:
        await self.log("error", message)


@dependency
def logger(event: RuntimeEvent) -> LoggerProxy:
    return LoggerProxy(event)


def _derive_log_source() -> str:
    frame = inspect.currentframe()
    try:
        frame = (
            frame.f_back.f_back
            if frame is not None and frame.f_back is not None
            else None
        )
        if frame is None:
            return "logger_dependency"
        module = frame.f_globals.get("__name__", "")
        code = frame.f_code
        return f"{module}:{code.co_name}:{frame.f_lineno}"
    finally:
        del frame
    return "logger_dependency"
