# fastnapcat 实现规划

## 1. 目标

`fastnapcat` 的目标不是再包一层 OneBot SDK，而是以 `FastEvents` 为事件应用内核，构建一个面向 NapCat / OneBot 的事件驱动机器人框架。

它需要同时满足几件事：

- 复用 `FastEvents` 的边界纪律：`app` 负责声明与组合，`bus` 负责运行时，复杂协议能力通过扩展和 DI 注入实现。
- 内置 NapCat 连接体验，让用户像 `onebot-mq` 一样直接创建 bot 对象、注册事件、启动运行，而不是自己手动装配 `bus`、`app`、WebSocket 客户端。
- 吸收 `py-napcat` 的数据模型和消息段能力，保留类型安全和 Pydantic 校验能力。
- 吸收 `onebot-mq/native_bot` 的易用层：消息会话、命令装饰器、参数解析、发送/回复快捷操作。
- 尽量使用事件驱动模型，而不是把核心设计拉回 callback + mutable session 的传统 bot 框架风格。

一句话概括：

`fastnapcat = FastEvents core + NapCat transport adapter + bot-oriented extensions + DI contexts`

---

## 2. 参考项目结论

### 2.1 来自 `FastEvents` 的约束

必须继承以下边界：

- `publish()` 只表示事件进入 bus，不表示事件已经处理完成。
- `app` 不是 host，不吞掉所有资源和生命周期。
- richer capability 不应继续堆进通用 `EventContext`，而应通过 DI typed context 注入。
- extension 只是普通对象组合，不是受框架托管的插件系统。
- extension 只能依赖 `app` 的公开能力，不能把 `bus` 暴露成扩展的常规依赖。
 
这意味着 `fastnapcat` 不能把 OneBot 的高层语义直接塞回 core，也不能为 command / session / reply / waiter 这些能力去修改 dispatcher 语义。

### 2.2 来自 `py-napcat` 的可复用资产

`py-napcat` 里最值得直接拷贝或等价迁移的是：

- 事件模型：`meta_event` / `message` / `request` / `notice` 及其细分类型。
- 消息段模型：接收段、发送段、Reply / At / Text / Image 等基础结构。
- 消息构建器：`text()` / `at()` / `reply()` / `image()` / `chain()` 这一类 builder API。
- API request 模型与 builder：发送消息、撤回、群成员信息、禁言等常用操作。

这些内容属于协议建模层，和 `FastEvents` 的理念不冲突，适合成为 `fastnapcat` 的协议模型基础。

### 2.3 来自 `onebot-mq/native_bot` 的可借鉴能力

`onebot-mq` 值得保留的是“使用体验”，不是内部架构：

- 直接创建 bot 对象并运行。
- 针对消息事件提供高频快捷能力：`send()`、`reply()`、`at_sender()`、`ban_user()`。
- 命令系统支持别名、私聊/群聊启停、run level、参数模型解析。
- 参数解析支持 `shlex` 风格的 POSIX flag + position args。

但它现在是直接挂在 websocket session 上做回调分发，这一层需要重构成 `FastEvents` 驱动，而不是原样照搬。

---

## 3. 总体架构

建议 `fastnapcat` 分成六层。

### 3.1 协议模型层 `models`

负责 OneBot / NapCat 数据建模。

包含：

- event models
- sender / notice / request / meta models
- receive segments / send segments
- API request / response models

这一层基本是纯 Pydantic 结构，不感知 `FastEvents`。

### 3.2 协议工具层 `message` / `api`

负责协议侧构造能力。

包含：

- message builder
- CQ / segment 转换工具
- API request builder
- 常用响应结构

这一层仍然不直接依赖 `FastEvents`，是可单独复用的协议工具箱。

### 3.3 运行时适配层 `runtime`

负责 NapCat 连接和入站/出站事件桥接。

核心职责：

- 管理 WebSocket 连接生命周期
- 接收 NapCat 原始 JSON 包
- 识别是事件包还是 API 响应包
- 将入站数据转成 `fastnapcat.models` 中的强类型对象
- 再发布到 `FastEvents` app/bus 中
- 处理出站 API 请求与 echo 关联

这一层是 `onebot-mq` 的 websocket 体验在 `FastEvents` 架构下的重建版本。

### 3.4 事件语义层 `adapter`

