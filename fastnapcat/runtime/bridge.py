"""Bridge transport IO into FastEvents and outbound helpers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING

from fastevents import FastEvents
from loguru import logger

from fastnapcat.adapter.inbound import (
    InboundEnvelope,
    debug_parse_inbound_payload,
    parse_inbound_payload,
)
from fastnapcat.adapter.tags import (
    outbound_api_observation_tags,
    outbound_api_tags,
    outbound_message_observation_tags,
    outbound_message_tags,
)
from fastnapcat.api.builder import api_builder
from fastnapcat.api.requests import APIRequest, APIRequestUnion
from fastnapcat.api.responses import APIResponse
from fastnapcat.models.events import HeartBeat, NapCatEvent
from fastnapcat.models.outbound import (
    OutboundApiIntent,
    OutboundApiObservation,
    OutboundMessageIntent,
    OutboundMessageObservation,
)
from fastnapcat.runtime.transport import NapCatTransport
from fastnapcat.runtime.registry import bridge_meta, register_bridge

if TYPE_CHECKING:
    from fastnapcat.facade.api import APIExtension


class RuntimeBridge:
    """Host-owned bridge between NapCat transport and a FastEvents app."""

    def __init__(
        self, app: FastEvents, transport: NapCatTransport, *, debug: bool = False
    ) -> None:
        self._app = app
        self.transport = transport
        self.debug = debug
        self.bridge_id = register_bridge(self)
        self.transport.bind_inbound_handler(self.handle_inbound_text)
        self.api: APIExtension | None = None
        self._ready_future: asyncio.Future[None] | None = None
        self._message_waiters: list[
            tuple[Callable[[object], bool], asyncio.Future[object], bool]
        ] = []

    async def astart(self) -> None:
        self._ready_future = asyncio.get_running_loop().create_future()
        await self.transport.astart()
        if (
            self.transport._ws_url is None
            and self._ready_future is not None
            and not self._ready_future.done()
        ):
            self._ready_future.set_result(None)

    async def astop(self) -> None:
        await self.transport.astop()
        future = self._ready_future
        self._ready_future = None
        if future is not None and not future.done():
            future.cancel()
        waiters = list(self._message_waiters)
        self._message_waiters.clear()
        for _, waiter, _ in waiters:
            if not waiter.done():
                waiter.cancel()

    async def wait_until_ready(self, timeout: float | None = None) -> None:
        future = self._ready_future
        if future is None:
            raise RuntimeError("runtime bridge is not started")
        if timeout is None:
            await future
            return
        await asyncio.wait_for(future, timeout=timeout)

    async def handle_inbound_text(self, text: str) -> InboundEnvelope:
        payload = json.loads(text)
        envelope = (
            debug_parse_inbound_payload(payload)
            if self.debug
            else parse_inbound_payload(payload)
        )
        if isinstance(envelope.model, APIResponse):
            if envelope.model.status == "failed" and envelope.model.echo is None:
                exc = RuntimeError(
                    f"napcat startup failed retcode={envelope.model.retcode}: {envelope.model.wording or envelope.model.message or 'unknown error'}"
                )
                self._mark_startup_error(exc)
                raise exc
            self.transport.resolve_response(envelope.model)
        elif isinstance(envelope.model, NapCatEvent):
            if isinstance(envelope.model, HeartBeat):
                logger.info(
                    "napcat heartbeat received interval={} online={} good={}",
                    envelope.model.interval,
                    envelope.model.status.get("online"),
                    envelope.model.status.get("good"),
                )
            self._mark_ready()
            consumed = self._resolve_message_waiters(envelope.model)
            if consumed:
                return envelope
        await self._publish_with_debug(
            tags=envelope.tags,
            payload=envelope.model,
            stage="inbound_event",
        )
        return envelope

    async def wait_for_message(
        self,
        matcher: Callable[[object], bool],
        *,
        timeout: float | None = None,
        consume: bool = False,
    ) -> object:
        future: asyncio.Future[object] = asyncio.get_running_loop().create_future()
        waiter = (matcher, future, consume)
        self._message_waiters.append(waiter)
        try:
            if timeout is None:
                return await future
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            with suppress(ValueError):
                self._message_waiters.remove(waiter)

    async def call_api(
        self, request: APIRequest | APIRequestUnion, timeout: float | None = None
    ) -> APIResponse:
        intent = OutboundApiIntent(
            request=request, timeout=timeout, source="runtime_bridge"
        )
        await self._publish_with_debug(
            tags=outbound_api_tags(),
            payload=intent,
            stage="outbound_api_intent",
        )
        response = await self.transport.send_request(
            request, wait_response=True, timeout=timeout
        )
        if response is None:
            raise RuntimeError("API call completed without a response")
        await self._publish_with_debug(
            tags=outbound_api_observation_tags(),
            payload=OutboundApiObservation(intent=intent, response=response),
            stage="outbound_api_observation",
        )
        return response

    async def send_message(self, intent: OutboundMessageIntent) -> APIResponse:
        await self._publish_with_debug(
            tags=outbound_message_tags(),
            payload=intent,
            stage="outbound_message_intent",
        )
        if intent.target_type == "group":
            if intent.group_id is None:
                raise ValueError("group outbound intent requires group_id")
            request = api_builder.send_group_message(
                group_id=intent.group_id,
                message=intent.message,
                auto_escape=intent.auto_escape,
                echo=intent.echo,
            )
        else:
            if intent.user_id is None:
                raise ValueError("private outbound intent requires user_id")
            request = api_builder.send_private_message(
                user_id=intent.user_id,
                message=intent.message,
                auto_escape=intent.auto_escape,
                echo=intent.echo,
            )
        response = await self.transport.send_request(
            request,
            wait_response=intent.await_response,
        )
        if response is None:
            raise RuntimeError("message send completed without a response")
        await self._publish_with_debug(
            tags=outbound_message_observation_tags(),
            payload=OutboundMessageObservation(
                intent=intent, request=request, response=response
            ),
            stage="outbound_message_observation",
        )
        return response

    async def _publish_with_debug(
        self,
        *,
        tags: tuple[str, ...],
        payload: object,
        stage: str,
    ) -> None:
        if self.debug:
            logger.debug(
                "bus publish stage={} tags={} payload_type={}",
                stage,
                tags,
                type(payload).__name__,
            )
        await self._app.publish(
            tags=tags,
            payload=payload,
            meta=bridge_meta(self.bridge_id),
        )

    def _mark_ready(self) -> None:
        future = self._ready_future
        if future is None or future.done():
            return
        future.set_result(None)

    def _mark_startup_error(self, exc: Exception) -> None:
        future = self._ready_future
        if future is None or future.done():
            return
        future.set_exception(exc)

    def _resolve_message_waiters(self, payload: object) -> bool:
        consumed = False
        for matcher, future, consume in list(self._message_waiters):
            if future.done():
                continue
            try:
                matched = matcher(payload)
            except Exception:
                continue
            if matched:
                future.set_result(payload)
                consumed = consumed or consume
        return consumed
