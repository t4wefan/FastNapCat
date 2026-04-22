"""Event models for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import Field

from .base import BaseModel
from .segments import ReceiveSegment


class PrivateSender(BaseModel):
    user_id: int = Field(..., alias="user_id")
    nickname: str = Field(default="")
    sex: Literal["male", "female", "unknown"] = Field(default="unknown")
    age: int = Field(default=-1)


class GroupSender(BaseModel):
    user_id: int = Field(..., alias="user_id")
    nickname: str = Field(default="")
    card: str | None = Field(default=None)
    sex: Literal["male", "female", "unknown"] = Field(default="unknown")
    age: int = Field(default=-1)
    area: str | None = Field(default=None)
    level: str | None = Field(default=None)
    role: Literal["owner", "admin", "member"] | None = Field(default=None)
    title: str | None = Field(default=None)


class HeartBeat(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["meta_event"] = "meta_event"
    meta_event_type: Literal["heartbeat"] = "heartbeat"
    status: dict[str, Any]
    interval: int


class LifeCycleEnable(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["meta_event"] = "meta_event"
    meta_event_type: Literal["lifecycle"] = "lifecycle"
    sub_type: Literal["enable"] = "enable"


class LifeCycleDisable(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["meta_event"] = "meta_event"
    meta_event_type: Literal["lifecycle"] = "lifecycle"
    sub_type: Literal["disable"] = "disable"


class LifeCycleConnect(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["meta_event"] = "meta_event"
    meta_event_type: Literal["lifecycle"] = "lifecycle"
    sub_type: Literal["connect"] = "connect"


class MessageType(BaseModel):
    message_format: Literal["array"] = "array"
    message: list[ReceiveSegment]


class PrivateFriendMessage(MessageType):
    self_id: int = Field(..., alias="self_id")
    user_id: int = Field(..., alias="user_id")
    time: int
    message_id: int = Field(..., alias="message_id")
    message_seq: int = Field(..., alias="message_seq")
    real_id: int = Field(..., alias="real_id")
    message_type: Literal["private"] = "private"
    sender: PrivateSender
    raw_message: str = Field(..., alias="raw_message")
    font: int
    sub_type: Literal["friend"] = "friend"
    post_type: Literal["message"] = "message"


class PrivateGroupMessage(MessageType):
    self_id: int = Field(..., alias="self_id")
    user_id: int = Field(..., alias="user_id")
    time: int
    message_id: int = Field(..., alias="message_id")
    message_seq: int = Field(..., alias="message_seq")
    real_id: int = Field(..., alias="real_id")
    message_type: Literal["private"] = "private"
    sender: PrivateSender
    raw_message: str = Field(..., alias="raw_message")
    font: int
    sub_type: Literal["group"] = "group"
    post_type: Literal["message"] = "message"


class GroupMessage(MessageType):
    self_id: int = Field(..., alias="self_id")
    user_id: int = Field(..., alias="user_id")
    time: int
    message_id: int = Field(..., alias="message_id")
    message_seq: int = Field(..., alias="message_seq")
    real_id: int = Field(..., alias="real_id")
    message_type: Literal["group"] = "group"
    sender: GroupSender
    raw_message: str = Field(..., alias="raw_message")
    font: int
    sub_type: Literal["normal"] = "normal"
    post_type: Literal["message"] = "message"
    group_id: int = Field(..., alias="group_id")


class PrivateFriendMessageSelf(MessageType):
    self_id: int = Field(..., alias="self_id")
    user_id: int = Field(..., alias="user_id")
    time: int
    message_id: int = Field(..., alias="message_id")
    message_seq: int = Field(..., alias="message_seq")
    real_id: int = Field(..., alias="real_id")
    message_type: Literal["private"] = "private"
    sender: dict[str, Any]
    raw_message: str = Field(..., alias="raw_message")
    font: int
    sub_type: Literal["friend"] = "friend"
    post_type: Literal["message_sent"] = "message_sent"


class PrivateGroupMessageSelf(MessageType):
    self_id: int = Field(..., alias="self_id")
    user_id: int = Field(..., alias="user_id")
    time: int
    message_id: int = Field(..., alias="message_id")
    message_seq: int = Field(..., alias="message_seq")
    real_id: int = Field(..., alias="real_id")
    message_type: Literal["private"] = "private"
    sender: dict[str, Any]
    raw_message: str = Field(..., alias="raw_message")
    font: int
    sub_type: Literal["group"] = "group"
    post_type: Literal["message_sent"] = "message_sent"


class GroupMessageSelf(MessageType):
    self_id: int = Field(..., alias="self_id")
    user_id: int = Field(..., alias="user_id")
    time: int
    message_id: int = Field(..., alias="message_id")
    message_seq: int = Field(..., alias="message_seq")
    real_id: int = Field(..., alias="real_id")
    message_type: Literal["group"] = "group"
    sender: dict[str, Any]
    raw_message: str = Field(..., alias="raw_message")
    font: int
    sub_type: Literal["normal"] = "normal"
    post_type: Literal["message_sent"] = "message_sent"
    group_id: int = Field(..., alias="group_id")


class RequestFriend(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["request"] = "request"
    request_type: Literal["friend"] = "friend"
    user_id: int = Field(..., alias="user_id")
    comment: str
    flag: str
    quick_action: Any | None = None


class RequestGroupAdd(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["request"] = "request"
    group_id: int = Field(..., alias="group_id")
    user_id: int = Field(..., alias="user_id")
    request_type: Literal["group"] = "group"
    comment: str
    flag: str
    sub_type: Literal["add"] = "add"
    quick_action: Any | None = None


class RequestGroupInvite(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["request"] = "request"
    group_id: int = Field(..., alias="group_id")
    user_id: int = Field(..., alias="user_id")
    request_type: Literal["group"] = "group"
    comment: str
    flag: str
    sub_type: Literal["invite"] = "invite"
    quick_action: Any | None = None


class BotOffline(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["notice"] = "notice"
    notice_type: Literal["bot_offline"] = "bot_offline"
    user_id: int = Field(..., alias="user_id")
    tag: str
    message: str


class FriendAdd(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["notice"] = "notice"
    notice_type: Literal["friend_add"] = "friend_add"
    user_id: int = Field(..., alias="user_id")


class FriendRecall(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["notice"] = "notice"
    notice_type: Literal["friend_recall"] = "friend_recall"
    user_id: int = Field(..., alias="user_id")
    message_id: int = Field(..., alias="message_id")


class UnknownNotice(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["notice"] = "notice"
    notice_type: str = Field(..., alias="notice_type")
    sub_type: str | None = Field(default=None, alias="sub_type")


class GroupAdminSet(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["notice"] = "notice"
    group_id: int = Field(..., alias="group_id")
    user_id: int = Field(..., alias="user_id")
    notice_type: Literal["group_admin"] = "group_admin"
    sub_type: Literal["set"] = "set"


class GroupAdminUnset(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["notice"] = "notice"
    group_id: int = Field(..., alias="group_id")
    user_id: int = Field(..., alias="user_id")
    notice_type: Literal["group_admin"] = "group_admin"
    sub_type: Literal["unset"] = "unset"


class GroupBanBan(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["notice"] = "notice"
    group_id: int = Field(..., alias="group_id")
    user_id: int = Field(..., alias="user_id")
    notice_type: Literal["group_ban"] = "group_ban"
    operator_id: int = Field(..., alias="operator_id")
    duration: int
    sub_type: Literal["ban"] = "ban"


class GroupBanLiftBan(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["notice"] = "notice"
    group_id: int = Field(..., alias="group_id")
    user_id: int = Field(..., alias="user_id")
    notice_type: Literal["group_ban"] = "group_ban"
    operator_id: int = Field(..., alias="operator_id")
    duration: int
    sub_type: Literal["lift_ban"] = "lift_ban"


class GroupCard(BaseModel):
    time: int
    self_id: int = Field(..., alias="self_id")
    post_type: Literal["notice"] = "notice"
    group_id: int = Field(..., alias="group_id")
    user_id: int = Field(..., alias="user_id")
    notice_type: Literal["group_card"] = "group_card"
    card_new: str = Field(..., alias="card_new")
    card_old: str = Field(..., alias="card_old")


MetaEvent: TypeAlias = HeartBeat | LifeCycleEnable | LifeCycleDisable | LifeCycleConnect
MessageEvent: TypeAlias = PrivateFriendMessage | PrivateGroupMessage | GroupMessage
MessageSentEvent: TypeAlias = (
    PrivateFriendMessageSelf | PrivateGroupMessageSelf | GroupMessageSelf
)
RequestEvent: TypeAlias = RequestFriend | RequestGroupAdd | RequestGroupInvite
NoticeEvent: TypeAlias = (
    BotOffline
    | FriendAdd
    | FriendRecall
    | UnknownNotice
    | GroupAdminSet
    | GroupAdminUnset
    | GroupBanBan
    | GroupBanLiftBan
    | GroupCard
)
NapCatEvent: TypeAlias = (
    MetaEvent | MessageEvent | MessageSentEvent | RequestEvent | NoticeEvent
)
