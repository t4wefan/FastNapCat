from __future__ import annotations

from fastnapcat.adapter.inbound import parse_inbound_payload
from fastnapcat.adapter.tags import TAG_COMMAND
from fastnapcat.api.builder import api_builder
from fastnapcat.command.models import CommandArgs
from fastnapcat.command.parser import parse_command_text
from fastnapcat.models.events import GroupMessage, GroupSender
from fastnapcat.models.segments import (
    ReceiveImage,
    ReceiveImageData,
    ReceiveText,
    ReceiveTextData,
)


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


def test_protocol_does_not_mark_raw_messages_as_commands():
    payload = make_group_message().model_dump(by_alias=True)
    envelope = parse_inbound_payload(payload)
    assert TAG_COMMAND not in envelope.tags


def test_command_args_help_text_describes_model_fields():
    class EchoArgs(CommandArgs):
        content: str

    help_text = EchoArgs.help_text()
    assert "CommandArgs: EchoArgs" in help_text
    assert "Usage: EchoArgs <content>" in help_text
    assert "content: str (position, required: True)" in help_text


def test_api_builder_generates_unique_default_echo_values():
    first = api_builder.send_group_message(group_id=3, message="hello")
    second = api_builder.send_group_message(group_id=3, message="hello")
    explicit = api_builder.send_group_message(
        group_id=3,
        message="hello",
        echo="custom-echo",
    )

    assert first.echo != second.echo
    assert first.echo.startswith("send_group_3_")
    assert second.echo.startswith("send_group_3_")
    assert explicit.echo == "custom-echo"