负责把 NapCat 数据模型投影为 `FastEvents` 中的 tags DSL，而不是把事件语义主要编码成点号路径字符串。

虽然框架仍然可以兼容 `.` 和通配风格订阅，但在 fastnapcat 自己的设计里，应优先使用 tag 组合表达语义。

也就是说，我们更希望这样思考事件：

- 这是一个 `napcat` 事件
- 它属于 `message`
- 它来自 `group`
- 它的 `sub_type` 是 `normal`

而不是先把它压扁成一个类似 `napcat.message.group.normal` 的单一路径字符串。

建议统一 tag 组合：

- `napcat`
- `meta`
- `message`
- `message_sent`
- `request`
- `notice`
- `api_response`
- `private`
- `group`
- `friend`
- `normal`
- `connect`
- `heartbeat`
- `group_admin`
- `set`

例如：

- 生命周期连接事件：`("napcat", "meta", "lifecycle", "connect")`
- 心跳事件：`("napcat", "meta", "heartbeat")`
- 私聊好友消息：`("napcat", "message", "private", "friend")`
- 私聊群临时消息：`("napcat", "message", "private", "group")`
- 群普通消息：`("napcat", "message", "group", "normal")`
- 自己发出的群消息：`("napcat", "message_sent", "group", "normal")`
- 好友请求：`("napcat", "request", "friend")`
- 加群请求：`("napcat", "request", "group", "add")`
- 群管理员设置通知：`("napcat", "notice", "group_admin", "set")`
- API 响应：`("napcat", "api_response")`

这样做的原因：

- handler 可以按 tag 组合声明式订阅事件语义。
- extension 可以依赖 tag 组合约定，而不是依赖某个固定的路径字符串格式。
- 同一个事件可同时携带多维分类信息，更符合 `FastEvents` 的 tags DSL 思想。
- future transport 或语义扩展时，不需要重新发明一整套路径命名规则。

设计原则：

- 点号字符串只作为兼容输入或文档展示方式，不作为 fastnapcat 的主语义模型。
- 框架内部发布事件时，应优先使用 tag tuple / tag set 风格。
- 上层包装接口也应围绕 tag 条件组合，而不是围绕字符串前缀匹配设计。

### 3.5 扩展层 `ext`

这是 `fastnapcat` 的真正功能中心。

初期至少要有：

- `NapCatExtension`：app 侧主入口，统一暴露 bot 能力。
- `ApiExtension`：请求-响应式 API 调用能力。
- `MessageExtension`：消息发送、段构建、消息目标推导。
- `CommandExtension`：命令注册、匹配、参数解析、帮助信息。
- `SessionExtension`：围绕 `bot.prompt` / `bot.listen` 提供最小等待能力。

### 3.6 DI 上下文层 `context`

负责给 handler 注入高频能力对象。

建议拆成多个 typed context，而不是一个巨大的 session：

- `NapCatEventContext`：当前 NapCat 事件 + FastEvents runtime event
- `MessageContext`：消息事件的发送、回复、at、撤回等能力
- `CommandContext`：命令名、原始参数、解析结果、帮助输出
- `ApiContext`：发起 API 调用、等待响应
- `NoticeContext` / `RequestContext`：针对特定事件类的快捷能力

不过这里还需要补一层应用层约束：`FastEvents` 默认是函数式 DI，这非常适合框架扩展；但 `fastnapcat` 是应用层封装，所以可以在装饰阶段识别内部已知的常见类型，并自动改写成对应 dependency。

也就是说，对用户来说，应该允许直接这样写：

```python
@bot.command("/echo")
async def echo(ctx: CommandContext, message: MessageContext, args: EchoArgs):
    ...
```

内部实现时，再把这些已知类型替换成函数式 dependency 注入即可。

但这里必须明确边界：我们不会支持“所有内部已知类型”都自动注入，只会支持一小组稳定、公开、语义清晰的应用层类型。

也就是说，自动注入是一层受控白名单机制，而不是任意类型猜测机制。

---

## 4. 需要实现的核心对象

### 4.1 `FastNapCat`

提供用户最直接的使用入口，负责在库内组装 `FastEvents app + bus + runtime + extensions`。

建议形态：

```python
bot = FastNapCat(
    ws_url="ws://localhost:3001",
    access_token="...",
)

@bot.on.message()
async def handle_message(ctx: MessageContext):
    await ctx.reply("hello")

bot.run()
```

