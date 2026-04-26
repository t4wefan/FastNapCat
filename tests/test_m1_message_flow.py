from __future__ import annotations

import asyncio
import json

import pytest

from fastnapcat import FastNapCat, MessageContext
from fastnapcat.models.events import GroupMessage
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
async def test_message_handler_receives_context_and_payload():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    received = asyncio.Event()

    @bot.on.message(group=True, private=False)
    async def handle(ctx: MessageContext, payload: GroupMessage):
        seen["text"] = ctx.text
        seen["group_id"] = ctx.group_id
        seen["payload_type"] = type(payload)
        received.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message().model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(received.wait(), timeout=1)
        assert seen["text"] == "hello"
        assert seen["group_id"] == 3
        assert seen["payload_type"] is GroupMessage
    finally:
        await bot.astop()


@pytest.mark.asyncio
async def test_message_context_reply_sends_group_message_request():
    bot = FastNapCat()
    sent_messages: list[dict[str, object]] = []
    ready = asyncio.Event()

    async def fake_sender(text: str) -> None:
        payload = json.loads(text)
        sent_messages.append(payload)
        if payload["action"] == "send_group_msg":
            response = {
                "status": "ok",
                "retcode": 0,
                "data": {"message_id": 99},
                "message": "",
                "wording": "",
                "echo": payload["echo"],
            }
            await bot.bridge.handle_inbound_text(json.dumps(response))

    bot.transport.bind_sender(fake_sender)

    @bot.on.group()
    async def handle(ctx: MessageContext):
        await ctx.reply("pong")
        ready.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message("ping").model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(ready.wait(), timeout=1)
        assert sent_messages
        assert sent_messages[0]["action"] == "send_group_msg"
        assert sent_messages[0]["params"]["group_id"] == 3
    finally:
        await bot.astop()


@pytest.mark.asyncio
async def test_message_context_uses_current_bot_bridge_with_multiple_instances():
    bot1 = FastNapCat()
    bot2 = FastNapCat()
    seen: dict[str, object] = {}
    ready1 = asyncio.Event()
    ready2 = asyncio.Event()

    @bot1.on.group()
    async def handle_bot1(ctx: MessageContext):
        seen["bot1_bridge"] = ctx.bridge
        ready1.set()

    @bot2.on.group()
    async def handle_bot2(ctx: MessageContext):
        seen["bot2_bridge"] = ctx.bridge
        ready2.set()

    await bot1.astart()
    await bot2.astart()
    try:
        await bot1.bridge.handle_inbound_text(
            make_group_message("from bot1").model_dump_json(by_alias=True)
        )
        await bot2.bridge.handle_inbound_text(
            make_group_message("from bot2").model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(ready1.wait(), timeout=1)
        await asyncio.wait_for(ready2.wait(), timeout=1)
        assert seen["bot1_bridge"] is bot1.bridge
        assert seen["bot2_bridge"] is bot2.bridge
    finally:
        await bot2.astop()
        await bot1.astop()
