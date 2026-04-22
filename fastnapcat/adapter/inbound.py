"""Inbound payload decoding for fastnapcat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastnapcat.adapter.tags import TAG_COMMAND, build_tags
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


@dataclass(slots=True)
class InboundEnvelope:
    model: NapCatEvent | APIResponse
    tags: tuple[str, ...]


def parse_inbound_payload(payload: dict[str, Any]) -> InboundEnvelope:
    if _looks_like_api_response(payload):
        model = APIResponse.model_validate(payload)
        return InboundEnvelope(model=model, tags=build_tags(model))

    model = _parse_event(payload)
    tags = build_tags(model)
    if _looks_like_command_message(model):
        tags = (*tags, TAG_COMMAND)
    return InboundEnvelope(model=model, tags=tags)


def debug_parse_inbound_payload(payload: dict[str, Any]) -> InboundEnvelope:
    from loguru import logger

    logger.debug(
        "parse inbound payload post_type={} message_type={} sub_type={} keys={}",
        payload.get("post_type"),
        payload.get("message_type"),
        payload.get("sub_type"),
        sorted(payload.keys()),
    )
    envelope = parse_inbound_payload(payload)
    logger.debug(
        "parsed inbound payload model={} tags={}",
        type(envelope.model).__name__,
        envelope.tags,
    )
    return envelope


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
        model = notice_map.get(key)
        if model is None:
            return UnknownNotice.model_validate(payload)
        return model.model_validate(payload)

    raise ValueError(f"unsupported inbound payload: {payload}")


def _looks_like_command_message(model: NapCatEvent) -> bool:
    if not isinstance(model, (PrivateFriendMessage, PrivateGroupMessage, GroupMessage)):
        return False
    return bool(model.raw_message.strip())
