from __future__ import annotations

import asyncio

import pytest

from fastnapcat import FastNapCat, MetaContext
from fastnapcat.models.events import HeartBeat


def make_heartbeat() -> HeartBeat:
    return HeartBeat(
        time=123,
        self_id=1,
        post_type="meta_event",
        meta_event_type="heartbeat",
        status={"online": True},
        interval=30000,
    )


@pytest.mark.asyncio
async def test_meta_handler_receives_meta_context():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    ready = asyncio.Event()

    @bot.on.meta()
    async def handle(ctx: MetaContext, payload: HeartBeat):
        seen["interval"] = ctx.event.interval
        seen["payload_type"] = type(payload)
        ready.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_heartbeat().model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(ready.wait(), timeout=1)
        assert seen["interval"] == 30000
        assert seen["payload_type"] is HeartBeat
    finally:
        await bot.astop()
