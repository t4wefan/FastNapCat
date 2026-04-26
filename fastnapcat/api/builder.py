"""API request builder for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from uuid import uuid4

from fastnapcat.api.requests import (
    DeleteMessageParams,
    DeleteMessageRequest,
    GetGroupMemberInfoParams,
    GetGroupMemberInfoRequest,
    SendGroupMessageParams,
    SendGroupMessageRequest,
    SendPrivateMessageParams,
    SendPrivateMessageRequest,
    SetGroupBanParams,
    SetGroupBanRequest,
)
from fastnapcat.models.segments import SendMessageSegment


class APIBuilder:
    @staticmethod
    def send_private_message(
        user_id: int,
        message: str | list[SendMessageSegment],
        auto_escape: bool = False,
        echo: str = "",
    ) -> SendPrivateMessageRequest:
        return SendPrivateMessageRequest(
            params=SendPrivateMessageParams(
                user_id=user_id, message=message, auto_escape=auto_escape
            ),
            echo=echo or _new_echo("send_private", user_id),
        )

    @staticmethod
    def send_group_message(
        group_id: int,
        message: str | list[SendMessageSegment],
        auto_escape: bool = False,
        echo: str = "",
    ) -> SendGroupMessageRequest:
        return SendGroupMessageRequest(
            params=SendGroupMessageParams(
                group_id=group_id, message=message, auto_escape=auto_escape
            ),
            echo=echo or _new_echo("send_group", group_id),
        )

    @staticmethod
    def delete_message(message_id: int, echo: str = "") -> DeleteMessageRequest:
        return DeleteMessageRequest(
            params=DeleteMessageParams(message_id=message_id),
            echo=echo or _new_echo("delete_message", message_id),
        )

    @staticmethod
    def get_group_member_info(
        group_id: int, user_id: int, no_cache: bool = False, echo: str = ""
    ) -> GetGroupMemberInfoRequest:
        return GetGroupMemberInfoRequest(
            params=GetGroupMemberInfoParams(
                group_id=group_id, user_id=user_id, no_cache=no_cache
            ),
            echo=echo or _new_echo("get_group_member_info", group_id, user_id),
        )

    @staticmethod
    def set_group_ban(
        group_id: int, user_id: int, duration: int = 30 * 60, echo: str = ""
    ) -> SetGroupBanRequest:
        return SetGroupBanRequest(
            params=SetGroupBanParams(
                group_id=group_id, user_id=user_id, duration=duration
            ),
            echo=echo or _new_echo("set_group_ban", group_id, user_id),
        )


def _new_echo(action: str, *parts: int) -> str:
    suffix = "_".join(str(part) for part in parts)
    prefix = f"{action}_{suffix}" if suffix else action
    return f"{prefix}_{uuid4().hex}"


api_builder = APIBuilder()
