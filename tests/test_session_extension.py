from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fastnapcat import FastNapCat, MessageContext
from fastnapcat.api.responses import APIResponse
from fastnapcat.models.events import GroupMessage
from fastnapcat.models.outbound import OutboundMessageIntent
from fastnapcat.models.segments import ReceiveText, ReceiveTextData


def make_group_message(
    raw_message: str = "hello", *, user_id: int = 2, group_id: int = 3, message_id: int = 10
) -> GroupMessage:
    return GroupMessage(
        self_id=1,
        user_id=user_id,
        time=123,
        message_id=message_id,
        message_seq=11,
        real_id=12,
        sender={"user_id": user_id, "nickname": "tester"},
        raw_message=raw_message,
        font=0,
        group_id=group_id,
        message=[ReceiveText(type="text", data=ReceiveTextData(text=raw_message))],
    )


@pytest.mark.asyncio
async def test_message_context_prompt_receives_next_message_in_same_group_conversation():
    bot = FastNapCat()
    received: dict[str, object] = {}
    done = asyncio.Event()

    @bot.on.group()
    async def handle(ctx: MessageContext):
        if ctx.text != "hello":
            return
        next_ctx = await ctx.prompt(timeout=1)
        received["text"] = next_ctx.text
        received["group_id"] = next_ctx.group_id
        received["user_id"] = next_ctx.user_id
        done.set()

    await bot.astart()
    try:
        first_event_task = asyncio.create_task(
            bot.bridge.handle_inbound_text(
                make_group_message().model_dump_json(by_alias=True)
            )
        )
        for _ in range(20):
            if bot.bridge._message_waiters:
                break
            await asyncio.sleep(0)
        assert bot.bridge._message_waiters
        await bot.bridge.handle_inbound_text(
            make_group_message("noise", user_id=999, message_id=11).model_dump_json(
                by_alias=True
            )
        )
        await bot.bridge.handle_inbound_text(
            make_group_message("world", message_id=12).model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(first_event_task, timeout=1)
        await asyncio.wait_for(done.wait(), timeout=1)
        assert received == {"text": "world", "group_id": 3, "user_id": 2}
    finally:
        await bot.astop()


@pytest.mark.asyncio
async def test_prompt_consumes_followup_message_before_regular_subscribers():
    bot = FastNapCat()
    sent_texts: list[str] = []
    replied = asyncio.Event()

    async def record_send(intent: OutboundMessageIntent):
        text_parts: list[str] = []
        for segment in intent.message:
            segment_type = getattr(segment, "type", None)
            segment_data = getattr(segment, "data", None)
            if segment_type != "text":
                continue
            candidate = getattr(segment_data, "text", None)
            if isinstance(candidate, str):
                text_parts.append(candidate)
        text = "".join(text_parts)
        sent_texts.append(text)
        return APIResponse(status="ok", retcode=0, data={"message_id": len(sent_texts)})

    bot.bridge.send_message = record_send  # type: ignore[method-assign]

    @bot.command("ask", prefixes=["/"])
    async def ask(ctx: MessageContext):
        await ctx.send("ask-start")
        next_ctx = await ctx.prompt(timeout=1)
        await next_ctx.reply(f"follow-up:{next_ctx.text}")
        replied.set()

    @bot.on.group(level=20)
    async def fallback(ctx: MessageContext):
        if ctx.text.startswith("/"):
            return
        await ctx.send(f"fallback:{ctx.text}")

    await bot.astart()
    try:
        first_event_task = asyncio.create_task(
            bot.bridge.handle_inbound_text(
                make_group_message("/ask", message_id=20).model_dump_json(by_alias=True)
            )
        )
        for _ in range(20):
            if bot.bridge._message_waiters:
                break
            await asyncio.sleep(0)
        assert bot.bridge._message_waiters
        await bot.bridge.handle_inbound_text(
            make_group_message("world", message_id=21).model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(first_event_task, timeout=1)
        await asyncio.wait_for(replied.wait(), timeout=1)

        assert any(text == "ask-start" for text in sent_texts)
        assert any(text == "follow-up:world" for text in sent_texts)
        assert all(text != "fallback:world" for text in sent_texts)
    finally:
        await bot.astop()
