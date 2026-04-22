## fastnapcat

`fastnapcat` 是一个基于 FastEvents 的 NapCat / OneBot 事件驱动机器人框架。

它的目标不是再封装一层传统 bot SDK，而是在保留事件模型的前提下，把机器人开发里最常见的几类能力整理成统一入口：

- NapCat websocket 接入
- 消息 / 通知 / 请求 / 元事件订阅
- 命令解析与参数注入
- 消息上下文与常用依赖注入
- API 调用与消息构造
- 会话等待能力
- 直接透传 FastEvents 原生能力

这份文档重点说明两件事：

1. 每个功能应该怎么用
2. 每个功能在什么边界下工作、什么时候不该用

---

## 安装

项目当前使用 `uv` 管理依赖。

```bash
uv add https://github.com/t4wefan/FastNapCat.git
```

运行示例：

```bash
uv run demo.py
```

如果你使用 NapCat 鉴权，可以在环境变量里提供 `ACCESS_TOKEN`。

---

## 快速开始

```python
from fastnapcat import FastNapCat, MessageContext, logger, message_text


bot = FastNapCat(
    ws_url="ws://127.0.0.1:16100",
)


@bot.on.private()
async def on_private(
    ctx: MessageContext,
    text: str = message_text(),
    console=logger(),
):
    await console.info(f"received: {text}")
    await ctx.send("ok")


bot.run()
```

这个例子里最常见的几个概念分别是：

- `FastNapCat(...)`：创建机器人应用
- `@bot.on.private()`：订阅私聊消息事件
- `MessageContext`：当前消息对应的高频操作对象
- `message_text()`：把消息原文注入成字符串
- `logger()`：注入一个面向当前事件的日志代理

### 什么时候用这个写法

这个写法适合：

- 先快速接入 NapCat websocket
- 处理最常见的消息收发
- 不需要自己管理底层事件总线

### 边界说明

- 如果你不传 `ws_url`，应用仍然可以启动，但不会主动连接 NapCat
- `MessageContext` 只能用于消息事件 handler，不能用于 `meta` / `notice` / `request`
- `message_text()` 只对消息事件有意义；非消息事件下不要这样注入

---

## 入口对象

`FastNapCat` 是主要入口，统一挂载了几类常用能力：

- `bot.on`：事件订阅入口
- `bot.command(...)`：命令注册
- `bot.api`：API 调用
- `bot.prompt(...)` / `bot.listen(...)`：会话等待
- `bot.fastevents`：直接访问底层 FastEvents app

### 使用建议

- 想写机器人主逻辑时，优先使用 `bot.on`、`bot.command(...)`、`bot.api`
- 只有在你明确知道 FastEvents 原生语义时，再直接使用 `bot.fastevents`

常见启动方式：

- `bot.run()`：阻塞运行
- `await bot.astart()`：异步启动
- `await bot.astop()`：异步停止

`run()` 已支持 Ctrl+C 优雅退出。

### 边界说明

- `run()` 适合脚本入口，不适合已经有自己事件循环的场景
- 如果你的程序本身已经运行在 asyncio 环境里，优先使用 `await bot.astart()` / `await bot.astop()`
- `FastNapCat` 本身是应用入口，不建议在一个进程里随意重复创建很多实例复用同一套全局逻辑

---

## 事件订阅

### 消息事件

```python
from fastnapcat import FastNapCat, MessageContext


bot = FastNapCat(ws_url="ws://127.0.0.1:16100")


@bot.on.private()
async def on_private(ctx: MessageContext):
    await ctx.send("private ok")


@bot.on.group()
async def on_group(ctx: MessageContext):
    await ctx.send("group ok")
```

### 默认调度优先级

当前默认约定是：

- `bot.command(...)` 默认 `level=10`
- `bot.on.xxx(...)` 默认 `level=20`

这意味着命令会先于普通消息订阅器执行。

### 命令与普通消息的关系

