from __future__ import annotations

import asyncio

import pytest

from fastnapcat import FastNapCat, logger
from fastnapcat.models.events import GroupMessage
from fastnapcat.models.outbound import OutboundLogIntent
from fastnapcat.models.segments import ReceiveText, ReceiveTextData


def make_group_message(raw_message: str = "hello") -> GroupMessage:
    return GroupMessage(
        self_id=1,
        user_id=2,
        time=123,
        message_id=10,
        message_seq=11,
        real_id=12,
        sender={"user_id": 2, "nickname": "tester"},
        raw_message=raw_message,
        font=0,
        group_id=3,
        message=[ReceiveText(type="text", data=ReceiveTextData(text=raw_message))],
    )


@pytest.mark.asyncio
async def test_logger_dependency_publishes_outbound_log_event():
    bot = FastNapCat()
    observed: list[OutboundLogIntent] = []
    ready = asyncio.Event()

    @bot.on(("napcat", "outbound", "outbound_log"))
    async def observe(payload: OutboundLogIntent):
        observed.append(payload)
        ready.set()

    @bot.on.group()
    async def handle(log=logger()):
        await log.info("hello log")

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message().model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(ready.wait(), timeout=1)
        assert observed
        assert observed[0].message == "hello log"
        assert observed[0].source == "logger_dependency"
    finally:
        await bot.astop()
