"""Shared base models for [`fastnapcat.models`](fastnapcat/models/__init__.py)."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict


class BaseModel(PydanticBaseModel):
    """Base immutable model used across the protocol layer."""

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        populate_by_name=True,
    )


SegmentTypeT = TypeVar("SegmentTypeT", bound=str)
SegmentDataT = TypeVar("SegmentDataT")


class BaseSegment(BaseModel, Generic[SegmentTypeT, SegmentDataT]):
    """Generic segment model for both receive and send segments."""

    type: SegmentTypeT
    data: SegmentDataT
