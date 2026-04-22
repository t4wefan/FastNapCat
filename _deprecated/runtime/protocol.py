"""Inbound protocol parsing for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any

from loguru import logger

from fastnapcat.adapter.tags import (
    ROOT_NAPCAT,
    TAG_GROUP,
    TAG_MESSAGE_SENT,
    TAG_NOTICE,
    TAG_PRIVATE,
    TAG_REQUEST,
    api_response_tags,
    command_tag,
    group_message_tags,
    heartbeat_tags,
    meta_lifecycle_tags,
    private_friend_message_tags,
    private_group_message_tags,
)
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
    RequestFriend,
    RequestGroupAdd,
    RequestGroupInvite,
)


@dataclass(slots=True)
class ParsedEnvelope:
    model: NapCatEvent | APIResponse
    tags: tuple[str, ...]
    command_name: str | None = None


def parse_inbound_payload(payload: dict[str, Any]) -> ParsedEnvelope:
    if _looks_like_api_response(payload):
        return ParsedEnvelope(
            model=APIResponse.model_validate(payload), tags=api_response_tags()
        )

    model = _parse_event(payload)
    tags = _build_tags(model)
    if isinstance(model, HeartBeat):
        logger.info("heartbeat received")
    command_name = _extract_command_name(model)
    if command_name:
        tags = (*tags, command_tag(command_name))
    return ParsedEnvelope(model=model, tags=tags, command_name=command_name)


def _looks_like_api_response(payload: dict[str, Any]) -> bool:
    return "status" in payload and "retcode" in payload


def _parse_event(payload: dict[str, Any]) -> NapCatEvent:
    post_type = payload.get("post_type")
    if post_type == "meta_event":
        meta_event_type = payload.get("meta_event_type")
        if meta_event_type == "heartbeat":
            return HeartBeat.model_validate(payload)
        subtype = payload.get("sub_type")
        if not isinstance(subtype, str):
            raise ValueError(f"unsupported lifecycle subtype: {subtype!r}")
        lifecycle_map = {
            "enable": LifeCycleEnable,
            "disable": LifeCycleDisable,
            "connect": LifeCycleConnect,
        }
        lifecycle_model = lifecycle_map.get(subtype)
        if lifecycle_model is None:
            raise ValueError(f"unsupported lifecycle subtype: {subtype!r}")
        return lifecycle_model.model_validate(payload)

    if post_type == "message":
        if payload.get("message_type") == "group":
            return GroupMessage.model_validate(payload)
        if payload.get("sub_type") == "friend":
            return PrivateFriendMessage.model_validate(payload)
        return PrivateGroupMessage.model_validate(payload)

    if post_type == "message_sent":
        if payload.get("message_type") == "group":
            return GroupMessageSelf.model_validate(payload)
        if payload.get("sub_type") == "friend":
            return PrivateFriendMessageSelf.model_validate(payload)
        return PrivateGroupMessageSelf.model_validate(payload)

    if post_type == "request":
        if payload.get("request_type") == "friend":
            return RequestFriend.model_validate(payload)
        if payload.get("sub_type") == "add":
            return RequestGroupAdd.model_validate(payload)
        return RequestGroupInvite.model_validate(payload)

    if post_type == "notice":
        notice_type = payload.get("notice_type")
        if not isinstance(notice_type, str):
            raise ValueError(f"unsupported notice type: {notice_type!r}")
        notice_map = {
            "bot_offline": BotOffline,
            "friend_add": FriendAdd,
            "friend_recall": FriendRecall,
            "group_admin:set": GroupAdminSet,
            "group_admin:unset": GroupAdminUnset,
            "group_ban:ban": GroupBanBan,
            "group_ban:lift_ban": GroupBanLiftBan,
            "group_card": GroupCard,
        }
        key = (
            notice_type
            if notice_type
            in {"bot_offline", "friend_add", "friend_recall", "group_card"}
            else f"{notice_type}:{payload.get('sub_type')}"
        )
        notice_model = notice_map.get(key)
        if notice_model is None:
            raise ValueError(f"unsupported notice subtype: {key!r}")
        return notice_model.model_validate(payload)

    raise ValueError(f"unsupported inbound payload: {payload}")


def _build_tags(model: NapCatEvent | APIResponse) -> tuple[str, ...]:
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
        return (ROOT_NAPCAT, TAG_MESSAGE_SENT, TAG_PRIVATE, "friend")
    if isinstance(model, PrivateGroupMessageSelf):
        return (ROOT_NAPCAT, TAG_MESSAGE_SENT, TAG_PRIVATE, TAG_GROUP)
    if isinstance(model, GroupMessageSelf):
        return (ROOT_NAPCAT, TAG_MESSAGE_SENT, TAG_GROUP, model.sub_type)
    if isinstance(model, RequestFriend):
        return (ROOT_NAPCAT, TAG_REQUEST, "friend")
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


def _extract_command_name(model: NapCatEvent | APIResponse) -> str | None:
    if not isinstance(model, (PrivateFriendMessage, PrivateGroupMessage, GroupMessage)):
        return None
    raw = model.raw_message.strip()
    if not raw:
        return None
    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = raw.split()
    if not parts:
        return None
    return parts[0]
