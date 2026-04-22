"""WebSocket runtime skeleton for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from websockets.asyncio.client import ClientConnection, connect

from fastevents import FastEvents

from fastnapcat.adapter.tags import (
    outbound_api_tags,
    outbound_log_tags,
    outbound_message_tags,
)
from fastnapcat.api.requests import APIRequest, APIRequestUnion
from fastnapcat.api.responses import APIResponse
from fastnapcat.ext.api import APIExtension
from fastnapcat.ext.outbound import OutboundExecutor
from fastnapcat.models.outbound import (
    OutboundApiIntent,
    OutboundLogIntent,
    OutboundMessageIntent,
)
from fastnapcat.runtime.protocol import ParsedEnvelope, parse_inbound_payload


SendTextCallable = Callable[[str], Awaitable[None]]


class NapCatWSRuntime:
    """Minimal runtime bridge between websocket IO and [`FastEvents`](refrence/FastEvents/fastevents/app.py:19)."""

    def __init__(
        self,
        ws_url: str | None = None,
        access_token: str | None = None,
        reconnect_interval: float = 3.0,
        heartbeat_interval: float = 30.0,
    ) -> None:
        self._app: FastEvents | None = None
        self._send_text: SendTextCallable | None = None
        self._pending_responses: dict[str, asyncio.Future[APIResponse]] = {}
        self._started = False
        self._ws_url = ws_url
        self._access_token = access_token
        self._reconnect_interval = reconnect_interval
        self._heartbeat_interval = heartbeat_interval
        self._connection: ClientConnection | None = None
        self._runner_task: asyncio.Task[None] | None = None
        self._receiver_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self.api: APIExtension | None = None
        self.outbound: OutboundExecutor | None = None

    def configure(
        self, ws_url: str | None = None, access_token: str | None = None
    ) -> None:
        if ws_url is not None:
            self._ws_url = ws_url
        if access_token is not None:
            self._access_token = access_token

    def bind_app(self, app: FastEvents) -> None:
        self._app = app

    def bind_sender(self, sender: SendTextCallable) -> None:
        self._send_text = sender

    async def astart(self) -> None:
        self._started = True
        self._stop_event = asyncio.Event()
        self.api = APIExtension(self)
        self.outbound = OutboundExecutor(self.send_request)
        if self._ws_url is not None:
            self._runner_task = asyncio.create_task(self._connection_loop())

    async def astop(self) -> None:
        self._started = False
        self._stop_event.set()
        for task in [self._heartbeat_task, self._receiver_task, self._runner_task]:
            if task is not None:
                task.cancel()
        self._heartbeat_task = None
        self._receiver_task = None
        self._runner_task = None
        connection = self._connection
        self._connection = None
        if connection is not None:
            await connection.close()
        pending = list(self._pending_responses.values())
        self._pending_responses.clear()
        for future in pending:
            if not future.done():
                future.cancel()

    async def handle_inbound_text(self, text: str) -> ParsedEnvelope:
        payload = json.loads(text)
        envelope = parse_inbound_payload(payload)
        if isinstance(envelope.model, APIResponse):
            self._resolve_response(envelope.model)
        await self._publish_envelope(envelope)
        return envelope

    async def send_request(
        self,
        request: APIRequest | APIRequestUnion,
        wait_response: bool = True,
        timeout: float | None = None,
    ) -> APIResponse | None:
        sender = self._require_sender()
        response_future: asyncio.Future[APIResponse] | None = None
        if wait_response:
            loop = asyncio.get_running_loop()
            response_future = loop.create_future()
            self._pending_responses[request.echo] = response_future

        try:
            await sender(request.model_dump_json(by_alias=True))
            if response_future is None:
                return None
            if timeout is None:
                return await response_future
            return await asyncio.wait_for(response_future, timeout=timeout)
        finally:
            if response_future is not None:
                self._pending_responses.pop(request.echo, None)

    async def _publish_envelope(self, envelope: ParsedEnvelope) -> None:
        app = self._require_app()
        await app.publish(tags=envelope.tags, payload=envelope.model)

    async def dispatch_outbound_message(
        self, intent: OutboundMessageIntent
    ) -> APIResponse:
        app = self._require_app()
        await app.publish(tags=outbound_message_tags(), payload=intent)
        if self.outbound is None:
            raise RuntimeError("outbound executor is not ready")
        return await self.outbound.execute_message(intent)

    async def dispatch_outbound_log(self, intent: OutboundLogIntent) -> None:
        app = self._require_app()
        await app.publish(tags=outbound_log_tags(), payload=intent)
        if self.outbound is None:
            raise RuntimeError("outbound executor is not ready")
        await self.outbound.execute_log(intent)

    async def dispatch_outbound_api(self, intent: OutboundApiIntent) -> APIResponse:
        app = self._require_app()
        await app.publish(tags=outbound_api_tags(), payload=intent)
        if self.outbound is None:
            raise RuntimeError("outbound executor is not ready")
        return await self.outbound.execute_api(intent)

    async def _connection_loop(self) -> None:
        while self._started and not self._stop_event.is_set():
            try:
                headers = None
                if self._access_token:
                    headers = {"Authorization": f"Bearer {self._access_token}"}
                async with connect(
                    self._ws_url, additional_headers=headers
                ) as websocket:
                    self._connection = websocket
                    self.bind_sender(websocket.send)
                    self._receiver_task = asyncio.create_task(
                        self._receive_loop(websocket)
                    )
                    self._heartbeat_task = asyncio.create_task(
                        self._heartbeat_loop(websocket)
                    )
                    await self._receiver_task
            except asyncio.CancelledError:
                raise
            except Exception:
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(self._reconnect_interval)
            finally:
                self._connection = None
                self._send_text = None
                for task in [self._receiver_task, self._heartbeat_task]:
                    if task is not None:
                        task.cancel()
                self._receiver_task = None
                self._heartbeat_task = None

    async def _receive_loop(self, websocket: ClientConnection) -> None:
        async for message in websocket:
            if isinstance(message, bytes):
                message = message.decode()
            await self.handle_inbound_text(message)

    async def _heartbeat_loop(self, websocket: ClientConnection) -> None:
        while self._started and not self._stop_event.is_set():
            await asyncio.sleep(self._heartbeat_interval)
            pong_waiter = await websocket.ping()
            await pong_waiter

    def _resolve_response(self, response: APIResponse) -> None:
        if response.echo is None:
            return
        future = self._pending_responses.get(response.echo)
        if future is None or future.done():
            return
        future.set_result(response)

    def _require_app(self) -> FastEvents:
        if self._app is None:
            raise RuntimeError("runtime is not bound to a FastEvents app")
        return self._app

    def _require_sender(self) -> SendTextCallable:
        if self._send_text is None:
            raise RuntimeError("runtime sender is not bound")
        return self._send_text
