"""Outbound intent models for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from fastnapcat.api.requests import APIRequest, APIRequestUnion
from fastnapcat.api.responses import APIResponse
from fastnapcat.models.base import BaseModel
from fastnapcat.models.segments import SendMessageSegment


class OutboundMessageIntent(BaseModel):
    kind: Literal["message"] = "message"
    target_type: Literal["private", "group"]
    user_id: int | None = Field(default=None, alias="user_id")
    group_id: int | None = Field(default=None, alias="group_id")
    message: str | list[SendMessageSegment]
    auto_escape: bool = False
    echo: str = ""
    await_response: bool = True
    source: Literal["message_context", "api_extension"] = "message_context"


class OutboundMessageObservation(BaseModel):
    kind: Literal["message_observation"] = "message_observation"
    intent: OutboundMessageIntent
    request: APIRequestUnion
    response: APIResponse | None = None


class OutboundLogIntent(BaseModel):
    kind: Literal["log"] = "log"
    level: str
    message: str
    source: str = "logger_dependency"


class OutboundApiIntent(BaseModel):
    kind: Literal["api"] = "api"
    request: APIRequest | APIRequestUnion
    timeout: float | None = None
    source: Literal["api_extension", "runtime_bridge"] = "api_extension"


class OutboundApiObservation(BaseModel):
    kind: Literal["api_observation"] = "api_observation"
    intent: OutboundApiIntent
    response: APIResponse | None = None
