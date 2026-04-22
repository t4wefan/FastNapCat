# fastnapcat DI 接口规范

## 1. 文档目标

本文档定义 `fastnapcat` 新一版 DI 的**公开接口**，只回答四个问题：

- 允许注入哪些**类型**
- 允许注入哪些**函数**
- 每个注入项的**返回类型**是什么
- 每个类型的注入是通过什么 **`_provider()`** 方法完成的

本文档不描述旧实现兼容层，也不描述 `fastnapcat/di/rewrite.py` 的保留策略。本文档面向的是“删了重来”后的目标接口。


## 2. 总体原则

新的 DI 设计完全建立在 [`FastEvents` 的原生依赖解析规则](refrence/FastEvents/fastevents/subscribers.py:181) 之上。

也就是说：

- handler 参数解析由 [`_DependencyResolver.build_kwargs()`](refrence/FastEvents/fastevents/subscribers.py:185) 负责
- 类型注入依赖注解类型自己的 [`_provider()`](refrence/FastEvents/fastevents/subscribers.py:158)
- 函数注入依赖 [`@dependency`](refrence/FastEvents/fastevents/subscribers.py:63)
- provider 本身也可以继续依赖其他可注入类型或依赖函数，见 [`resolve_dependency()`](refrence/FastEvents/fastevents/subscribers.py:239)

因此，`fastnapcat` 不再维护一套并行的“参数二次分发器”。


## 3. 类型注入与函数注入的边界

### 3.1 类型注入

以下对象必须设计成**类型注入**：

- 有明确领域语义的对象
- 本身拥有方法、状态或行为的对象
- 可以作为其他 provider 的依赖输入的对象
- 用户在 handler 中会频繁作为主参数使用的对象

类型注入统一通过该类型上的 [`_provider()`](refrence/FastEvents/fastevents/subscribers.py:158) 完成。


### 3.2 函数注入

以下对象才允许设计成**函数注入**：

- 从上下文对象中派生出的轻量值
- 纯快捷访问能力
- 没有必要单独定义成领域类型的值视图

函数注入统一使用 [`@dependency`](refrence/FastEvents/fastevents/subscribers.py:63) 定义。


### 3.3 边界判定规则

- 完整上下文对象：必须是类型注入
- 服务对象：必须是类型注入
- 命令参数模型：必须是类型注入
- 事件模型：优先直接使用 payload 模型类型注入
- 单个派生值：可以是函数注入
- 如果某能力同时可设计为类型和函数，则**类型为主，函数只能是语法糖**


## 4. 注入接口总览

新的公开注入接口分为两类：

- **类型注入主接口**：面向完整对象
- **函数注入快捷接口**：面向派生值


## 5. 类型注入接口

### 5.1 框架基础类型

#### [`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)

- 注入方式：框架原生支持
- 返回类型：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- provider：无，属于 `FastEvents` 内建注入
- 用途：访问当前事件的 `tags`、`meta`、`payload`、`ctx`

示例：

```python
@bot.on("napcat.message")
async def handle(event: RuntimeEvent) -> None:
    print(event.tags)
```


#### [`EventContext`](refrence/FastEvents/fastevents/events.py:129)

- 注入方式：类型注入
- 返回类型：[`EventContext`](refrence/FastEvents/fastevents/events.py:129)
- provider：[`EventContext._provider()`](refrence/FastEvents/fastevents/events.py:153)
- 用途：在当前运行时上下文中继续发布事件

示例：

```python
@bot.on("napcat.notice")
async def handle(ctx: EventContext) -> None:
    await ctx.publish(tags="audit.notice", payload={"ok": True})
```


### 5.2 NapCat payload 模型注入

`FastEvents` 原生支持将 payload 直接校验为 `Pydantic BaseModel`，见 [`_resolve_payload()`](refrence/FastEvents/fastevents/subscribers.py:257)。

因此，NapCat typed payload 直接属于可注入类型。

#### 可直接注入的 payload 模型

包括但不限于：