- 如果一条消息 **不是命令**，command subscriber 会 `not consume`，消息会继续传给下一层普通 handler
- 如果一条消息 **命中了某个命令**，命令 handler 会消费这条消息，普通消息 handler 默认不会再处理它
- 如果命令 **命中了但参数不合法**，当前命令会直接回复参数帮助，并视为已消费，不再继续向下一层传递

也可以通过 `bot.on.message(...)` 统一订阅消息，并用参数控制：

- `private=True / False`
- `group=True / False`
- `sub_type=...`

### 什么时候用 `on.message(...)`

适合：

- 想把私聊和群聊统一处理
- 只想在一处做路由判断

不太适合：

- 私聊、群聊逻辑差异明显
- 你更希望 handler 的语义直接体现在装饰器名字上

### 其他事件

除了消息事件，也支持：

- `@bot.on.meta()`
- `@bot.on.notice()`
- `@bot.on.request()`

对应可注入上下文：

- `MetaContext`
- `NoticeContext`
- `RequestContext`
- `NapCatEventContext`

### 边界说明

- `meta` / `notice` / `request` 不是消息事件，不要在这些 handler 中注入 `MessageContext`
- 如果你只关心原始事件对象，也可以直接注入对应 payload model 或 `RuntimeEvent`

---

## 消息上下文

`MessageContext` 是机器人开发里最常用的上下文对象，主要提供：

- `await ctx.send(...)`
- `await ctx.reply(...)`
- `await ctx.at_sender(...)`
- `await ctx.ban_user(...)`（仅群消息可用）

常见属性：

- `ctx.user_id`
- `ctx.group_id`
- `ctx.message_id`
- `ctx.text`
- `ctx.segments`
- `ctx.is_private`
- `ctx.is_group`

示例：

```python
from fastnapcat import FastNapCat, MessageContext


bot = FastNapCat(ws_url="ws://127.0.0.1:16100")


@bot.on.group()
async def handle(ctx: MessageContext):
    await ctx.reply("收到")
```

### 常见用法

- `ctx.send(...)`：给当前会话发送普通消息
- `ctx.reply(...)`：携带回复段发送
- `ctx.at_sender(...)`：在群里 @ 当前发送者
- `ctx.prompt(...)`：等待同一会话的下一条消息

### `send()` 支持的内容

`ctx.send(...)` 可以发送：

- 字符串
- 由 `message_builder` 构造的消息段列表
- 接收到的图片对象
- `PIL.Image.Image`

这意味着你可以直接把收到的图片再发回去，也可以把 PIL 图片对象直接发送。

### 边界说明

- `ban_user()` 只对群消息有效；私聊调用会抛异常
- `reply()` 依赖当前消息的 `message_id`
- `prompt()` 只等待“同一会话”的下一条消息：
  - 私聊：同一 `user_id`
  - 群聊：同一 `group_id` 且同一 `user_id`
- `prompt()` 当前会消费这条 follow-up 消息，因此它不会再继续落到普通消息 handler

---

## 依赖注入

`fastnapcat` 当前主要有两类注入方式：

### 1. 类型注入

直接在参数上写注解：

- `MessageContext`
- `CommandContext`
- `MetaContext`
- `NoticeContext`
- `RequestContext`
- `NapCatEventContext`
- `CommandArgs` 子类

适合：

- 注入完整上下文对象
- 注入命令参数模型
- 注入原始 payload model

### 2. 函数式依赖注入

通过默认值注入高频派生值：

- `message_text()`：消息原文字符串
- `images()`：图片集合
- `logger()`：事件日志代理

示例：

```python
from fastnapcat import FastNapCat, MessageContext, images, logger, message_text


bot = FastNapCat(ws_url="ws://127.0.0.1:16100")


@bot.on.private()
async def handle(
    ctx: MessageContext,
    text: str = message_text(),
    pics=images(),
    console=logger(),
):
    await console.info(text)
    if pics:
        await ctx.send(pics[0])
```

### 边界说明

