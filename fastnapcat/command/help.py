"""Shared command help rendering for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from typing import Any, get_origin

from pydantic import BaseModel as PydanticBaseModel


def render_command_help(
    *,
    command_name: str,
    model: type[PydanticBaseModel] | None = None,
    matched_prefix: str | None = None,
    prefixes: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    description: str = "",
) -> str:
    rendered_prefix = matched_prefix or select_help_prefix(prefixes)
    display_name = f"{rendered_prefix}{command_name}"
    usage_parts = [display_name]
    argument_lines: list[str] = []
    alias_lines = [f"{rendered_prefix}{alias}" for alias in aliases]

    if model is not None:
        for field_name, field_info in model.model_fields.items():
            if field_name == "parsed_command":
                continue
            placeholder = field_name.upper()
            option_display = format_command_field_option(field_name, field_info)
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

            line = f"  {(option_display or field_name)}  {field_info.description or '无说明'}"
            if not field_info.is_required() and field_info.default is not None:
                line += f" ({field_info.default})"
            argument_lines.append(line)

    body = [" ".join(usage_parts)]
    if description:
        body.append(description)
    if alias_lines:
        body.append(f"= {', '.join(alias_lines)}")
    if argument_lines:
        body.extend(argument_lines)
    return "\n".join(body)


def select_help_prefix(prefixes: tuple[str, ...]) -> str:
    if prefixes:
        return prefixes[0]
    return ""


def format_command_field_option(field_name: str, field_info: Any) -> str | None:
    if not field_accepts_flag(field_name, field_info):
        return None

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

    short_aliases = [
        alias for alias in aliases if alias.startswith("-") and not alias.startswith("--")
    ]
    long_aliases = [alias for alias in aliases if alias.startswith("--") and alias != long_option]
    parts = [long_option, *short_aliases, *long_aliases]
    if parts:
        return " | ".join(parts)
    return None


def field_accepts_flag(field_name: str, field_info: Any) -> bool:
    aliases = [field_name]
    if isinstance(field_info.alias, str) and field_info.alias not in aliases:
        aliases.append(field_info.alias)
    if (
        isinstance(field_info.validation_alias, str)
        and field_info.validation_alias not in aliases
    ):
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
