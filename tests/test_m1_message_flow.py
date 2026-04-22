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
