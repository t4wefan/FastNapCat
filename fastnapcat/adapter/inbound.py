"""Inbound payload decoding for fastnapcat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastnapcat.adapter.coerce import coerce_napcat_event
from fastnapcat.adapter.tags import build_tags
from fastnapcat.api.responses import APIResponse
from fastnapcat.models.events import NapCatEvent


@dataclass(slots=True)
class InboundEnvelope:
    model: NapCatEvent | APIResponse
    tags: tuple[str, ...]


def parse_inbound_payload(payload: dict[str, Any]) -> InboundEnvelope:
    if _looks_like_api_response(payload):
        model = APIResponse.model_validate(payload)
        return InboundEnvelope(model=model, tags=build_tags(model))

    model = coerce_napcat_event(payload)
    tags = build_tags(model)
    return InboundEnvelope(model=model, tags=tags)


def debug_parse_inbound_payload(payload: dict[str, Any]) -> InboundEnvelope:
    from loguru import logger

    logger.debug(
        "parse inbound payload post_type={} message_type={} sub_type={} keys={}",
        payload.get("post_type"),
        payload.get("message_type"),
        payload.get("sub_type"),
        sorted(payload.keys()),
    )
    envelope = parse_inbound_payload(payload)
    logger.debug(
        "parsed inbound payload model={} tags={}",
        type(envelope.model).__name__,
        envelope.tags,
    )
    return envelope


def _looks_like_api_response(payload: dict[str, Any]) -> bool:
    return "status" in payload and "retcode" in payload