它内部应管理：

- `self.app: FastEvents`
- `self.bus`
- `self.runtime`
- `self.napcat: NapCatExtension`
- `self.commands: CommandExtension`

设计原则：

- 对用户暴露一个易用 facade。
- 对内部仍然坚持 `FastEvents` 边界，不把 facade 变成一团全能对象。
- `bot.on(...)` 应尽量透传 `FastEvents` 的原始注册接口。
- `bot.on.message(...)`、`bot.on.notice(...)`、`bot.on.request(...)` 则是 fastnapcat 的语义包装层。

建议接口草案：

```python
@bot.on(("napcat", "message", "group", "normal"))
async def raw_group(event: RuntimeEvent):
    ...


@bot.on.group()
async def handle_group(ctx: MessageContext):
    ...
```

### 4.2 `NapCatRuntime`

负责 websocket 通信与事件桥接。

建议职责：

- 连接 NapCat websocket
- 读取入站 json
- 按模型解析为 event / api response
- 发布为 `FastEvents` 标准事件
- 发送 API 请求并维护 echo -> future 的等待表
- 提供启动/关闭生命周期

关键点：

- API 响应本质上也是事件，应尽可能进入统一事件流。
- 同时为了易用性，需要在运行时内部维护 `echo` 等待，以支持 `await api.call(...)`。
- 这可以通过 extension 在上层封装，但 runtime 至少要提供最小的响应匹配能力。

### 4.3 `NapCatExtension`

主扩展，负责把 bot 能力挂到 app 上。

建议提供：

- `on(...)`：直接透传 `FastEvents app.on(...)`
- `on.message(...)` / `on.private(...)` / `on.group(...)` / `on.notice(...)` / `on.request(...)` / `on.meta(...)` 等语法糖
- `send_private()` / `send_group()`
- `call_api()`
- `listen_message()` / `wait_for()`

本质上这些能力仍应委托给 `app.on()`、`app.listen()`、`ApiExtension`、`SessionExtension`，而不是自己实现一套新 dispatcher。

这里还应强调：`on.message(...)` 不应简单翻译成某个点号路径字符串，而应翻译成一组 tags 条件。

其中 `on.message(...)` 建议支持以下筛选参数：

- `private: bool = True`
- `group: bool = True`
- `self_message: bool | None = None`
- `sub_type: str | None = None`
- `level: int = -1`
- `name: str | None = None`

默认语义建议：

- `level=-1`，把普通消息监听放在观察层。
- `private=True` 表示接收私聊消息。
- `group=True` 表示接收群聊消息。
- 默认 `private=True, group=True`，表示同时接收私聊和群聊消息。
- `private=False, group=True` 表示只接收群聊消息。
- `private=True, group=False` 表示只接收私聊消息。
- `private=False, group=False` 属于无意义配置，应直接报错或拒绝注册。
- `self_message=False` 默认忽略自己发出的 `message_sent` 事件，除非显式开启。

建议的内部翻译方式：

- `bot.on.message()` -> 订阅包含 `("napcat", "message")` 的事件
- `bot.on.message(group=True, private=True)` -> 订阅包含 `("napcat", "message")` 且接受群聊和私聊两个分支
- `bot.on.message(group=True, private=False)` -> 订阅包含 `("napcat", "message", "group")` 的事件
- `bot.on.message(group=False, private=True)` -> 订阅包含 `("napcat", "message", "private")` 的事件
- `bot.on.message(group=True, sub_type="normal")` -> 订阅包含 `("napcat", "message", "group", "normal")` 的事件
- `bot.on.message(self_message=True)` -> 从 `message` 扩展到同时接收 `message_sent` 体系

额外语法糖建议：

- `bot.on.private(...)` 等价于 `bot.on.message(private=True, group=False, ...)`
- `bot.on.group(...)` 等价于 `bot.on.message(private=False, group=True, ...)`

这样一方面保留统一入口 `on.message(...)`，另一方面也让两个最高频场景拥有更短的写法。

### 4.4 `ApiExtension`

提供 OneBot API 调用体验。

建议最小接口：

- `call(action: ApiRequestModel) -> ApiResponseModel`
- `send_private_message(...)`
- `send_group_message(...)`
- `delete_message(...)`
- `set_group_ban(...)`

