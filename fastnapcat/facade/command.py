"""Command extension for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, get_type_hints

from fastevents import FastEvents, RuntimeEvent
from fastevents.exceptions import SessionNotConsumed
from pydantic import ValidationError

from fastnapcat.adapter.coerce import coerce_message_event
from fastnapcat.adapter.tags import (
    ROOT_NAPCAT,
    TAG_COMMAND,
    TAG_GROUP,
    TAG_MESSAGE,
    TAG_PRIVATE,
)
from fastnapcat.command.parser import (
    MAX_COMMAND_NAME_LENGTH,
    ParsedCommand,
    parse_command_text,
)
from fastnapcat.command.models import CommandArgs
from fastnapcat.context.message import MessageContext
from fastnapcat.facade.api import APIExtension
from fastnapcat.runtime.bridge import RuntimeBridge
from fastnapcat.runtime.registry import bridge_from_event


Handler = Callable[..., Awaitable[Any]]


class CommandExtension:
    """Thin command registration layer built on top of [`FastEvents.on()`](refrence/FastEvents/fastevents/app.py:27)."""

    def __init__(
        self, app: FastEvents, bridge: RuntimeBridge, api: APIExtension | None = None
    ) -> None:
        self.app = app
        self.bridge = bridge
        self.api = api
        self._command_specs: dict[str, CommandSpec] = {}

    def command(
        self,
        name: str,
        level: int = 10,
        aliases: list[str] | None = None,
        description: str = "",
        prefixes: list[str] | None = None,
        private: bool = True,
        group: bool = True,
    ):
        if not private and not group:
            raise ValueError("at least one of private/group must be enabled")
        normalized = _normalize_command_name(name)
        normalized_aliases = tuple(_normalize_command_name(alias) for alias in aliases or [])
        normalized_prefixes = _normalize_prefixes(prefixes)
        _validate_command_tokens(
            name=normalized,
            aliases=normalized_aliases,
            prefixes=normalized_prefixes,
        )
        spec = CommandSpec(
            name=normalized,
            aliases=normalized_aliases,
            description=description,
            prefixes=normalized_prefixes,
            private=private,
            group=group,
        )
        self._command_specs[normalized] = spec

        def decorator(callback: Handler) -> Handler:
            detected_args_model = _find_command_args_model(callback)
            active_spec = (
                spec.with_args_model(detected_args_model)
                if detected_args_model is not None
                else spec
            )
            self._command_specs[normalized] = active_spec

            if private and group:
                message_subscription = (ROOT_NAPCAT, TAG_MESSAGE)
            elif private:
                message_subscription = (ROOT_NAPCAT, TAG_MESSAGE, TAG_PRIVATE)
            else:
                message_subscription = (ROOT_NAPCAT, TAG_MESSAGE, TAG_GROUP)

            matcher = _wrap_command_matcher(
                spec=active_spec,
            )
            self.app.on(message_subscription, level=level)(matcher)
            self.app.on(_command_subscription(active_spec))(callback)
            return callback

        return decorator

    def help_text(self) -> str:
        help_blocks = [
            _render_command_help(spec)
            for spec in self._command_specs.values()
        ]
        return "\n\n".join(block for block in help_blocks if block)


def parse_command_from_message(text: str) -> ParsedCommand | None:
    return parse_command_text(text)


def _normalize_command_name(name: str) -> str:
    if name.startswith("command."):
        name = name.removeprefix("command.")
    if len(name) > MAX_COMMAND_NAME_LENGTH:
        raise ValueError(
            f"command name must be at most {MAX_COMMAND_NAME_LENGTH} characters"
        )
    return name


def _normalize_prefixes(prefixes: list[str] | None) -> tuple[str, ...]:
    if not prefixes:
        return ()

    normalized: list[str] = []
    for prefix in prefixes:
        candidate = prefix.strip()
        if not candidate:
            continue
        if candidate not in normalized:
            normalized.append(candidate)
    return tuple(normalized)


def _find_command_args_model(callback: Handler) -> type[CommandArgs] | None:
    annotations = get_type_hints(callback)
    for annotation in annotations.values():
        if (
            isinstance(annotation, type)
            and issubclass(annotation, CommandArgs)
            and annotation is not CommandArgs
        ):
            return annotation
    return None


class CommandSpec:
    def __init__(
        self,
        *,
        name: str,
        aliases: tuple[str, ...],
        description: str,
        prefixes: tuple[str, ...],
        private: bool,
        group: bool,
        args_model: type[CommandArgs] | None = None,
    ) -> None:
        self.name = name
        self.aliases = aliases
        self.description = description
        self.prefixes = prefixes
        self.private = private
        self.group = group
        self.args_model = args_model

    def with_args_model(self, args_model: type[CommandArgs]) -> "CommandSpec":
        return CommandSpec(
            name=self.name,
            aliases=self.aliases,
            description=self.description,
            prefixes=self.prefixes,
            private=self.private,
            group=self.group,
            args_model=args_model,
        )


def _wrap_command_matcher(*, spec: CommandSpec) -> Handler:
    async def _matcher(event: RuntimeEvent):
        if any(tag.startswith("command.") for tag in event.tags):
            raise SessionNotConsumed()

        command_source = _extract_command_source_from_event(event)
        if command_source is None:
            raise SessionNotConsumed()
        raw_text, message_type, payload = command_source
        if message_type == "private" and not spec.private:
            raise SessionNotConsumed()
        if message_type == "group" and not spec.group:
            raise SessionNotConsumed()

        parsed = parse_command_text(raw_text, prefixes=spec.prefixes)
        if parsed is None:
            raise SessionNotConsumed()
        if parsed.name != spec.name and parsed.name not in spec.aliases:
            raise SessionNotConsumed()

        payload_model = coerce_message_event(payload)
        message_context = MessageContext(payload_model, bridge_from_event(event))

        if spec.args_model is not None:
            try:
                _build_command_args(
                    model=spec.args_model,
                    parsed=parsed,
                    raw_text=raw_text,
                )
            except ValidationError:
                await message_context.reply(
                    _format_command_validation_error(
                        spec=spec,
                        model=spec.args_model,
                        parsed=parsed,
                    )
                )
                return None

        meta = dict(event.meta)
        meta["command_prefixes"] = list(spec.prefixes)
        await event.ctx.publish(
            tags=_command_event_tags(spec),
            payload=payload_model,
            meta=meta,
        )
        return None

    return _matcher


def _extract_command_source_from_event(
    event: RuntimeEvent,
) -> tuple[str, str, object] | None:
    payload = event.payload
    if isinstance(payload, dict):
        raw_message = payload.get("raw_message")
        message_type = payload.get("message_type")
        if isinstance(raw_message, str) and isinstance(message_type, str):
            return raw_message, message_type, payload
    raw_message = getattr(payload, "raw_message", None)
    message_type = getattr(payload, "message_type", None)
    if isinstance(raw_message, str) and isinstance(message_type, str):
        return raw_message, message_type, payload
    return None


def _validate_command_tokens(
    *, name: str, aliases: tuple[str, ...], prefixes: tuple[str, ...]
) -> None:
    tokens = (name, *aliases)
    for token in tokens:
        for prefix in prefixes:
            if prefix and token.startswith(prefix):
                raise ValueError(
                    f"command token '{token}' must not include prefix '{prefix}'"
                )


def _command_subscription(spec: CommandSpec) -> tuple[str, ...]:
    return (ROOT_NAPCAT, TAG_COMMAND, _command_tag(spec.name))


def _command_event_tags(spec: CommandSpec) -> tuple[str, ...]:
    return (ROOT_NAPCAT, TAG_COMMAND, _command_tag(spec.name))


def _command_tag(name: str) -> str:
    normalized = name.lower().strip()
    safe = "".join(
        char if (char.isalnum() or char in {"_", "."}) else "_"
        for char in normalized
    ).strip("_.")
    return f"command.{safe or 'unknown'}"


def _build_command_args(
    *, model: type[CommandArgs], parsed: ParsedCommand, raw_text: str
) -> CommandArgs:
    metadata = {
        "name": parsed.name,
        "input_name": parsed.input_name,
        "matched_prefix": parsed.matched_prefix,
        "raw_text": raw_text,
        "argv": parsed.argv,
        "flags": parsed.flags,
        "position_args": parsed.position_args,
    }
    values: dict[str, object] = {"parsed_command": metadata}
    remaining_position_args = list(parsed.position_args)

    for field_name, field_info in model.model_fields.items():
        if field_name == "parsed_command":
            continue
        if field_name in metadata:
            values[field_name] = metadata[field_name]
            continue
        aliases = [field_name]
        if isinstance(field_info.alias, str) and field_info.alias not in aliases:
            aliases.append(field_info.alias)
        if isinstance(field_info.validation_alias, str):
            aliases.append(field_info.validation_alias)
        alias = getattr(field_info, "serialization_alias", None)
        if isinstance(alias, str) and alias not in aliases:
            aliases.append(alias)

        matched = False
        for candidate in aliases:
            if candidate in parsed.flags:
                values[field_name] = parsed.flags[candidate]
                matched = True
                break
        if matched:
            continue

        if remaining_position_args:
            values[field_name] = remaining_position_args.pop(0)

    return model.model_validate(values)


def _format_command_validation_error(
    *, spec: CommandSpec, model: type[CommandArgs], parsed: ParsedCommand
) -> str:
    return _render_command_help(
        spec,
        matched_prefix=parsed.matched_prefix,
        model=model,
    )


def _render_command_help(
    spec: CommandSpec,
    *,
    matched_prefix: str | None = None,
    model: type[CommandArgs] | None = None,
) -> str:
    command_name = f"{matched_prefix or _select_help_prefix(spec)}{spec.name}"
    alias_prefix = matched_prefix or _select_help_prefix(spec)
    usage_parts = [command_name]
    argument_lines: list[str] = []
    alias_lines = [f"{alias_prefix}{alias}" for alias in spec.aliases]
    active_model = model or spec.args_model

    if active_model is not None:
        for field_name, field_info in active_model.model_fields.items():
            if field_name == "parsed_command":
                continue
            placeholder = field_name.upper()
            option_display = _format_command_field_option(field_name, field_info)
            if option_display is None:
                if field_info.is_required():
                    usage_parts.append(f"<{placeholder}>")
                else:
                    usage_parts.append(f"[{placeholder}]")
            else:
                if field_info.is_required():
                    usage_parts.append(f"{option_display} <{placeholder}>")
                else:
                    usage_parts.append(f"[{option_display} <{placeholder}>]")

            description = field_info.description or "无说明"
            label = option_display or field_name
            line = f"  {label}  {description}"
            if not field_info.is_required() and field_info.default is not None:
                line += f" ({field_info.default})"
            argument_lines.append(line)

    body = [" ".join(usage_parts)]

    if spec.description:
        body.append(spec.description)

    if alias_lines:
        body.append(f"= {', '.join(alias_lines)}")

    if argument_lines:
        body.extend(argument_lines)

    return "\n".join(body)


def _select_help_prefix(spec: CommandSpec) -> str:
    if spec.prefixes:
        return spec.prefixes[0]
    return ""


def _format_command_field_option(field_name: str, field_info: Any) -> str | None:
    long_option = f"--{field_name.replace('_', '-')}"
    aliases: list[str] = []

    candidate_aliases = [
        field_info.alias,
        field_info.validation_alias,
        getattr(field_info, "serialization_alias", None),
    ]
    for candidate in candidate_aliases:
        if not isinstance(candidate, str):
            continue
        normalized = candidate.strip()
        if not normalized:
            continue
        if len(normalized) == 1:
            normalized = f"-{normalized}"
        elif not normalized.startswith("-"):
            normalized = f"--{normalized.replace('_', '-')}"
        if normalized not in aliases:
            aliases.append(normalized)

    short_aliases = [alias for alias in aliases if alias.startswith("-") and not alias.startswith("--")]
    long_aliases = [alias for alias in aliases if alias.startswith("--") and alias != long_option]

    parts = [long_option, *short_aliases, *long_aliases]
    if parts:
        return " | ".join(parts)
    return None
