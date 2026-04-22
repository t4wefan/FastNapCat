from __future__ import annotations

import asyncio

import pytest

from fastnapcat import CommandContext, FastNapCat, MessageContext
from fastnapcat.command.models import CommandArgs
from pydantic import Field
from fastnapcat.models.events import GroupMessage
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


class EchoArgs(CommandArgs):
    name: str
    raw_text: str
    argv: list[str]
    flags: dict[str, str | bool]
    position_args: list[str]


class EchoFlagArgs(CommandArgs):
    flag1: str


class EchoHelpArgs(CommandArgs):
    content: str = Field(description="message body")
    times: int = Field(default=1, description="repeat times")


@pytest.mark.asyncio
async def test_command_handler_receives_command_context_and_args():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    received = asyncio.Event()

    @bot.command("echo", prefixes=["/"])
    async def handle(
        ctx: MessageContext, cmd: CommandContext, args: EchoArgs, payload: GroupMessage
    ):
        seen["name"] = cmd.name
        seen["position_args"] = cmd.position_args
        seen["argv"] = args.argv
        seen["payload_type"] = type(payload)
        seen["group_id"] = ctx.group_id
        received.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message().model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(received.wait(), timeout=1)
        assert seen["name"] == "echo"
        assert seen["position_args"] == ["hello"]
        assert seen["argv"] == ["hello"]
        assert seen["payload_type"] is GroupMessage
        assert seen["group_id"] == 3
    finally:
        await bot.astop()


@pytest.mark.asyncio
async def test_command_args_injects_flag_fields_from_parsed_command():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    received = asyncio.Event()

    @bot.command("echo", prefixes=["/"])
    async def handle(args: EchoFlagArgs):
        seen["flag1"] = args.flag1
        seen["parsed_name"] = args.parsed_command.name
        seen["parsed_flags"] = args.parsed_command.flags
        received.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message("/echo --flag1 hello").model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(received.wait(), timeout=1)
        assert seen["flag1"] == "hello"
        assert seen["parsed_name"] == "echo"
        assert seen["parsed_flags"] == {"flag1": "hello"}
    finally:
        await bot.astop()


@pytest.mark.asyncio
async def test_command_alias_and_prefix_match_canonical_command():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    received = asyncio.Event()

    @bot.command("echo", aliases=["say"], prefixes=["!"], description="echo text")
    async def handle(args: EchoFlagArgs):
        seen["name"] = args.parsed_command.name
        seen["input_name"] = args.parsed_command.input_name
        seen["matched_prefix"] = args.parsed_command.matched_prefix
        received.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_group_message("!say --flag1 hello").model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(received.wait(), timeout=1)
        assert seen["name"] == "say"
        assert seen["input_name"] == "!say"
        assert seen["matched_prefix"] == "!"
    finally:
        await bot.astop()


def test_command_args_help_text_uses_model_metadata():
    help_text = EchoHelpArgs.help_text()
    assert "CommandArgs: EchoHelpArgs" in help_text
    assert "Usage: EchoHelpArgs <content> [<times>]" in help_text
    assert "content: str (position, required: True) - message body" in help_text
    assert "times: int (position, required: False) - repeat times [default: 1]" in help_text