实现思路：

- 为每个请求分配唯一 `echo`
- runtime 发送请求
- 监听包含 `("napcat", "api_response")` tags 的事件或直接等待 runtime future
- 返回强类型响应对象

### 4.5 `CommandExtension`

负责命令系统。

需要覆盖 `onebot-mq` 已有能力，并做成事件驱动版。

这里有一个重要方向调整：命令系统不应过度依赖“为每个命令单独注册一套匹配器”。更好的方式是在消息进入时先做一次轻量预解析，把首个 token 提取出来，再把命令语义放进 tags。

功能要求：

- 支持声明命令、别名、描述
- 限制只在私聊 / 群聊启用
- run level 支持，默认 `level=1`
- 支持显式 `args_model`
- 支持通过参数类型自动推断参数模型
- 支持 POSIX 风格参数解析
- 支持自动注入 `CommandContext`
- 支持帮助文案生成
- 支持消息预解析后自动产生 command tags

建议用法：

```python
@bot.command("/ban", aliases=["/mute"])
async def ban(ctx: CommandContext, args: BanArgs, message: MessageContext):
    await message.ban_user(args.duration)
```

这里的 `args_model` 不一定需要显式写出。

如果装饰器在分析函数签名时发现：

- 存在一个参数类型是 `BanArgs`
- 且它不是框架已知上下文类型
- 同时它满足命令参数模型约束

那么就可以自动把它视为当前命令的参数模型。

也就是说，应用层可以做下面这件事：

- 用户写 `args: EchoArgs`
- 框架在装饰阶段识别这个参数类型
- 自动推断这就是当前命令的 `args_model`
- 再在内部把它包装成对应的 dependency 注入

实现步骤：

1. 在消息进入系统时，对文本消息做一次轻量预解析
2. 对消息做 `split` / `shlex` 风格首 token 提取
3. 如果首 token 可识别为命令名，则把命令语义加入事件 tags
4. 命令扩展再基于这些 tags 做进一步参数解析和模型校验
5. 构造 `CommandContext` 注入 handler

推荐的 tag 语义：

- 原始消息：`("napcat", "message", ...)`
- 如果文本是 `aa bb cc`
- 则预解析出命令名 `aa`
- 并为事件额外附加一个不可分割的命令 tag，例如 `"command.aa"`

这里不要把命令 tag 再拆成多个 tag 片段。

也就是说，不建议使用 `("command", "aa")` 这种形式。

原因是：

- `command.aa` 在这里表示一个不可分割的语义单元
- 拆分后可能导致语义歧义、意外匹配或超出预期的订阅结果
- 命令名更适合作为一个原子 tag 附着在消息事件上

所以这里的原则应是：

- 消息分类使用组合 tags
- 命令名使用原子 tag，例如 `command.aa`

这样做的好处是：

- 降低命令注册压力，不需要每个命令都先挂一层独立的消息匹配逻辑
- 命令本质上变成“带有特定 command tags 的消息事件”
- 普通 `bot.on(...)` 也可以直接订阅命令语义，而不必总是通过 `bot.command(...)`

例如：

```python
@bot.on("command.aa", level=1)
async def handle_aa(message: MessageContext, args: MyArgs):
    ...
```

默认层级约定：

- `bot.on.message(...)` 默认 `level=-1`
- `bot.command(...)` 默认 `level=1`

这样分层的意义是：

- 普通 message handler 默认属于观察层或预处理层。
- command handler 作为显式业务处理层，落在正级别，更符合 `FastEvents` 的传播语义。
- 后续要叠加 fallback、兜底消息处理、AI 对话层时，也更容易继续分层。

### 4.6 `SessionExtension`

负责对话式等待能力。

建议首批能力：

- `bot.prompt(...)`
- `bot.listen(...)`

其中建议把 `bot.prompt` 和 `bot.listen` 提升为 facade 层的一等 API。

#### `bot.prompt(...)`

语义：

- 绑定当前对话上下文
- 默认使用当前消息事件里的 `user_id` 和 `group_id`
- 等待下一条匹配消息
- 收到后直接返回消息对象或 `MessageContext`

典型场景：

- 在一个 handler 中追问用户下一句话
- 在群聊里只继续等待当前用户的下一条回复

建议用法：

