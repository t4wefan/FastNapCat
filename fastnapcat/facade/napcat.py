"""Primary extension entrypoints for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastevents import FastEvents

from fastnapcat.adapter.tags import (
    ROOT_NAPCAT,
    TAG_GROUP,
    TAG_MESSAGE,
    TAG_META,
    TAG_NOTICE,
    TAG_PRIVATE,
    TAG_REQUEST,
)
from fastnapcat.facade.api import APIExtension
from fastnapcat.runtime.bridge import RuntimeBridge


Handler = Callable[..., Awaitable[Any]]


class OnFacade:
    """High-level registration facade layered on top of [`FastEvents.on()`](refrence/FastEvents/fastevents/app.py:27)."""

    def __init__(
        self, app: FastEvents, bridge: RuntimeBridge, api: APIExtension | None = None
    ) -> None:
        self._app = app
        self._bridge = bridge
        self._api = api

    def __call__(self, subscription, level: int = 0, name: str | None = None):
        return self._app.on(subscription, level=level, name=name)

    def message(
        self,
        private: bool = True,
        group: bool = True,
        sub_type: str | None = None,
        level: int = 20,
        name: str | None = None,
    ):
        # self_message support is intentionally not exposed on the new path yet.
        subscription = _message_subscription(
            private=private, group=group, sub_type=sub_type
        )

        def decorator(callback: Handler) -> Handler:
            self._app.on(subscription, level=level, name=name)(callback)
            return callback

        return decorator

    def meta(self, level: int = 20, name: str | None = None):
        def decorator(callback: Handler) -> Handler:
            self._app.on((ROOT_NAPCAT, TAG_META), level=level, name=name)(callback)
            return callback

        return decorator

    def private(self, level: int = 20, name: str | None = None):
        return self.message(private=True, group=False, level=level, name=name)

    def group(
        self, sub_type: str | None = None, level: int = 20, name: str | None = None
    ):
        return self.message(
            private=False, group=True, sub_type=sub_type, level=level, name=name
        )

    def notice(self, level: int = 20, name: str | None = None):
        def decorator(callback: Handler) -> Handler:
            self._app.on((ROOT_NAPCAT, TAG_NOTICE), level=level, name=name)(callback)
            return callback

        return decorator

    def request(self, level: int = 20, name: str | None = None):
        def decorator(callback: Handler) -> Handler:
            self._app.on((ROOT_NAPCAT, TAG_REQUEST), level=level, name=name)(callback)
            return callback

        return decorator


class NapCatExtension:
    """App-bound extension exposing bot-oriented subscription sugar."""

    def __init__(
        self, app: FastEvents, bridge: RuntimeBridge, api: APIExtension | None = None
    ) -> None:
        self.app = app
        self.on = OnFacade(app, bridge, api)


def _message_subscription(
    private: bool, group: bool, sub_type: str | None
) -> tuple[str, ...]:
    if not private and not group:
        raise ValueError("at least one of private/group must be enabled")
    if private and group:
        return (
            (ROOT_NAPCAT, TAG_MESSAGE)
            if sub_type is None
            else (ROOT_NAPCAT, TAG_MESSAGE, sub_type)
        )
    if private:
        base = (ROOT_NAPCAT, TAG_MESSAGE, TAG_PRIVATE)
    else:
        base = (ROOT_NAPCAT, TAG_MESSAGE, TAG_GROUP)
    return base if sub_type is None else (*base, sub_type)