- [`GroupMessage`](fastnapcat/models/events.py)
- [`PrivateFriendMessage`](fastnapcat/models/events.py)
- [`PrivateGroupMessage`](fastnapcat/models/events.py)
- 其他 notice / request / meta 事件模型，位于 [`fastnapcat/models/events.py`](fastnapcat/models/events.py)

- 注入方式：payload 模型注解
- 返回类型：参数标注的具体事件模型类型
- provider：无，走 `FastEvents` 的 payload model validate 路径
- 用途：直接拿到强类型事件模型

示例：

```python
@bot.on.group()
async def handle(data: GroupMessage) -> None:
    print(data.group_id)
```


### 5.3 `fastnapcat` 上下文类型

#### [`NapCatEventContext`](fastnapcat/context/event.py:14)

- 注入方式：类型注入
- 返回类型：[`NapCatEventContext`](fastnapcat/context/event.py:14)
- provider：[`NapCatEventContext._provider()`](fastnapcat/context/event.py:18)
- provider 返回：`Dependency[NapCatEventContext]`
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 用途：统一访问 NapCat 事件模型和当前运行时事件

provider 形式：

```python
@staticmethod
def _provider():
    @dependency
    def _event_context(event: RuntimeEvent) -> NapCatEventContext:
        ...
    return _event_context
```


#### [`MessageContext`](fastnapcat/context/message.py:45)

- 注入方式：类型注入
- 返回类型：[`MessageContext`](fastnapcat/context/message.py:45)
- provider：[`MessageContext._provider()`](fastnapcat/context/message.py:55)
- provider 返回：`Dependency[MessageContext]`
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 语义要求：
  - 仅在 message payload 上可注入
  - 负责提供 `send()`、`reply()`、`at_sender()` 等消息交互能力

建议使用方式：

```python
@bot.on.private()
async def handle(ctx: MessageContext) -> None:
    await ctx.reply("ok")
```


#### [`CommandContext`](fastnapcat/context/command.py:16)

