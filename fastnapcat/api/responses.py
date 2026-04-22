"""OneBot API response models for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from fastnapcat.models.base import BaseModel


class APIResponse(BaseModel):
    status: str
    retcode: int
    data: dict[str, Any] | None = Field(default_factory=dict)
    message: str = ""
    wording: str = ""
    echo: str | None = None


class SendMessageResponseData(BaseModel):
    message_id: int = Field(..., alias="message_id")


class SendMessageResponse(APIResponse):
    data: SendMessageResponseData | None = None
