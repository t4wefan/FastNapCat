"""Outbound event execution for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from loguru import logger as _logger

from fastnapcat.api.builder import api_builder
from fastnapcat.api.responses import APIResponse
from fastnapcat.models.outbound import (
    OutboundApiIntent,
    OutboundLogIntent,
    OutboundMessageIntent,
)


class OutboundExecutor:
    """Execute outbound intents at the framework edge."""

    def __init__(self, send_request) -> None:
        self._send_request = send_request

    async def execute_message(self, intent: OutboundMessageIntent) -> APIResponse:
        if intent.target_type == "group":
            if intent.group_id is None:
                raise ValueError("group outbound intent requires group_id")
            request = api_builder.send_group_message(
                group_id=intent.group_id,
                message=intent.message,
                auto_escape=intent.auto_escape,
                echo=intent.echo,
            )
            response = await self._send_request(
                request, wait_response=intent.await_response
            )
            if response is None:
                raise RuntimeError("outbound group message did not return a response")
            return response

        if intent.user_id is None:
            raise ValueError("private outbound intent requires user_id")
        request = api_builder.send_private_message(
            user_id=intent.user_id,
            message=intent.message,
            auto_escape=intent.auto_escape,
            echo=intent.echo,
        )
        response = await self._send_request(
            request, wait_response=intent.await_response
        )
        if response is None:
            raise RuntimeError("outbound private message did not return a response")
        return response

    async def execute_log(self, intent: OutboundLogIntent) -> None:
        log_method = getattr(_logger, intent.level.lower(), None)
        if callable(log_method):
            log_method(intent.message)
            return
        _logger.log(intent.level.upper(), intent.message)

    async def execute_api(self, intent: OutboundApiIntent) -> APIResponse:
        response = await self._send_request(
            intent.request, wait_response=True, timeout=intent.timeout
        )
        if response is None:
            raise RuntimeError("outbound api intent did not return a response")
        return response
