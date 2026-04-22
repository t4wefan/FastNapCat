"""Command-scoped context objects for fastnapcat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from fastevents import RuntimeEvent, dependency

from fastnapcat.command.parser import ParsedCommand
from fastnapcat.command.models import CommandArgs, CommandArgsMeta
from fastnapcat.context.message import MessageContext
from fastnapcat.models.events import GroupMessage, PrivateFriendMessage, PrivateGroupMessage


@dataclass(slots=True)
class CommandContext:
    name: str
    input_name: str
    matched_prefix: str | None
    raw_text: str
    argv: list[str]
    flags: dict[str, str | bool]
    position_args: list[str]

    @classmethod
    def from_parsed(cls, parsed: ParsedCommand, raw_text: str) -> Self:
        return cls(
            name=parsed.name,
            input_name=parsed.input_name,
            matched_prefix=parsed.matched_prefix,
            raw_text=raw_text,
            argv=parsed.argv,
            flags=parsed.flags,
            position_args=parsed.position_args,
        )

    def bind_message(self, message: MessageContext) -> "BoundCommandContext":
        return BoundCommandContext(command=self, message=message)

    @classmethod
    def _provider(cls):
        @dependency
        def _command_context(event: RuntimeEvent) -> Self:
            payload = _coerce_command_payload(event.payload)
            parsed = CommandArgs._parse_command_from_event(event)
            return cls.from_parsed(parsed, payload.raw_message)

        return _command_context


@dataclass(slots=True)
class BoundCommandContext:
    command: CommandContext
    message: MessageContext


def _coerce_command_payload(
    payload: object,
) -> PrivateFriendMessage | PrivateGroupMessage | GroupMessage:
    if isinstance(payload, (PrivateFriendMessage, PrivateGroupMessage, GroupMessage)):
        return payload
    if not isinstance(payload, dict):
        raise TypeError("command_context() requires a message event payload")
    message_type = payload.get("message_type")
    sub_type = payload.get("sub_type")
    if message_type == "group":
        return GroupMessage.model_validate(payload)
    if sub_type == "friend":
        return PrivateFriendMessage.model_validate(payload)
    return PrivateGroupMessage.model_validate(payload)