- `message_text()` 只返回消息原文字符串，不负责命令解析
- `images()` 只提取图片消息段，不会处理语音、文件、视频
- `logger()` 是面向当前事件的日志代理，不是全局日志配置入口

---

## 命令系统

### 定义命令

```python
from fastnapcat import CommandArgs, FastNapCat, MessageContext, logger


class EchoArgs(CommandArgs):
    content: str
    times: int = 1


bot = FastNapCat(ws_url="ws://127.0.0.1:16100")


@bot.command("echo", prefixes=["/"])
async def echo(ctx: MessageContext, args: EchoArgs, console=logger()):
    await console.info(args.model_dump_json())
    for _ in range(max(1, args.times)):
        await ctx.send(args.content)
```

对于命令：

```text
/echo --content hello --times 2
```

会得到：

- `args.content == "hello"`
- `args.times == 2`
- `args.parsed_command.name == "echo"`
- `args.parsed_command.input_name == "/echo"`
- `args.parsed_command.argv == ["--content", "hello", "--times", "2"]`
- `args.parsed_command.flags == {"content": "hello", "times": "2"}`

### `CommandArgs` 的用途

`CommandArgs` 把两类信息分开了：

- 你的业务字段，例如 `flag1`
- 内部解析元信息 `parsed_command`

这意味着 handler 里既可以直接拿到业务参数，也能在需要时访问原始命令解析结果。

### 当前命令匹配语义

- `@bot.command("echo", prefixes=["/"])` 匹配 `/echo ...`
- `aliases=["say"]` 可以匹配 `/say ...`
- command 默认优先于普通 `on.message` / `on.private` / `on.group`

### 参数错误时的行为

- 如果命令名没匹配上：当前 command `not consume`，消息继续向后分发
- 如果命令名匹配上，但 `CommandArgs` 校验失败：
  - 框架会自动回复命令帮助
  - 当前事件视为已消费
  - 不会继续传给普通消息 handler

### 当前注意事项

当前命令注册接口已经支持：

- 命令名
- 私聊 / 群聊范围控制
- aliases
- description
- prefixes

帮助文本会基于这些信息自动生成，但目前它仍然属于轻量命令系统，不是完整 CLI / shell 框架。

---

## 图片接收与处理

`images()` 返回的不是裸列表，而是 `ReceiveImages`。

单张图片对象是 `ReceiveImageAsset`，支持：

- `await image.download()`
- `await image.to_pil()`

图片集合支持：

- `pics.images`
- `pics[0]`
- `await pics.to_pils()`

示例：

```python
from fastnapcat import FastNapCat, MessageContext, images, logger
from fastnapcat.models.segments import ReceiveImages


bot = FastNapCat(ws_url="ws://127.0.0.1:16100")


@bot.on.private()
async def on_private(
    ctx: MessageContext,
    pics: ReceiveImages = images(),
    console=logger(),
):
    if pics:
        first = pics[0]
        pil_image = await first.to_pil()
        await console.info(pil_image.size)
        await ctx.send(first)
```

### 注意事项

- `images()` 只会提取消息段里的图片
- 如果当前事件不是消息事件，返回的是空集合
- 接收到的图片对象可以直接回发，也可以先转成 PIL 处理后再发送
- 图片下载和 `to_pil()` 依赖图片源可访问；如果是失效链接或非法 base64，会抛异常

---

## API 调用

你可以通过 `bot.api` 直接访问常用 OneBot / NapCat API。

当前已封装的高频调用包括：

- `send_private_message(...)`
- `send_group_message(...)`
- `delete_message(...)`
- `get_group_member_info(...)`
- `set_group_ban(...)`

示例：

```python
from fastnapcat import FastNapCat


bot = FastNapCat(ws_url="ws://127.0.0.1:16100")


async def demo():
    await bot.api.send_private_message(user_id=123456, message="hello")
```

### 什么时候用 `bot.api`

适合：