```python
@bot.on.group()
async def survey(message: MessageContext, bot: FastNapCat):
    await message.reply("请输入答案")
    next_message = await bot.prompt(timeout=30)
    await next_message.reply("收到")
```

这里的关键点是：`prompt()` 不需要用户手动再传 `user_id` / `group_id`，它应该默认继承当前对话上下文。

#### `bot.listen(...)`

语义：

- 由调用者手动提供监听键或过滤条件
- 返回一个异步迭代器
- 适合长时间监听某一类事件流，而不是只等待单条消息

建议参数方向：

- `id` 或 `key`
- `user_id`
- `group_id`
- `tags`
- `timeout`
- `predicate`

建议用法：

```python
async with bot.listen(id="room-123", group_id=123456) as stream:
    async for message in stream:
        ...
```

`prompt()` 可以视为 `listen()` 的单条消息快捷封装：

- `prompt()` 绑定当前上下文
- `listen()` 手动指定上下文并返回流

实现原则：

- 不做全局阻塞式 session manager。
- 用 `app.listen()` + matcher 过滤实现临时事件流。
- 会话本质仍然是“等待未来事件”，而不是维护一个独立状态机框架。

---

## 5. 需要迁移或重写的数据模型

### 5.1 必须迁移的模型

第一阶段建议直接迁移以下模型，因为它们是整个框架的协议地基。

#### 事件模型

- `HeartBeat`
- `LifeCycleEnable`
- `LifeCycleDisable`
- `LifeCycleConnect`
- `PrivateFriendMessage`
- `PrivateGroupMessage`
- `GroupMessage`
- `PrivateFriendMessageSelf`
- `GroupMessageSelf`
- `RequestFriend`
- `RequestGroupAdd`
- `RequestGroupInvite`
- 高频 `notice` 模型

#### 消息段模型

- `ReceiveText`
- `ReceiveAt`
- `ReceiveImage`
- `ReceiveReply`
- `TextSegment`
- `AtSegment`
- `ReplySegment`
- `ImageSegment`
- `FaceSegment`

#### API 请求模型

- 发送私聊消息
- 发送群消息
- 撤回消息
- 获取群成员信息
- 群禁言

### 5.2 不建议第一阶段全量照搬的部分

- 全量 notice / segment 覆盖可以分批迁移，不必第一版一次做完。
- CQ 码完整互转不是首个阻塞项，可放在第二阶段。
- 所有 API action 不必首批覆盖，优先高频消息和群管操作。

### 5.3 迁移方式建议

不要把 `py-napcat` 原文件原封不动塞进来，而应做一次结构整理：

- 命名统一到 `fastnapcat.models`
- 删除无关和明显重复的实现
- 修正已有数据模型里的小问题
- 补齐事件 union、response model、解析入口

目标不是“copy 一个 SDK 目录”，而是形成 `fastnapcat` 自己的协议模型层。

---

## 6. DI 设计

这是整个项目最关键的一层，因为 `FastEvents` 的价值就在于声明式 handler + 注入。

这里需要优先满足一个实际目标：高频操作必须短，handler 里不应该到处写又长又重的上下文调用。也就是说，DI 设计不能只追求“分层干净”，还要追求“写机器人代码时足够顺手”。

### 6.1 最小 DI 集合

第一阶段建议至少实现两层注入能力：

- 上下文对象：适合需要一整组能力时使用
- 高频语法糖：适合只拿单个高频值时使用
- 已知类型自动注入：适合应用层自然签名

建议 provider 集合：

- `napcat_event()` -> 当前 NapCat 事件对象
- `runtime_event()` -> 当前 `FastEvents.RuntimeEvent`
- `message_context()` -> `MessageContext`
- `command_context()` -> `CommandContext`
- `api_context()` -> `ApiContext`
- `bot_context()` -> `FastNapCat` 或 `NapCatExtension`
- `message_text()` -> 当前消息中的纯文本部分，取不到则返回空字符串
- `images()` -> 当前消息中的全部图片列表，取不到则返回空列表
- `arg()` -> 当前命令已校验的参数对象，由参数注解决定具体模型类型

推荐使用策略：

- 需要一整套消息能力时，注入 `MessageContext`
- 只想拿文字内容时，直接注入 `message_text()`
- 只想拿命令参数模型时，直接写 `args: MyArgs`
- 这样可以显著缩短高频 handler 的写法

