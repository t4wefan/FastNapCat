"""Command parsing helpers for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

import shlex
from dataclasses import dataclass


MAX_COMMAND_NAME_LENGTH = 50


@dataclass(slots=True)
class ParsedCommand:
    name: str
    input_name: str
    matched_prefix: str | None
    argv: list[str]
    flags: dict[str, str | bool]
    position_args: list[str]


def parse_command_text(
    text: str, *, prefixes: tuple[str, ...] | list[str] | None = None
) -> ParsedCommand | None:
    raw = text.strip()
    if not raw:
        return None

    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = raw.split()

    if not parts:
        return None

    token = parts[0]
    matched_prefix = _match_prefix(token, prefixes)
    name = token.removeprefix(matched_prefix) if matched_prefix else token
    if not name or len(name) > MAX_COMMAND_NAME_LENGTH:
        return None
    argv = parts[1:]
    flags: dict[str, str | bool] = {}
    position_args: list[str] = []

    index = 0
    while index < len(argv):
        current = argv[index]
        if current.startswith("--"):
            key = current[2:]
            if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
                flags[key] = argv[index + 1]
                index += 2
                continue
            flags[key] = True
            index += 1
            continue
        if current.startswith("-") and len(current) > 1 and not current[1].isdigit():
            key = current[1:]
            if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
                flags[key] = argv[index + 1]
                index += 2
                continue
            flags[key] = True
            index += 1
            continue
        position_args.append(current)
        index += 1

    return ParsedCommand(
        name=name,
        input_name=token,
        matched_prefix=matched_prefix,
        argv=argv,
        flags=flags,
        position_args=position_args,
    )


def _match_prefix(
    token: str, prefixes: tuple[str, ...] | list[str] | None
) -> str | None:
    if not prefixes:
        return None
    for prefix in sorted(prefixes, key=len, reverse=True):
        if prefix and token.startswith(prefix):
            return prefix
    return None