- 主动给任意用户 / 群发送消息
- 不依赖当前上下文时调用 OneBot API
- 在业务逻辑里显式做平台操作

### 边界说明

- `bot.api` 是对常用 API 的高层封装，不等于完整覆盖 NapCat 所有接口
- API 调用成功与否取决于 NapCat 响应，不等于一定产生业务效果
- 某些接口只对群聊或特定权限可用，例如群管相关接口

---

## 消息构造

如果你需要更精细地构造消息段，可以使用 `message_builder`：

- `message_builder.text(...)`
- `message_builder.at(...)`
- `message_builder.reply(...)`
- `message_builder.face(...)`
- `message_builder.image(...)`
- `message_builder.chain(...)`

示例：

```python
from fastnapcat import FastNapCat, MessageContext, message_builder


bot = FastNapCat(ws_url="ws://127.0.0.1:16100")


@bot.on.group()
async def handle(ctx: MessageContext):
    await ctx.send(
        message_builder.chain(
            message_builder.at(ctx.user_id),
            message_builder.text(" hello"),
        )
    )
```

### 什么时候用 `message_builder`

适合：

- 需要精确控制消息段顺序
- 要组合 reply / at / text / image 等多段消息

不太适合：

- 只是发送一条简单文本
- 已经拿到 `ReceiveImageAsset` 并希望直接回发

---

## 会话能力

`fastnapcat` 目前提供的是基于事件流监听的轻量会话能力：

- `await ctx.prompt(...)`

示例：

```python
from fastnapcat import FastNapCat, MessageContext


bot = FastNapCat(ws_url="ws://127.0.0.1:16100")


@bot.on.private()
async def ask_once(ctx: MessageContext):
    await ctx.send("请回复一句话")
    next_ctx = await ctx.prompt(timeout=30)
    await next_ctx.reply(f"你刚才说的是：{next_ctx.text}")
```

### 注意事项

- 当前会话能力是轻量封装，不是完整的多轮状态机会话框架
- `prompt()` 更适合做简单等待、下一条消息确认、一次性交互
- `prompt()` 会消费命中的 follow-up 消息，因此这条消息默认不会再被普通消息 handler 处理
- 如果你需要复杂会话状态、分支流程、持久化恢复，建议在业务层自己维护状态机

---

## 直接使用 FastEvents 原生能力

`fastnapcat` 直接导出了部分 `FastEvents` 能力：

- `FastEvents`
- `EventContext`
- `RuntimeEvent`
- `dependency`
- `new_event`

同时也能通过 `bot.fastevents` 直接访问底层 app。

示例：

```python
from fastnapcat import FastNapCat, RuntimeEvent


bot = FastNapCat()


@bot.fastevents.on(("biz", "custom"), level=0)
async def handle(event: RuntimeEvent):
    print(event.payload)
```

---

## 注意事项

### 1. `MessageContext` 只适用于消息事件

如果当前 handler 订阅的不是消息事件，就不要注入 `MessageContext`。

### 2. 命令参数注入依赖消息原文

`CommandArgs` 只适用于被识别为命令的消息事件。

命令未命中时会继续向下一层传播；命令命中但参数错误时会由命令系统直接回复帮助并消费事件。

### 3. `ban_user()` 只适用于群消息

在私聊里调用会抛异常。

### 4. `images()` 在非消息事件里会返回空集合

这属于正常行为，不代表框架异常。

### 5. 当前文档重点介绍“怎么用”

如果你想看更细的设计和演进过程，可以继续参考：

- `docs/fastnapcat-implementation-plan.md`
- `docs/fastnapcat-di-interface-spec.md`
- `docs/fastnapcat-rewrite-plan.md`

---

## 当前状态

当前项目已经完成主链路打通，适合继续围绕以下方向迭代：

- 文档完善
- API 面稳定性提升
- 命令 / 会话能力继续增强
- 更多测试覆盖

如果你想快速判断它是否已经能用：答案是已经能跑通消息、命令、上下文注入、常用 API 和基础会话能力。
