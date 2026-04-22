"""OneBot API request models for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import Field

from fastnapcat.models.base import BaseModel
from fastnapcat.models.segments import SendMessageSegment


APIAction: TypeAlias = Literal[
    "send_private_msg",
    "send_group_msg",
    "delete_msg",
    "get_group_member_info",
    "set_group_ban",
]


class SendPrivateMessageParams(BaseModel):
    user_id: int = Field(..., alias="user_id")
    message: str | list[SendMessageSegment]
    auto_escape: bool = False


class SendGroupMessageParams(BaseModel):
    group_id: int = Field(..., alias="group_id")
    message: str | list[SendMessageSegment]
    auto_escape: bool = False


class DeleteMessageParams(BaseModel):
    message_id: int = Field(..., alias="message_id")


class GetGroupMemberInfoParams(BaseModel):
    group_id: int = Field(..., alias="group_id")
    user_id: int = Field(..., alias="user_id")
    no_cache: bool = False


class SetGroupBanParams(BaseModel):
    group_id: int = Field(..., alias="group_id")
    user_id: int = Field(..., alias="user_id")
    duration: int = 30 * 60


APIParams: TypeAlias = (
    SendPrivateMessageParams
    | SendGroupMessageParams
    | DeleteMessageParams
    | GetGroupMemberInfoParams
    | SetGroupBanParams
)


class APIRequest(BaseModel):
    action: APIAction
    params: APIParams
    echo: str


class SendPrivateMessageRequest(BaseModel):
    action: Literal["send_private_msg"] = "send_private_msg"
    params: SendPrivateMessageParams
    echo: str


class SendGroupMessageRequest(BaseModel):
    action: Literal["send_group_msg"] = "send_group_msg"
    params: SendGroupMessageParams
    echo: str


class DeleteMessageRequest(BaseModel):
    action: Literal["delete_msg"] = "delete_msg"
    params: DeleteMessageParams
    echo: str


class GetGroupMemberInfoRequest(BaseModel):
    action: Literal["get_group_member_info"] = "get_group_member_info"
    params: GetGroupMemberInfoParams
    echo: str


class SetGroupBanRequest(BaseModel):
    action: Literal["set_group_ban"] = "set_group_ban"
    params: SetGroupBanParams
    echo: str


APIRequestUnion: TypeAlias = (
    SendPrivateMessageRequest
    | SendGroupMessageRequest
    | DeleteMessageRequest
    | GetGroupMemberInfoRequest
    | SetGroupBanRequest
)