例如：

```python
@bot.on.message()
async def echo(text: str = message_text()):
    ...


@bot.command("/ban")
async def ban(args: BanArgs, message: MessageContext):
    await message.ban_user(args.duration)
```

这里的关键是：应用层应允许已知类型直接注入，而不要求所有东西都显式写成 dependency 调用。

建议自动识别的已知类型至少包括：

- `FastNapCat`
- `MessageContext`
- `CommandContext`
- `ApiContext`
- `NoticeContext`
- `RequestContext`
- 命令参数模型类型

但不建议继续无限扩张。自动注入白名单应满足三个条件：

- 类型是公开 API 的一部分
- 语义稳定，用户容易理解来源
- 注入行为不会和普通业务类型产生歧义

实现方式可以很简单：

- 在 `@bot.on...` / `@bot.command(...)` 装饰阶段读取函数签名
- 识别这些已知类型
- 自动替换成内部对应的函数式 dependency

这样用户看到的是自然签名，底层运行的仍然是 `FastEvents` 原生 DI 机制。

### 6.2 `MessageContext`

应提供：

- `event`
- `user_id`
- `group_id`
- `message_id`
- `text`
- `segments`
- `is_private`
- `is_group`
- `send()`
- `reply()`
- `at_sender()`
- `recall()`
- `ban_user()`

同时消息相关 API 应尽量返回发送结果，而不是只返回 `None`。

建议：

- `await message.send(...)` 至少返回 `message_id`
- `await message.reply(...)` 至少返回 `message_id`
- 如果底层响应足够完整，可以返回 `SentMessage` 之类的轻量结果对象

建议结果对象：

```python
class SentMessage(BaseModel):
    message_id: int
    raw_response: ApiResponse | None = None
```

这样用户可以自然地写：

```python
sent = await message.reply("hello")
print(sent.message_id)
```

这基本对应 `onebot-mq` 的 `MessageSession` 能力，但改成细粒度 typed context，而不是框架内部万能 session。

如果只做第一阶段最小实现，也至少要保证：

- `send()` / `reply()` 返回 `int` 型 `message_id`
- 而不是 fire-and-forget

### 6.3 `CommandContext`

应提供：

- `name`
- `raw_text`
- `argv`
- `position_args`
- `flags`
- `validated_args`
- `has_validation_error`
- `validation_error`
- `help_text()`

但这里不应该要求每次都显式写 `ctx.validated_args`，否则高频命令处理会显得很笨重。

因此建议把命令参数注入拆成两种风格：

- `CommandContext`：完整命令上下文
- `args()`：高频参数糖

同时支持 handler 直接拿 Pydantic 参数模型：

```python
@bot.command("/echo", args_model=EchoArgs)
async def echo(ctx: CommandContext, args: EchoArgs, message: MessageContext):
    ...
```

建议进一步明确 `args()` 的语义：

- `args()` 只能在命令 handler 中使用
- 如果当前 handler 不是通过 `bot.command(...)` 注册，应直接报错
- 如果是命令 handler，但参数模型没有配置，也应报错
- 如果是命令 handler，理论上前一阶段已经完成校验，因此正常情况下不会再次报错

推荐用法：

```python
@bot.command("/echo")
async def echo(args: EchoArgs, text_value: str = message_text()):
    ...
```

这比反复写 `ctx.validated_args` 更符合高频使用习惯。

### 6.4 `ApiContext`

应提供：

- `call()`
- `send_private_message()`
- `send_group_message()`
- `delete_message()`
- `set_group_ban()`

它本质是 `ApiExtension` 的 handler-side 入口。

如果某个 handler 只需要发一条消息或撤回消息，也不应该被迫先拿 `ApiContext` 再调长链路 API，因此高频消息操作仍应优先通过 `MessageContext` 暴露。

### 6.5 高频语法糖设计

为了降低 handler 编写成本，建议把以下依赖形式作为一等公民写进框架设计，而不是只保留 context 风格。

#### `message_text()`

语义：

- 从当前消息中提取纯文本部分
- 如果当前事件不是消息事件，返回空字符串
- 如果消息里没有文本段，也返回空字符串

推荐返回类型：`str`

示例：

```python
@bot.on.message()
async def log_text(value: str = message_text()):
    if value:
        print(value)
```

#### `images()`

语义：

