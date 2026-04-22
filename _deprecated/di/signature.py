"""Signature inspection helpers for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

from fastnapcat.app import FastNapCat
from fastnapcat.command.models import CommandArgs
from fastnapcat.context.event import NapCatEventContext, NoticeContext, RequestContext
from fastnapcat.context.message import MessageContext
from fastnapcat.ext.api import APIExtension
from fastnapcat.models.base import BaseModel


KNOWN_INJECTABLE_TYPES = {
    FastNapCat,
    MessageContext,
    APIExtension,
    NapCatEventContext,
    NoticeContext,
    RequestContext,
}


@dataclass(slots=True)
class SignatureAnalysis:
    known_types: dict[str, type[Any]]
    command_model: type[BaseModel] | None


def analyze_handler_signature(callback) -> SignatureAnalysis:
    signature = inspect.signature(callback)
    known_types: dict[str, type[Any]] = {}
    command_model: type[BaseModel] | None = None

    for parameter in signature.parameters.values():
        annotation = parameter.annotation
        if annotation is inspect._empty:
            continue
        if annotation in KNOWN_INJECTABLE_TYPES:
            known_types[parameter.name] = annotation
            continue
        if inspect.isclass(annotation) and issubclass(annotation, CommandArgs):
            if command_model is None:
                command_model = annotation

    return SignatureAnalysis(known_types=known_types, command_model=command_model)
