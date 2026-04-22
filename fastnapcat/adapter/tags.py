"""Tag constants and helpers for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

from typing import TypeAlias


from fastnapcat.api.responses import APIResponse
from fastnapcat.models.events import (
    BotOffline,
    FriendAdd,
    FriendRecall,
    GroupAdminSet,
    GroupAdminUnset,
    GroupBanBan,
    GroupBanLiftBan,
    GroupCard,
    GroupMessage,
    GroupMessageSelf,
    HeartBeat,
    LifeCycleConnect,
    LifeCycleDisable,
    LifeCycleEnable,
    NapCatEvent,
    PrivateFriendMessage,
    PrivateFriendMessageSelf,
    PrivateGroupMessage,
    PrivateGroupMessageSelf,
    UnknownNotice,
    RequestFriend,
    RequestGroupAdd,
    RequestGroupInvite,
)

TagTuple: TypeAlias = tuple[str, ...]

ROOT_NAPCAT = "napcat"
TAG_META = "meta"
TAG_LIFECYCLE = "lifecycle"
TAG_HEARTBEAT = "heartbeat"
TAG_MESSAGE = "message"
TAG_MESSAGE_SENT = "message_sent"
TAG_PRIVATE = "private"
TAG_GROUP = "group"
TAG_FRIEND = "friend"
TAG_NORMAL = "normal"
TAG_REQUEST = "request"
TAG_NOTICE = "notice"
TAG_API_RESPONSE = "api_response"
TAG_COMMAND = "command"
TAG_OUTBOUND = "outbound"
TAG_OUTBOUND_MESSAGE = "outbound_message"
TAG_OUTBOUND_LOG = "outbound_log"
TAG_OUTBOUND_API = "outbound_api"
TAG_OBSERVATION = "observation"


def command_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_MESSAGE, TAG_COMMAND)


def meta_lifecycle_tags(sub_type: str) -> TagTuple:
    return (ROOT_NAPCAT, TAG_META, TAG_LIFECYCLE, sub_type)


def heartbeat_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_META, TAG_HEARTBEAT)


def private_friend_message_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_MESSAGE, TAG_PRIVATE, TAG_FRIEND)


def private_group_message_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_MESSAGE, TAG_PRIVATE, TAG_GROUP)


def group_message_tags(sub_type: str = TAG_NORMAL) -> TagTuple:
    return (ROOT_NAPCAT, TAG_MESSAGE, TAG_GROUP, sub_type)


def api_response_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_API_RESPONSE)


def outbound_message_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_OUTBOUND, TAG_OUTBOUND_MESSAGE)


def outbound_log_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_OUTBOUND, TAG_OUTBOUND_LOG)


def outbound_api_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_OUTBOUND, TAG_OUTBOUND_API)


def outbound_message_observation_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_OUTBOUND, TAG_OUTBOUND_MESSAGE, TAG_OBSERVATION)


def outbound_api_observation_tags() -> TagTuple:
    return (ROOT_NAPCAT, TAG_OUTBOUND, TAG_OUTBOUND_API, TAG_OBSERVATION)


def build_tags(model: NapCatEvent | APIResponse) -> TagTuple:
    if isinstance(model, APIResponse):
        return api_response_tags()
    if isinstance(model, HeartBeat):
        return heartbeat_tags()
    if isinstance(model, (LifeCycleEnable, LifeCycleDisable, LifeCycleConnect)):
        return meta_lifecycle_tags(model.sub_type)
    if isinstance(model, PrivateFriendMessage):
        return private_friend_message_tags()
    if isinstance(model, PrivateGroupMessage):
        return private_group_message_tags()
    if isinstance(model, GroupMessage):
        return group_message_tags(model.sub_type)
    if isinstance(model, PrivateFriendMessageSelf):
        return (ROOT_NAPCAT, TAG_MESSAGE_SENT, TAG_PRIVATE, TAG_FRIEND)
    if isinstance(model, PrivateGroupMessageSelf):
        return (ROOT_NAPCAT, TAG_MESSAGE_SENT, TAG_PRIVATE, TAG_GROUP)
    if isinstance(model, GroupMessageSelf):
        return (ROOT_NAPCAT, TAG_MESSAGE_SENT, TAG_GROUP, model.sub_type)
    if isinstance(model, RequestFriend):
        return (ROOT_NAPCAT, TAG_REQUEST, TAG_FRIEND)
    if isinstance(model, RequestGroupAdd):
        return (ROOT_NAPCAT, TAG_REQUEST, TAG_GROUP, "add")
    if isinstance(model, RequestGroupInvite):
        return (ROOT_NAPCAT, TAG_REQUEST, TAG_GROUP, "invite")
    if isinstance(model, BotOffline):
        return (ROOT_NAPCAT, TAG_NOTICE, "bot_offline")
    if isinstance(model, FriendAdd):
        return (ROOT_NAPCAT, TAG_NOTICE, "friend_add")
    if isinstance(model, FriendRecall):
        return (ROOT_NAPCAT, TAG_NOTICE, "friend_recall")
    if isinstance(model, UnknownNotice):
        tags = [ROOT_NAPCAT, TAG_NOTICE, model.notice_type]
        if model.sub_type:
            tags.append(model.sub_type)
        return tuple(tags)
    if isinstance(model, GroupAdminSet):
        return (ROOT_NAPCAT, TAG_NOTICE, "group_admin", "set")
    if isinstance(model, GroupAdminUnset):
        return (ROOT_NAPCAT, TAG_NOTICE, "group_admin", "unset")
    if isinstance(model, GroupBanBan):
        return (ROOT_NAPCAT, TAG_NOTICE, "group_ban", "ban")
    if isinstance(model, GroupBanLiftBan):
        return (ROOT_NAPCAT, TAG_NOTICE, "group_ban", "lift_ban")
    if isinstance(model, GroupCard):
        return (ROOT_NAPCAT, TAG_NOTICE, "group_card")
    raise TypeError(f"unsupported model: {type(model)!r}")
