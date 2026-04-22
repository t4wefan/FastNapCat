"""Transport layer for NapCat websocket IO."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from loguru import logger
from websockets.asyncio.client import ClientConnection, connect

from fastnapcat.api.requests import APIRequest, APIRequestUnion
from fastnapcat.api.responses import APIResponse


SendTextCallable = Callable[[str], Awaitable[None]]
InboundTextHandler = Callable[[str], Awaitable[object]]


class NapCatTransport:
    """Own websocket connectivity and request/response waiting."""

    def __init__(
        self,
        ws_url: str | None = None,
        access_token: str | None = None,
        reconnect_interval: float = 3.0,
        heartbeat_interval: float = 30.0,
        *,
        debug: bool = False,
    ) -> None:
        self._ws_url = ws_url
        self._access_token = access_token
        self._reconnect_interval = reconnect_interval
        self._heartbeat_interval = heartbeat_interval
        self._debug = debug
        self._send_text: SendTextCallable | None = None
        self._inbound_handler: InboundTextHandler | None = None
        self._pending_responses: dict[str, asyncio.Future[APIResponse]] = {}
        self._started = False
        self._connection: ClientConnection | None = None
        self._runner_task: asyncio.Task[None] | None = None
        self._receiver_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._inbound_tasks: set[asyncio.Task[object]] = set()
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()

    def configure(
        self, ws_url: str | None = None, access_token: str | None = None
    ) -> None:
        if ws_url is not None:
            self._ws_url = ws_url
        if access_token is not None:
            self._access_token = access_token

    def bind_sender(self, sender: SendTextCallable) -> None:
        self._send_text = sender

    def bind_inbound_handler(self, handler: InboundTextHandler) -> None:
        self._inbound_handler = handler

    def set_debug(self, debug: bool) -> None:
        self._debug = debug

    async def astart(self) -> None:
        self._started = True
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._debug_log("transport start ws_url={}", self._ws_url)
        if self._ws_url is None:
            self._connected_event.set()
            return
        if self._ws_url is not None:
            self._runner_task = asyncio.create_task(self._connection_loop())

    async def astop(self) -> None:
        self._started = False
        self._stop_event.set()
        self._connected_event.clear()
        self._debug_log("transport stop")
        for task in [self._heartbeat_task, self._receiver_task, self._runner_task]:
            if task is not None:
                task.cancel()
        for task in list(self._inbound_tasks):
            task.cancel()
        self._heartbeat_task = None
        self._receiver_task = None
        self._runner_task = None
        connection = self._connection
        self._connection = None
        self._send_text = None
        if connection is not None:
            await connection.close()
        pending = list(self._pending_responses.values())
        self._pending_responses.clear()
        for future in pending:
            if not future.done():
                future.cancel()
        inbound_tasks = list(self._inbound_tasks)
        self._inbound_tasks.clear()
        for task in inbound_tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def send_request(
        self,
        request: APIRequest | APIRequestUnion,
        *,
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
            payload = request.model_dump_json(by_alias=True)
            self._debug_log(
                "ws outbound action={} echo={} wait_response={} payload={}",
                request.action,
                request.echo,
                wait_response,
                payload,
            )
            await sender(payload)
            if response_future is None:
                return None
            if timeout is None:
                response = await response_future
            else:
                response = await asyncio.wait_for(response_future, timeout=timeout)
            self._debug_log(
                "ws response resolved echo={} status={} retcode={}",
                response.echo,
                response.status,
                response.retcode,
            )
            return response
        finally:
            if response_future is not None:
                self._pending_responses.pop(request.echo, None)

    def resolve_response(self, response: APIResponse) -> None:
        self._debug_log(
            "resolve response echo={} status={} retcode={}",
            response.echo,
            response.status,
            response.retcode,
        )
        if response.echo is None:
            return
        future = self._pending_responses.get(response.echo)
        if future is None or future.done():
            return
        future.set_result(response)

    async def wait_until_connected(self, timeout: float | None = None) -> None:
        if self._ws_url is None:
            return
        if timeout is None:
            await self._connected_event.wait()
            return
        await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)

    @property
    def is_connected(self) -> bool:
        return self._connected_event.is_set()

    async def _connection_loop(self) -> None:
        while self._started and not self._stop_event.is_set():
            try:
                ws_url = self._ws_url
                if ws_url is None:
                    return
                headers = None
                if self._access_token:
                    headers = {"Authorization": f"Bearer {self._access_token}"}
                self._debug_log("connecting websocket url={}", ws_url)
                async with connect(
                    ws_url, additional_headers=headers
                ) as websocket:
                    logger.info("napcat websocket connected: {}", ws_url)
                    self._debug_log("websocket connected url={}", ws_url)
                    self._connection = websocket
                    self._connected_event.set()
                    self.bind_sender(websocket.send)
                    self._receiver_task = asyncio.create_task(
                        self._receive_loop(websocket)
                    )
                    self._heartbeat_task = asyncio.create_task(
                        self._heartbeat_loop(websocket)
                    )
                    await self._receiver_task
            except asyncio.CancelledError:
                self._debug_log("connection loop cancelled")
                raise
            except Exception as exc:
                logger.warning(
                    "napcat websocket disconnected: {}",
                    repr(exc),
                )
                logger.info(
                    "reconnecting napcat websocket in {}s",
                    self._reconnect_interval,
                )
                self._debug_log(
                    "connection loop error={} reconnect_in={}",
                    repr(exc),
                    self._reconnect_interval,
                )
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(self._reconnect_interval)
            finally:
                if self._connection is not None:
                    logger.info("napcat websocket connection closed")
                self._debug_log("websocket connection cleanup")
                self._connected_event.clear()
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
            elif isinstance(message, (bytearray, memoryview)):
                message = bytes(message).decode()
            self._debug_log("ws inbound payload={}", message)
            handler = self._inbound_handler
            if handler is not None:
                task = asyncio.ensure_future(handler(message))
                self._inbound_tasks.add(task)
                task.add_done_callback(self._inbound_tasks.discard)

    async def _heartbeat_loop(self, websocket: ClientConnection) -> None:
        while self._started and not self._stop_event.is_set():
            await asyncio.sleep(self._heartbeat_interval)
            self._debug_log("sending websocket ping")
            pong_waiter = await websocket.ping()
            await pong_waiter
            self._debug_log("received websocket pong")

    def _require_sender(self) -> SendTextCallable:
        if self._send_text is None:
            raise RuntimeError("transport sender is not bound")
        return self._send_text

    def _debug_log(self, message: str, *args: object) -> None:
        if not self._debug:
            return
        logger.debug(message, *args)
