"""Event-level contexts for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from fastevents import RuntimeEvent, dependency

from fastnapcat.adapter.coerce import (
    coerce_meta_event,
    coerce_napcat_event,
    coerce_notice_event,
    coerce_request_event,
)
from fastnapcat.models.events import MetaEvent, NapCatEvent, NoticeEvent, RequestEvent


@dataclass(slots=True)
class NapCatEventContext:
    event: NapCatEvent
    runtime_event: RuntimeEvent

    @classmethod
    def _provider(cls):
        @dependency
        def _event_context(event: RuntimeEvent) -> Self:
            return cls(event=coerce_napcat_event(event.payload), runtime_event=event)

        return _event_context


@dataclass(slots=True)
class MetaContext:
    event: MetaEvent
    runtime_event: RuntimeEvent

    @classmethod
    def _provider(cls):
        @dependency
        def _meta_context(event: RuntimeEvent) -> Self:
            payload = coerce_meta_event(event.payload)
            return cls(event=payload, runtime_event=event)

        return _meta_context


@dataclass(slots=True)
class NoticeContext:
    event: NoticeEvent
    runtime_event: RuntimeEvent

    @classmethod
    def _provider(cls):
        @dependency
        def _notice_context(event: RuntimeEvent) -> Self:
            payload = coerce_notice_event(event.payload)
            return cls(event=payload, runtime_event=event)

        return _notice_context


@dataclass(slots=True)
class RequestContext:
    event: RequestEvent
    runtime_event: RuntimeEvent

    @classmethod
    def _provider(cls):
        @dependency
        def _request_context(event: RuntimeEvent) -> Self:
            payload = coerce_request_event(event.payload)
            return cls(event=payload, runtime_event=event)

        return _request_context
