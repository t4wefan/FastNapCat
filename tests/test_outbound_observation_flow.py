from __future__ import annotations

import asyncio
import json

import pytest

from fastnapcat import FastNapCat, MessageContext
from fastnapcat.models.events import GroupMessage
from fastnapcat.models.outbound import OutboundMessageObservation
from fastnapcat.models.segments import ReceiveText, ReceiveTextData


def make_group_message(raw_message: str = "ping") -> GroupMessage:
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
async def test_outbound_message_observation_is_published():
    bot = FastNapCat()
    observed: list[OutboundMessageObservation] = []
    ready = asyncio.Event()

    async def fake_sender(text: str) -> None:
        payload = json.loads(text)
        response = {
            "status": "ok",
            "retcode": 0,
            "data": {"message_id": 100},
            "message": "",
            "wording": "",
            "echo": payload["echo"],
        }
        await bot.bridge.handle_inbound_text(json.dumps(response))

    bot.transport.bind_sender(fake_sender)

    @bot.on(("napcat", "outbound", "outbound_message", "observation"))
    async def observe(payload: OutboundMessageObservation):
        observed.append(payload)
        ready.set()

    @bot.on.group()
    async def handle(ctx: MessageContext):
        await ctx.reply("pong")

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message().model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(ready.wait(), timeout=1)
        assert observed
        assert observed[0].intent.source == "message_context"
        assert observed[0].response is not None
    finally:
        await bot.astop()
