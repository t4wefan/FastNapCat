from __future__ import annotations

import asyncio

import pytest

from fastnapcat import FastNapCat, NoticeContext
from fastnapcat.models.events import FriendAdd


def make_friend_add() -> FriendAdd:
    return FriendAdd(
        time=123,
        self_id=1,
        post_type="notice",
        notice_type="friend_add",
        user_id=2,
    )


@pytest.mark.asyncio
async def test_notice_handler_receives_notice_context():
    bot = FastNapCat()
    seen: dict[str, object] = {}
    ready = asyncio.Event()

    @bot.on.notice()
    async def handle(ctx: NoticeContext, payload: FriendAdd):
        seen["user_id"] = ctx.event.user_id
        seen["payload_type"] = type(payload)
        ready.set()

    await bot.astart()
    try:
        await bot.bridge.handle_inbound_text(
            make_friend_add().model_dump_json(by_alias=True)
        )
        await asyncio.wait_for(ready.wait(), timeout=1)
        assert seen["user_id"] == 2
        assert seen["payload_type"] is FriendAdd
    finally:
        await bot.astop()
