from __future__ import annotations

import asyncio

from fastnapcat import FastNapCat


bot = FastNapCat(ws_url="ws://127.0.0.1:16100", access_token="1_dzglLBtPdLuVEc")


async def main() -> None:
    await bot.astart()
    try:
        # 主动发群消息
        response = await bot.api.send_group_message(
            123456789,
            "hello from fastnapcat",
        )
        print(response)

        # 主动发私聊消息
        private_response = await bot.api.send_private_message(
            10000,
            "hello private message",
        )
        print(private_response)

        while True:
            await asyncio.sleep(10)
    finally:
        await bot.astop()


if __name__ == "__main__":
    asyncio.run(main())
