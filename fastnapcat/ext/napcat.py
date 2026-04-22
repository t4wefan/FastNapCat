"""Compatibility wrapper for the new facade napcat module."""

from __future__ import annotations

from warnings import warn

from fastnapcat.facade.napcat import NapCatExtension as _NapCatExtension
from fastnapcat.facade.napcat import OnFacade as _OnFacade


warn(
    "fastnapcat.ext.napcat is a compatibility layer; import from fastnapcat.facade.napcat instead",
    DeprecationWarning,
    stacklevel=2,
)

NapCatExtension = _NapCatExtension
OnFacade = _OnFacade

__all__ = ["NapCatExtension", "OnFacade"]
