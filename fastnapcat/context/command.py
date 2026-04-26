"""Command-scoped context objects for fastnapcat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from fastevents import RuntimeEvent, dependency

from fastnapcat.command.models import get_command_meta
from fastnapcat.command.parser import ParsedCommand


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

    @classmethod
    def _provider(cls):
        @dependency
        def _command_context(event: RuntimeEvent) -> Self:
            meta = get_command_meta(event)
            return cls(
                name=meta.name,
                input_name=meta.input_name,
                matched_prefix=meta.matched_prefix,
                raw_text=meta.raw_text,
                argv=meta.argv,
                flags=meta.flags,
                position_args=meta.position_args,
            )

        return _command_context