- 注入方式：类型注入
- 返回类型：[`CommandContext`](fastnapcat/context/command.py:16)
- provider：[`CommandContext._provider()`](fastnapcat/context/command.py:36)
- provider 返回：`Dependency[CommandContext]`
- 依赖输入：
  - [`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
  - 命令解析逻辑，如 [`CommandArgs._parse_command_from_event()`](fastnapcat/command/models.py:33)
- 语义要求：
  - 仅在可解析为命令的 message payload 上可注入
  - 提供 `name`、`raw_text`、`argv`、`flags`、`position_args`

建议使用方式：

```python
@bot.command("/echo")
async def handle(cmd: CommandContext) -> None:
    print(cmd.flags)
```


#### [`NoticeContext`](fastnapcat/context/event.py:45)

- 注入方式：类型注入
- 返回类型：[`NoticeContext`](fastnapcat/context/event.py:45)
- provider：[`NoticeContext._provider()`](fastnapcat/context/event.py:49)
- provider 返回：`Dependency[NoticeContext]`
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 语义要求：仅在 notice 事件上可注入


#### [`RequestContext`](fastnapcat/context/event.py:62)

- 注入方式：类型注入
- 返回类型：[`RequestContext`](fastnapcat/context/event.py:62)
- provider：[`RequestContext._provider()`](fastnapcat/context/event.py:66)
- provider 返回：`Dependency[RequestContext]`
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 语义要求：仅在 request 事件上可注入


#### [`MetaContext`](fastnapcat/context/event.py:28)

- 注入方式：类型注入
- 返回类型：[`MetaContext`](fastnapcat/context/event.py:28)
- provider：[`MetaContext._provider()`](fastnapcat/context/event.py:32)
- provider 返回：`Dependency[MetaContext]`
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 语义要求：仅在 meta 事件上可注入


### 5.4 命令参数类型

#### [`CommandArgs`](fastnapcat/command/models.py:23) 及其子类

- 注入方式：类型注入
- 返回类型：具体的 [`CommandArgs`](fastnapcat/command/models.py:23) 子类实例
- provider：每个子类自动生成的 [`_provider`](fastnapcat/command/models.py:30)
- provider 工厂：[`CommandArgs._make_provider()`](fastnapcat/command/models.py:44)
- provider 返回：`Dependency[具体 CommandArgs 子类]`
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 语义要求：
  - 仅在命令消息上可注入
  - 自动填充 [`parsed_command`](fastnapcat/command/models.py:26)
  - 自动将 flags / position args 映射到业务字段

示例：

```python
class EchoArgs(CommandArgs):
    content: str


@bot.command("/echo")
async def handle(args: EchoArgs) -> None:
    print(args.content)
```


### 5.5 服务类型

#### `APIExtension`

- 注入方式：类型注入
- 返回类型：`APIExtension`
- provider：**新实现中需要新增 `APIExtension._provider()`**
- provider 返回：`Dependency[APIExtension]`
- 依赖输入：运行时绑定的 API 服务实例
- 用途：直接调用 NapCat / OneBot API

建议 provider 形式：

```python
@staticmethod
def _provider():
    @dependency
    def _api(...) -> APIExtension:
        ...
    return _api
```


#### [`LoggerProxy`](fastnapcat/di/providers.py:101)

- 注入方式：类型注入
- 返回类型：[`LoggerProxy`](fastnapcat/di/providers.py:101)
- provider：**新实现中建议为 `LoggerProxy` 增加 `_provider()`**
- provider 返回：`Dependency[LoggerProxy]`
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 用途：向 outbound log 事件流发送日志意图

设计要求：

- `LoggerProxy` 应成为正式类型注入对象
- [`logger()`](docs/fastnapcat-di-interface-spec.md) 只是它的快捷函数入口，不再是唯一入口


## 6. 函数注入接口

函数注入只保留“派生值快捷访问”。

### 6.1 [`message_text()`](fastnapcat/di/providers.py:36)

- 注入方式：函数注入
- 返回类型：`str`
- 定义位置：[`message_text()`](fastnapcat/di/providers.py:36)
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 语义：
  - 若当前事件是消息事件，返回 `raw_message`
  - 若不是消息事件，返回空字符串或在重构后按统一策略抛出注入错误

建议使用方式：

```python
@bot.on.group()
async def handle(text: str = message_text()) -> None:
    print(text)
```


### 6.2 [`images()`](fastnapcat/di/providers.py:45)

- 注入方式：函数注入
- 返回类型：[`ReceiveImages`](fastnapcat/models/segments.py:82)
- 定义位置：[`images()`](fastnapcat/di/providers.py:45)
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 语义：提取当前消息中的图片集合

建议使用方式：

```python
@bot.on.private()
async def handle(pics = images()) -> None:
    if pics:
        first = pics[0]
        await first.download()
```
```


### 6.3 [`logger()`](fastnapcat/di/providers.py:130)

- 注入方式：函数注入
- 返回类型：[`LoggerProxy`](fastnapcat/di/providers.py:101)
- 定义位置：[`logger()`](fastnapcat/di/providers.py:130)
- 依赖输入：[`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- 语义：返回当前事件绑定的日志代理

建议定位：

- 保留为 `LoggerProxy` 的快捷入口
- 但主推荐写法应逐步迁移到 `log: LoggerProxy`

示例：

```python
@bot.on.private()
async def handle(log = logger()) -> None:
    await log.info("received")
```


## 7. 明确不再推荐的函数注入

以下函数不建议继续作为新 DI 规范的公开主接口。

### [`arg()`](fastnapcat/di/providers.py:77)

- 现状返回类型：[`CommandArgs`](fastnapcat/command/models.py:23)
- 不推荐原因：[`CommandArgs`](fastnapcat/command/models.py:23) 子类本身就是正式类型注入路径，`arg()` 没有独立语义价值


### [`command_context()`](fastnapcat/di/providers.py:93)

- 现状返回类型：[`CommandContext`](fastnapcat/context/command.py:16)
- 不推荐原因：[`CommandContext`](fastnapcat/context/command.py:16) 本身就是完整上下文对象，应走类型注入，而不是再暴露平行函数入口


### [`napcat_event()`](fastnapcat/di/providers.py:87)

- 现状返回类型：当前 payload 原值
- 不推荐原因：
  - 若要拿完整事件，应注入 [`NapCatEventContext`](fastnapcat/context/event.py:14)
  - 若要拿具体 payload，应直接注解具体事件模型类型


### `message_event()`

- 现状返回类型：消息事件 payload
- 不推荐原因：应由 payload 模型类型注入替代


## 8. provider 方法规范

所有类型注入对象都应遵守 `FastEvents` 的 provider 约定，见 [`_get_annotation_provider()`](refrence/FastEvents/fastevents/subscribers.py:158)。

### 8.1 provider 形态

每个可自动类型注入的类都必须提供：

```python
@staticmethod
def _provider():
    @dependency
    def provider(...) -> SelfType:
        ...
    return provider
```
```

### 8.2 强制要求

- `_provider` 必须是 `staticmethod`
- `_provider()` 不能接受位置参数
- `_provider()` 必须返回 `Dependency`
- provider callback 的依赖输入必须同样满足 `FastEvents` 可注入规则

这些要求都来自 [`_get_annotation_provider()`](refrence/FastEvents/fastevents/subscribers.py:161) 到 [`_get_annotation_provider()`](refrence/FastEvents/fastevents/subscribers.py:177) 的校验逻辑。


## 9. 推荐写法

### 9.1 消息处理

```python
@bot.on.group()
async def handle(
    data: GroupMessage,
    ctx: MessageContext,
    log: LoggerProxy,
    text: str = message_text(),
) -> None:
    await log.info(text)
    await ctx.reply("ok")
```
```

### 9.2 命令处理

```python
class EchoArgs(CommandArgs):
    content: str


@bot.command("/echo")
async def echo(
    ctx: MessageContext,
    cmd: CommandContext,
    args: EchoArgs,
    log: LoggerProxy,
) -> None:
    await log.info(args.content)
    await ctx.send(args.content)
```
```

### 9.3 notice 处理

```python
@bot.on.notice()
async def handle(ctx: NoticeContext, log: LoggerProxy) -> None:
    await log.info(ctx.event.notice_type)
```
```


## 10. 最终接口结论

新的 `fastnapcat` DI 接口应明确收敛为：

### 类型注入主接口

- [`RuntimeEvent`](refrence/FastEvents/fastevents/events.py:164)
- [`EventContext`](refrence/FastEvents/fastevents/events.py:129)
- NapCat payload models，位于 [`fastnapcat/models/events.py`](fastnapcat/models/events.py)
- [`NapCatEventContext`](fastnapcat/context/event.py:14)
- [`MessageContext`](fastnapcat/context/message.py:45)
- [`CommandContext`](fastnapcat/context/command.py:16)
- [`NoticeContext`](fastnapcat/context/event.py:45)
- [`RequestContext`](fastnapcat/context/event.py:62)
- [`MetaContext`](fastnapcat/context/event.py:28)
- [`CommandArgs`](fastnapcat/command/models.py:23) 子类
- `APIExtension`
- [`LoggerProxy`](fastnapcat/di/providers.py:101)

### 函数注入快捷接口

- [`message_text()`](fastnapcat/di/providers.py:36) -> `str`
- [`images()`](fastnapcat/di/providers.py:45) -> [`ReceiveImages`](fastnapcat/models/segments.py:82)
- [`logger()`](fastnapcat/di/providers.py:130) -> [`LoggerProxy`](fastnapcat/di/providers.py:101)

### 不再推荐作为公开主接口

- [`arg()`](fastnapcat/di/providers.py:77)
- [`command_context()`](fastnapcat/di/providers.py:93)
- [`napcat_event()`](fastnapcat/di/providers.py:87)
- `message_event()`

这就是新 DI 的最终边界：**完整对象走类型注入，派生快捷值走函数注入。**