- 返回消息中的全部图片
- 没有图片则返回空列表

推荐返回类型：`list[ImageInput]`

#### `arg()`

语义：

- 直接返回当前命令对应的已校验参数对象
- 非命令 handler 中使用时直接抛出错误
- 命令未配置 `args_model` 时直接抛出错误
- 命令 handler 中正常情况下不再重复做用户侧校验逻辑

这里由参数注解决定返回类型，而不是在 `arg(...)` 调用里再次重复写模型。

进一步地，在应用层甚至可以允许更短的写法：

```python
@bot.command("/ban")
async def ban(args: BanArgs):
    ...
```

也就是：

- 如果签名里出现一个可识别的命令参数模型类型
- 那么 `arg()` 和显式 `args_model=` 都可以省略
- 框架在装饰阶段自动完成推断和包装

#### `message_id()` / `user_id()` / `group_id()`

这类简单标量也可以作为后续可选语法糖保留，以便继续压缩高频 handler 代码。

### 6.6 推荐交互风格

更推荐的 handler 写法应该像这样：

```python
@bot.on.group()
async def greet(text_value: str = message_text(), message: MessageContext):
    if text_value == "ping":
        sent = await message.reply("pong")
        print(sent.message_id)
```

或者在命令里进一步压缩成：

```python
@bot.command("/ban")
async def ban(args: BanArgs, message: MessageContext):
    await message.ban_user(args.duration)
```

这比“所有事情都先拿 `ctx` 再长链调用”更适合机器人开发里的高频写法。

---

## 7. 命令系统需求与设计

### 7.1 需要覆盖的功能

从 `onebot-mq` 迁移时，命令系统至少要支持：

- 命令名与别名
- 私聊 / 群聊启用开关
- run level
- 参数模型校验
- POSIX 风格参数
- 帮助文本
- 命令未命中时继续传播
- 命中后可选择消费或继续传播

### 7.2 参数解析规则

建议保留 `onebot-mq` 的 `shlex` 路线，因为它在聊天命令里足够实用。

支持：

- `--text hello`
- `--text "hello world"`
- `-t hello`
- `--dry-run`
- 位置参数

输出结构：

- `flags: dict[str, Any]`
- `position_args: list[str]`

### 7.3 命令匹配方式

建议第一阶段支持显式命令前缀，不做过度智能推断。

例如：

- `/help`
- `/ban 123 --duration 60`
- `!ping`

prefix 设计：

- 全局默认 prefix 列表
- 命令级可覆盖
- 群聊与私聊可有不同默认策略

### 7.4 事件驱动式实现

命令系统不要单独拥有一套注册中心和执行引擎，而应建立在事件系统之上：

- 消息进入包含 `("napcat", "message")` tags 的事件流
- 命令扩展是这些事件的订阅者
- 命中后构造 `CommandContext`
- 再调用用户 handler

这样命令也只是“消息事件上的高层协议”，符合 `FastEvents` 的架构哲学。

---

## 8. 用户体验目标

需要提供接近 `onebot-mq` 的开发体验，但内部更干净，同时 API 结构尽量与 `FastEvents` 保持一致。

### 8.1 目标用法

```python
from fastnapcat import FastNapCat
from fastnapcat.command import CommandArgs


bot = FastNapCat(ws_url="ws://localhost:3001", access_token="token")


@bot.on.group()
async def group_echo(message):
    if "hello" in message.text:
        await message.reply("world")


@bot.command("/echo")
async def echo(cmd, message):
    await message.reply(cmd.join_args())


bot.run()
```

### 8.2 更底层的组合式用法

同时也应保留 `FastEvents` 风格：

```python
app = FastEvents()
napcat = NapCatExtension(app, ws_url="...")
commands = CommandExtension(app, napcat=napcat)


@napcat.on.private(level=-1)
async def watch_private(ctx: MessageContext):
    ...
```

这样既有高级 facade，也有低级组合能力。

---

## 9. 模块划分建议

建议目录结构如下：

```text
fastnapcat/
  __init__.py
  app.py
  runtime/
    __init__.py
    ws.py
    protocol.py
  models/
    __init__.py
    base.py
    events.py
    segments.py
    api.py
  message/
    __init__.py
    builder.py
    convert.py
  api/
    __init__.py
    builder.py
    requests.py
    responses.py
  adapter/
    __init__.py
    publish.py
    tags.py
  context/
    __init__.py
    event.py
    message.py
    command.py
    api.py
    session.py
  ext/
    __init__.py
    napcat.py
    api.py
    command.py
    session.py
  di/
    __init__.py
    providers.py
  command/
    __init__.py
    parser.py
    models.py
    registry.py
```

