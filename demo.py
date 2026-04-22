from fastnapcat import (
    CommandArgs,
    CommandContext,
    FastNapCat,
    MessageContext,
    MetaContext,
    images,
    logger,
    message_builder,
    message_text,
)
import os

from pydantic import Field
from dotenv import load_dotenv

load_dotenv()

bot = FastNapCat(
    ws_url="ws://127.0.0.1:16100",
    access_token=os.environ.get("ACCESS_TOKEN"),
    debug=True,
)


class EchoArgs(CommandArgs):
    content: str = Field(description="要回显的文本内容")
    times: int = Field(default=1, description="重复发送次数")


class BanArgs(CommandArgs):
    duration: int = Field(default=60, description="禁言秒数")


class PrivateSendArgs(CommandArgs):
    user_id: int = Field(description="目标用户 ID")
    content: str = Field(description="要发送的私聊内容")


@bot.on.meta()
async def on_meta(ctx: MetaContext, console=logger()) -> None:
    await console.info(f"meta event received: {type(ctx.event).__name__}")


@bot.on.private()
async def on_private(
    ctx: MessageContext,
    message: str = message_text(),
    console=logger(),
    pics=images(),
):
    await console.info(f"private message: {message}")
    if pics.images:
        first = pics.images[0]
        pil_image = await first.to_pil()
        await console.info(f"echo first image, size={pil_image.size}")
        res = await ctx.send(first)
        await console.info(f"echoed image message_id={res.message_id}")
        return
    await ctx.send("收到私聊消息，发送图片可体验图片回显。")


@bot.command("echo", prefixes=["/"], aliases=["say"], description="回显输入内容")
async def echo_command(
    ctx: MessageContext,
    args: EchoArgs,
    console=logger(),
) -> None:
    await console.info(
        "received echo command: "
        + args.model_dump_json()
        + f" matched_name={args.parsed_command.name}"
    )
    repeat = max(1, args.times)
    for _ in range(repeat):
        await ctx.send(args.content)


@bot.command("banme", prefixes=["/"], description="在群里把自己禁言一小会")
async def ban_me(ctx: MessageContext, args: BanArgs, console=logger()) -> None:
    if not ctx.is_group:
        await ctx.send("/banme 只能在群聊里使用")
        return
    await console.info(f"ban current user for {args.duration}s")
    await ctx.ban_user(duration=args.duration)
    await ctx.reply(f"已尝试禁言你 {args.duration} 秒")


@bot.command("ask", prefixes=["/"], description="演示 prompt 会话等待")
async def ask_next_message(ctx: MessageContext, console=logger()) -> None:
    await ctx.send("请在 30 秒内回复下一条消息")
    try:
        next_ctx = await ctx.prompt(timeout=30)
    except TimeoutError:
        await ctx.send("等待超时")
        return
    await console.info(f"prompt received follow-up: {next_ctx.text}")
    await next_ctx.reply(f"你刚才说的是：{next_ctx.text}")


@bot.command(
    "sendpm",
    prefixes=["/"],
    description="演示通过 bot.api 主动发送私聊消息",
)
async def send_private_via_api(
    args: PrivateSendArgs,
    console=logger(),
) -> None:
    response = await bot.api.send_private_message(
        user_id=args.user_id,
        message=args.content,
    )
    await console.info("sendpm response=" + response.model_dump_json())


@bot.command("help", prefixes=["/"], description="展示命令帮助")
async def show_help(ctx: MessageContext) -> None:
    await ctx.send(bot.commands.help_text())


if __name__ == "__main__":
    bot.run()
