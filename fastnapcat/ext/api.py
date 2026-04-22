"""Compatibility wrapper for the new facade API module."""

from __future__ import annotations

from warnings import warn

from fastnapcat.facade.api import APIExtension as _APIExtension


warn(
    "fastnapcat.ext.api is a compatibility layer; import from fastnapcat.facade.api instead",
    DeprecationWarning,
    stacklevel=2,
)

APIExtension = _APIExtension

__all__ = ["APIExtension"]
