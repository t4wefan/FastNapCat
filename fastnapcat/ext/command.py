"""Compatibility wrapper for the new facade command module."""

from __future__ import annotations

from warnings import warn

from fastnapcat.facade.command import CommandExtension as _CommandExtension
from fastnapcat.facade.command import (
    parse_command_from_message as _parse_command_from_message,
)


warn(
    "fastnapcat.ext.command is a compatibility layer; import from fastnapcat.facade.command instead",
    DeprecationWarning,
    stacklevel=2,
)

CommandExtension = _CommandExtension
parse_command_from_message = _parse_command_from_message

__all__ = ["CommandExtension", "parse_command_from_message"]
