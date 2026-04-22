from __future__ import annotations

import pytest

from fastnapcat.adapter.tags import command_tag
from fastnapcat.command.models import CommandArgs
from fastnapcat.command.parser import parse_command_text
from fastnapcat.context.message import MessageContext
from _deprecated.di.signature import analyze_handler_signature
from fastnapcat.models.events import GroupMessage, GroupSender
from fastnapcat.models.segments import (
    ReceiveImage,
    ReceiveImageData,
    ReceiveText,
    ReceiveTextData,
)
from fastnapcat.runtime.protocol import parse_inbound_payload


def make_group_message() -> GroupMessage:
    return GroupMessage(
        self_id=1,
        user_id=2,
        time=123,
        message_id=10,
        message_seq=11,
        real_id=12,
        sender=GroupSender(user_id=2, nickname="tester"),
        raw_message="/ban --duration 60 target",
        font=0,
        group_id=3,
        message=[
            ReceiveText(
                type="text", data=ReceiveTextData(text="/ban --duration 60 target")
            ),
            ReceiveImage(
                type="image", data=ReceiveImageData(url="https://example.com/a.png")
            ),
        ],
    )


def test_parse_command_text():
    parsed = parse_command_text('/ban --duration 60 "hello world"')
    assert parsed is not None
    assert parsed.name == "/ban"
    assert parsed.flags["duration"] == "60"
    assert parsed.position_args == ["hello world"]


def test_protocol_adds_command_tag():
    payload = make_group_message().model_dump(by_alias=True)
    envelope = parse_inbound_payload(payload)
    assert command_tag("/ban") in envelope.tags
    assert envelope.command_name == "/ban"


def test_signature_analysis_detects_command_model():
    class EchoArgs(CommandArgs):
        pass

    async def handler(args: EchoArgs, message: MessageContext):
        return None

    result = analyze_handler_signature(handler)
    assert result.command_model is EchoArgs
    assert "message" in result.known_types