如果初版想更克制，也可以把 `adapter` / `di` / `context` 收缩一部分，但概念边界最好先保留。

---

## 10. 分阶段落地计划

### Phase 1: 协议建模落地

目标：先让项目拥有 NapCat 的类型基础。

任务：

- 从 `py-napcat` 整理并迁移核心事件模型
- 整理消息段模型和 message builder
- 整理核心 API request builder
- 定义统一 response model

完成标志：

- 能把原始 json 解析为强类型事件
- 能构造发送消息、撤回等高频 API 请求

### Phase 2: 运行时接入

目标：建立 websocket runtime，并让 NapCat 事件进入 `FastEvents`。

任务：

- 实现 websocket 客户端管理
- 实现入站 json -> typed event
- 实现 typed event -> `app.publish(...)`
- 实现 API 响应等待机制

完成标志：

- NapCat 的真实事件可以被 `FastEvents` handler 订阅到

### Phase 3: facade 与基础 DI

目标：提供基础 bot 开发体验。

任务：

- 实现 `FastNapCat`
- 实现 `NapCatExtension`
- 实现 `MessageContext`
- 实现 `ApiContext`
- 提供 `bot.on()` 与 `bot.on.message(...)`

完成标志：

- 用户能写出最小可用 bot，并完成收消息和回复消息

### Phase 4: 命令系统

目标：覆盖 `onebot-mq` 的命令体验。

任务：

- 实现参数解析器
- 实现 `CommandExtension`
- 实现 `CommandContext`
- 支持显式 `args_model`
- 支持通过参数类型自动推断参数模型

完成标志：

- 命令注册、别名、flag 参数、帮助文案可用

### Phase 5: 会话与等待能力

目标：构建更适合 bot 的事件驱动对话能力。

任务：

- 实现 `SessionExtension`
- 支持 `bot.prompt`
- 支持 `bot.listen`
- 实现 matcher / predicate 过滤

完成标志：

- 可编写多轮对话逻辑而不引入额外的全局会话框架

---

## 11. 风险与设计红线

### 11.1 不要把 `FastNapCat` 做成巨石对象

`FastNapCat` 应该是 facade，不应该自己持有所有业务逻辑实现。

### 11.2 不要把 NapCat 特性直接塞进 `FastEvents` core

例如：

- `reply()` 不应该加进通用 `EventContext`
- `group_id` / `user_id` 不应该让 core 感知
- 命令系统不应该要求 dispatcher 特判

### 11.3 不要继续沿用 `onebot-mq` 的“ws session 即框架”设计

ws session 应该只是 transport/runtime 的一部分，而不是开发模型本身。

### 11.4 不要让 command/session 成为另一个 mini-framework

命令和会话都应表达为“事件之上的高层协议”。

### 11.5 不要第一版就追求全量 OneBot 覆盖

先覆盖高频路径：

- 消息接收
- 消息发送/回复
- 命令解析
- API 请求/响应
- 等待下一条消息

---

## 12. 建议的首批交付范围

为了尽快得到可运行版本，第一批建议只做以下功能：

- `FastNapCat` facade
- websocket runtime
- 核心事件模型
- 核心消息段模型 + builder
- 发送私聊 / 群聊 / 回复 / 撤回
- `MessageContext`
- `ApiContext`
- `bot.on()` / `bot.on.message(...)`
- `command()` + 参数类型推断
- `bot.prompt()` / `bot.listen()`

有了这一批后，框架就已经能覆盖大多数聊天机器人基础场景。

---

## 13. 下一步建议

建议按下面顺序开始真正编码：

1. 先整理并迁移 `py-napcat` 的最小协议模型集合
2. 再实现 `NapCatRuntime`，打通 websocket 入站 -> `FastEvents`
3. 再实现 `FastNapCat` facade 和 `MessageContext`
4. 然后补 `ApiExtension`
5. 再落命令系统
6. 最后做会话等待能力

这样可以确保每一步都能跑起来，而不是一开始就堆太多上层抽象。
