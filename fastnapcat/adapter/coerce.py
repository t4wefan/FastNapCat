"""Coerce decoded FastEvents payloads back into NapCat protocol models."""

from __future__ import annotations

from typing import Any

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
    MessageEvent,
    MessageSentEvent,
    MetaEvent,
    NapCatEvent,
    NoticeEvent,
    PrivateFriendMessage,
    PrivateFriendMessageSelf,
    PrivateGroupMessage,
    PrivateGroupMessageSelf,
    RequestEvent,
    RequestFriend,
    RequestGroupAdd,
    RequestGroupInvite,
    UnknownNotice,
)


def coerce_napcat_event(payload: object) -> NapCatEvent:
    if isinstance(payload, _NAPCAT_EVENT_MODELS):
        return payload
    data = _require_payload_dict(payload)
    post_type = data.get("post_type")
    if post_type == "meta_event":
        return coerce_meta_event(data)
    if post_type == "message":
        return coerce_message_event(data)
    if post_type == "message_sent":
        return coerce_message_sent_event(data)
    if post_type == "request":
        return coerce_request_event(data)
    if post_type == "notice":
        return coerce_notice_event(data)
    raise ValueError(f"unsupported inbound payload: {payload}")


def coerce_meta_event(payload: object) -> MetaEvent:
    if isinstance(payload, _META_EVENT_MODELS):
        return payload
    data = _require_payload_dict(payload)
    meta_event_type = data.get("meta_event_type")
    if meta_event_type == "heartbeat":
        return HeartBeat.model_validate(data)
    subtype = data.get("sub_type")
    lifecycle_map = {
        "enable": LifeCycleEnable,
        "disable": LifeCycleDisable,
        "connect": LifeCycleConnect,
    }
    lifecycle_model = lifecycle_map.get(subtype)
    if lifecycle_model is None:
        raise ValueError(f"unsupported lifecycle subtype: {subtype!r}")
    return lifecycle_model.model_validate(data)


def coerce_message_event(payload: object) -> MessageEvent:
    if isinstance(payload, _MESSAGE_EVENT_MODELS):
        return payload
    data = _require_payload_dict(payload)
    if data.get("message_type") == "group":
        return GroupMessage.model_validate(data)
    if data.get("sub_type") == "friend":
        return PrivateFriendMessage.model_validate(data)
    return PrivateGroupMessage.model_validate(data)


def coerce_message_sent_event(payload: object) -> MessageSentEvent:
    if isinstance(payload, _MESSAGE_SENT_EVENT_MODELS):
        return payload
    data = _require_payload_dict(payload)
    if data.get("message_type") == "group":
        return GroupMessageSelf.model_validate(data)
    if data.get("sub_type") == "friend":
        return PrivateFriendMessageSelf.model_validate(data)
    return PrivateGroupMessageSelf.model_validate(data)


def coerce_request_event(payload: object) -> RequestEvent:
    if isinstance(payload, _REQUEST_EVENT_MODELS):
        return payload
    data = _require_payload_dict(payload)
    if data.get("request_type") == "friend":
        return RequestFriend.model_validate(data)
    if data.get("sub_type") == "add":
        return RequestGroupAdd.model_validate(data)
    return RequestGroupInvite.model_validate(data)


def coerce_notice_event(payload: object) -> NoticeEvent:
    if isinstance(payload, _NOTICE_EVENT_MODELS):
        return payload
    data = _require_payload_dict(payload)
    notice_type = data.get("notice_type")
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
        else f"{notice_type}:{data.get('sub_type')}"
    )
    model = notice_map.get(key)
    if model is None:
        return UnknownNotice.model_validate(data)
    return model.model_validate(data)


def _require_payload_dict(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("NapCat event payload must be a dict or known event model")
    return payload


_META_EVENT_MODELS = (HeartBeat, LifeCycleEnable, LifeCycleDisable, LifeCycleConnect)
_MESSAGE_EVENT_MODELS = (PrivateFriendMessage, PrivateGroupMessage, GroupMessage)
_MESSAGE_SENT_EVENT_MODELS = (
    PrivateFriendMessageSelf,
    PrivateGroupMessageSelf,
    GroupMessageSelf,
)
_REQUEST_EVENT_MODELS = (RequestFriend, RequestGroupAdd, RequestGroupInvite)
_NOTICE_EVENT_MODELS = (
    BotOffline,
    FriendAdd,
    FriendRecall,
    UnknownNotice,
    GroupAdminSet,
    GroupAdminUnset,
    GroupBanBan,
    GroupBanLiftBan,
    GroupCard,
)
_NAPCAT_EVENT_MODELS = (
    *_META_EVENT_MODELS,
    *_MESSAGE_EVENT_MODELS,
    *_MESSAGE_SENT_EVENT_MODELS,
    *_REQUEST_EVENT_MODELS,
    *_NOTICE_EVENT_MODELS,
)
