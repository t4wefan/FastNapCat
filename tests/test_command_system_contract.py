from __future__ import annotations

import asyncio

import pytest

from fastnapcat import (
    CommandContext,
    FastNapCat,
    MessageContext,
    RuntimeEvent,
    logger,
    message_text,
)
from fastnapcat.api.responses import APIResponse
from fastnapcat.command.models import CommandArgs
from fastnapcat.models.events import GroupMessage
from fastnapcat.models.outbound import OutboundLogIntent, OutboundMessageIntent
from fastnapcat.models.segments import ReceiveText, ReceiveTextData


def make_group_message(raw_message: str = "/echo hello") -> GroupMessage:
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


def extract_text(intent: OutboundMessageIntent) -> str:
    text_parts: list[str] = []
    for segment in intent.message:
        if getattr(segment, "type", None) != "text":
            continue
        segment_data = getattr(segment, "data", None)
        text = getattr(segment_data, "text", None)
        if isinstance(text, str):
            text_parts.append(text)
    return "".join(text_parts)


class RequiredContentArgs(CommandArgs):
    content: str


class FlagArgs(CommandArgs):
    flag1: str


@pytest.mark.asyncio
async def test_unknown_command_does_not_consume_regular_message_handlers():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    ready = asyncio.Event()

    @bot.command("echo", prefixes=["/"])
    async def echo():
        seen["command"] = True

    @bot.on.group(level=20)
    async def fallback(ctx: MessageContext):
        seen["fallback_text"] = ctx.text
        ready.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message("/missing hello").model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(ready.wait(), timeout=1)
        assert "command" not in seen
        assert seen["fallback_text"] == "/missing hello"
    finally:
        await bot.astop()


@pytest.mark.asyncio
async def test_invalid_command_args_reply_help_and_consume_regular_handlers():
    bot = FastNapCat()
    sent_texts: list[str] = []
    fallback_called = asyncio.Event()

    async def record_send(intent: OutboundMessageIntent):
        sent_texts.append(extract_text(intent))
        return APIResponse(
            status="ok",
            retcode=0,
            data={"message_id": len(sent_texts)},
        )

    bot.bridge.send_message = record_send  # type: ignore[method-assign]

    @bot.command("echo", prefixes=["/"])
    async def echo(args: RequiredContentArgs):
        _ = args

    @bot.on.group(level=20)
    async def fallback():
        fallback_called.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message("/echo").model_dump_json(by_alias=True)
        )
        for _ in range(20):
            if sent_texts or fallback_called.is_set():
                break
            await asyncio.sleep(0)
        assert sent_texts
        help_text = "\n".join(sent_texts).lower()
        assert "echo" in help_text
        assert "content" in help_text
        assert not fallback_called.is_set()
    finally:
        await bot.astop()


@pytest.mark.asyncio
async def test_command_handler_keeps_standard_dependency_injection_surface():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    log_ready = asyncio.Event()
    command_ready = asyncio.Event()

    @bot.on(("napcat", "outbound", "outbound_log"))
    async def observe_log(payload: OutboundLogIntent):
        seen["log_message"] = payload.message
        log_ready.set()

    @bot.command("echo", prefixes=["/"])
    async def echo(
        payload: GroupMessage,
        text: str = message_text(),
        log=logger(),
    ):
        seen["payload_type"] = type(payload)
        seen["text"] = text
        await log.info("command log")
        command_ready.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message("/echo hello").model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(command_ready.wait(), timeout=1)
        await asyncio.wait_for(log_ready.wait(), timeout=1)
        assert seen["payload_type"] is GroupMessage
        assert seen["text"] == "/echo hello"
        assert seen["log_message"] == "command log"
    finally:
        await bot.astop()


@pytest.mark.asyncio
async def test_command_dispatch_publishes_derived_event_with_atomic_command_tag():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    command_ready = asyncio.Event()
    derived_ready = asyncio.Event()

    @bot.command("echo", prefixes=["/"])
    async def echo(args: FlagArgs):
        seen["command_arg"] = args.flag1
        command_ready.set()

    @bot.on(("napcat", "command", "command.echo"), level=0)
    async def observe_command_event(
        event: RuntimeEvent,
        cmd: CommandContext,
        args: FlagArgs,
        payload: GroupMessage,
    ):
        seen["derived_tags"] = event.tags
        seen["derived_name"] = cmd.name
        seen["derived_arg"] = args.flag1
        seen["derived_payload_type"] = type(payload)
        derived_ready.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message("/echo --flag1 hello").model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(command_ready.wait(), timeout=1)
        await asyncio.wait_for(derived_ready.wait(), timeout=1)
        assert "command.echo" in seen["derived_tags"]
        assert seen["derived_name"] == "echo"
        assert seen["derived_arg"] == "hello"
        assert seen["derived_payload_type"] is GroupMessage
    finally:
        await bot.astop()


@pytest.mark.asyncio
async def test_derived_command_event_does_not_reach_regular_message_handlers():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    command_ready = asyncio.Event()
    fallback_called = asyncio.Event()

    @bot.command("echo", prefixes=["/"])
    async def echo():
        command_ready.set()

    @bot.on.group(level=20)
    async def fallback(ctx: MessageContext):
        seen["fallback_text"] = ctx.text
        fallback_called.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message("/echo hello").model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(command_ready.wait(), timeout=1)
        for _ in range(20):
            if fallback_called.is_set():
                break
            await asyncio.sleep(0)
        assert "fallback_text" not in seen
        assert not fallback_called.is_set()
    finally:
        await bot.astop()
