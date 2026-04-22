"""Application facade for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

import asyncio
import sys
from contextlib import suppress
from typing import TYPE_CHECKING

from fastevents import FastEvents, InMemoryBus
from loguru import logger

from fastnapcat.adapter.tags import outbound_log_tags
from fastnapcat.facade.api import APIExtension
from fastnapcat.facade.command import CommandExtension
from fastnapcat.facade.napcat import NapCatExtension
from fastnapcat.context.message import MessageContext
from fastnapcat.models.outbound import OutboundLogIntent
from fastnapcat.runtime.bridge import RuntimeBridge
from fastnapcat.runtime.transport import NapCatTransport

if TYPE_CHECKING:
    from loguru import Record


class FastNapCat:
    """High-level facade that owns the local [`FastEvents`](refrence/FastEvents/fastevents/app.py:19) app and runtime."""

    DEFAULT_CONNECT_TIMEOUT = 10.0

    def __init__(
        self,
        ws_url: str | None = None,
        access_token: str | None = None,
        *,
        debug: bool = False,
    ) -> None:
        logger.remove()
        logger.add(
            sink=sys.stdout,
            format=self._log_format,
            colorize=True,
        )

        self.app: FastEvents = FastEvents(debug=debug)
        self.fastevents: FastEvents = self.app
        self.bus = InMemoryBus()
        self.transport = NapCatTransport(
            ws_url=ws_url,
            access_token=access_token,
            debug=debug,
        )
        self.bridge = RuntimeBridge(self.app, self.transport, debug=debug)
        self.runtime = self.bridge
        self.debug = debug
        MessageContext.bind_bridge(self.bridge)

        self.api = APIExtension(self.bridge)
        self.bridge.api = self.api
        self.on = NapCatExtension(self.app, self.bridge, self.api).on
        self.commands = CommandExtension(self.app, self.bridge, self.api)

        @self.app.on(outbound_log_tags(), level=0, name="fastnapcat_builtin_log_sink")
        async def _log_sink(payload: OutboundLogIntent):
            bound_logger = logger.bind(fastnapcat_source=payload.source)
            log_method = getattr(bound_logger, payload.level.lower(), None)
            if callable(log_method):
                log_method(payload.message)
                return
            bound_logger.log(payload.level.upper(), payload.message)

        self.command = self.commands.command

        logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.__init__").info(
            "fastnapcat initializing ws_url={} debug={}",
            ws_url,
            debug,
        )

    async def astart(self) -> None:
        try:
            # logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astart").info("starting fastnapcat event bus")
            await self.bus.astart(self.app)
            logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astart").info(
                "fastnapcat event bus started"
            )

            if self.transport._ws_url is None:
                pass
                # logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astart").info("starting fastnapcat runtime without websocket transport")
            else:
                # logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astart").info("starting napcat websocket transport: {}", self.transport._ws_url)
                pass
            await self.bridge.astart()

            if self.transport._ws_url is not None:
                logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astart").info(
                    "waiting for napcat websocket connection"
                )
                await self.transport.wait_until_connected(
                    timeout=self.DEFAULT_CONNECT_TIMEOUT
                )
                # logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astart").info("napcat websocket connection established")
                # logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astart").info("waiting for napcat runtime readiness")
                await self.bridge.wait_until_ready(timeout=self.DEFAULT_CONNECT_TIMEOUT)

            logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astart").info(
                "fastnapcat is ready to receive messages"
            )
        except Exception:
            logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astart").exception(
                "fastnapcat startup failed"
            )
            await self.astop()
            raise

    def start(self) -> None:
        asyncio.run(self.astart())

    async def astop(self) -> None:
        logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astop").info(
            "stopping fastnapcat runtime"
        )
        await self.bridge.astop()
        await self.bus.astop()
        logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.astop").info(
            "fastnapcat stopped"
        )

    def run(self) -> None:
        try:
            asyncio.run(self._run_forever())
        except KeyboardInterrupt:
            logger.bind(fastnapcat_source="fastnapcat.app:FastNapCat.run").info(
                "received Ctrl+C, fastnapcat exited gracefully"
            )

    async def _run_forever(self) -> None:
        await self.astart()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.bind(
                fastnapcat_source="fastnapcat.app:FastNapCat._run_forever"
            ).info("run loop cancelled, shutting down fastnapcat")
            raise
        finally:
            with suppress(Exception):
                await self.astop()

    @staticmethod
    def _log_format(record: Record) -> str:
        extra = record.get("extra", {})
        if isinstance(extra, dict):
            source = extra.get("fastnapcat_source")
        else:
            source = None
        if not source:
            name = record.get("name", "unknown")
            function = record.get("function", "unknown")
            source = f"{name}:{function}"
        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            f"<cyan>{source}</cyan> - "
            "<level>{message}</level>\n"
        )
