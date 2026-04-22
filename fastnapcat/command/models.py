"""Command argument base models for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from typing import Any, get_origin

from fastevents import RuntimeEvent, dependency
from pydantic import Field

from fastnapcat.command.parser import ParsedCommand, parse_command_text
from fastnapcat.models.base import BaseModel
from fastnapcat.models.events import GroupMessage, PrivateFriendMessage, PrivateGroupMessage


class CommandArgsMeta(BaseModel):
    """Internal parsed command metadata attached to [`CommandArgs`](fastnapcat/command/models.py:10)."""

    name: str = ""
    input_name: str = ""
    matched_prefix: str | None = None
    raw_text: str = ""
    argv: list[str] = Field(default_factory=list)
    flags: dict[str, str | bool] = Field(default_factory=dict)
    position_args: list[str] = Field(default_factory=list)


class CommandArgs(BaseModel):
    """Base command argument model with provider-based injection semantics."""

    parsed_command: CommandArgsMeta = Field(default_factory=CommandArgsMeta)

    @classmethod
    def help_text(cls) -> str:
        lines = [f"CommandArgs: {cls.__name__}"]
        lines.append(f"Usage: {cls.usage_text()}")

        field_lines = cls.describe_fields()
        if field_lines:
            lines.append("Arguments:")
            lines.extend(field_lines)
        else:
            lines.append("Arguments: none")
        return "\n".join(lines)

    @classmethod
    def usage_text(cls) -> str:
        parts = [cls.__name__]
        for field_name, field_info in cls.model_fields.items():
            if field_name == "parsed_command":
                continue
            is_flag = cls._field_accepts_flag(field_name, field_info)
            placeholder = field_name.upper()
            if is_flag:
                segment = f"--{field_name} {placeholder}"
            else:
                segment = f"<{field_name}>"
            if not field_info.is_required():
                segment = f"[{segment}]"
            parts.append(segment)
        return " ".join(parts)

    @classmethod
    def describe_fields(cls) -> list[str]:
        lines: list[str] = []
        for field_name, field_info in cls.model_fields.items():
            if field_name == "parsed_command":
                continue
            annotation = field_info.annotation
            field_type = getattr(annotation, "__name__", str(annotation))
            required = field_info.is_required()
            description = field_info.description or "No description"
            default = field_info.default if field_info.default is not None else None
            mode = "flag" if cls._field_accepts_flag(field_name, field_info) else "position"
            detail = f"  - {field_name}: {field_type} ({mode}, required: {required}) - {description}"
            if default is not None and not required:
                detail += f" [default: {default}]"
            lines.append(detail)
        return lines

    @classmethod
    def _provider(cls):
        """Static DI entry required by [`FastEvents`](refrence/FastEvents/fastevents/subscribers.py:158)."""

        return cls._make_provider_for(cls)

    @classmethod
    def _parse_command_from_event(cls, event: RuntimeEvent) -> ParsedCommand:
        payload = _coerce_command_payload(event.payload)
        raw_message = getattr(payload, "raw_message", None)
        if not isinstance(raw_message, str):
            raise TypeError("command args require a message event payload")
        meta = event.meta if isinstance(event.meta, dict) else {}
        prefixes = meta.get("command_prefixes")
        if not isinstance(prefixes, (list, tuple)):
            prefixes = None
        parsed = parse_command_text(raw_message, prefixes=prefixes)
        if parsed is None:
            raise RuntimeError("command args are not available for the current event")
        return parsed

    @staticmethod
    def _make_provider_for(model: type["CommandArgs"]):
        @dependency
        def _command_args(event: RuntimeEvent) -> CommandArgs:
            payload = _coerce_command_payload(event.payload)
            parsed = model._parse_command_from_event(event)
            metadata = {
                "name": parsed.name,
                "input_name": parsed.input_name,
                "matched_prefix": parsed.matched_prefix,
                "raw_text": payload.raw_message,
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

        return _command_args

    @staticmethod
    def _field_accepts_flag(field_name: str, field_info: Any) -> bool:
        aliases = [field_name]
        if isinstance(field_info.alias, str) and field_info.alias not in aliases:
            aliases.append(field_info.alias)
        if isinstance(field_info.validation_alias, str) and field_info.validation_alias not in aliases:
            aliases.append(field_info.validation_alias)
        serialization_alias = getattr(field_info, "serialization_alias", None)
        if isinstance(serialization_alias, str) and serialization_alias not in aliases:
            aliases.append(serialization_alias)
        if any(candidate.startswith("-") for candidate in aliases):
            return True
        annotation = field_info.annotation
        origin = get_origin(annotation)
        if annotation is bool:
            return True
        return origin is dict


def _coerce_command_payload(
    payload: object,
) -> PrivateFriendMessage | PrivateGroupMessage | GroupMessage:
    if isinstance(payload, (PrivateFriendMessage, PrivateGroupMessage, GroupMessage)):
        return payload
    if not isinstance(payload, dict):
        raise TypeError("command args require a message event payload")
    message_type = payload.get("message_type")
    sub_type = payload.get("sub_type")
    if message_type == "group":
        return GroupMessage.model_validate(payload)
    if sub_type == "friend":
        return PrivateFriendMessage.model_validate(payload)
    return PrivateGroupMessage.model_validate(payload)
