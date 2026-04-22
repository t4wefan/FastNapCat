# fastnapcat 重写方案

## 1. 背景

当前 `fastnapcat` 已经有一批可复用的协议模型与工具代码，但运行时、DI、facade 的边界没有立稳，导致几个核心问题同时存在：

- websocket 连接、事件桥接、API 调用、outbound 分发混在一起
- 装饰器层、DI 层、runtime 层之间依赖方向混乱
- 一部分接口在语义上模仿 bot 框架，但底层没有真正贴合 `fastevents`
- `ext` 的职责被说重了，而 `fastevents` 的 extension 实际只是 app-bound 能力组合，不提供生命周期保证

这次重写的目标不是修补现有实现，而是基于既有协议层代码，重新建立一套更克制、更事件驱动、并且严格遵守 `fastevents` 边界的骨架。


## 2. 设计目标

重写后需要满足下面几个目标：

- 以 `fastevents` 作为唯一事件内核，不重复实现 dispatcher、bus、dependency resolver
- 以 NapCat / OneBot 数据模型作为协议核心，保留强类型与 Pydantic 校验能力
- adapter 负责协议到事件语义的投影，而不是让 facade 或 runtime 到处理解原始 payload
- 通过 dependency 函数和受控自动注入，提供符合 `fastevents` 风格的 DI 体验
- facade 只做 app 能力组合、语法糖和生命周期编排，不伪装成插件系统
- 上层 API 尽量克制，避免把框架重新做成 callback + mutable session 的传统 bot 结构


## 3. 来自 fastevents 的约束

重写必须遵守以下边界：

- `publish()` 只保证事件进入 bus，不保证事件已处理完成
- 拥有 lifecycle 的是 bus 和宿主对象，不是 extension
- `app.ex` 只是 app-bound mount namespace；如果对象实现 `bind_app()`，会在挂载时调用一次，但不会获得启动、关闭、依赖排序等保证
- `fastevents` 已经提供 handler 参数解析和 `dependency()` 机制，fastnapcat 不应再重写一套并行注入系统
- richer capability 应通过 typed context 和 dependency 暴露，而不是不断膨胀通用 context

因此，`fastnapcat` 的宿主应该是 `FastNapCat`，而不是 `app.ex`。`FastNapCat` 负责组装 app、bus、transport、bridge 和 facade helper；facade helper 本身不拥有后台任务，也不负责 start/stop。


## 4. 总体架构

### 4.1 协议层

负责 NapCat / OneBot 的纯模型与构造工具。

包含：

- `fastnapcat/models/`
- `fastnapcat/api/`
- `fastnapcat/message/`

这一层不依赖 `fastevents`。


### 4.2 适配层

负责把 NapCat 协议数据投影为框架内部事件语义。

包含：

- `adapter/inbound.py`：原始 payload 解码为 `NapCatEvent | APIResponse`
- `adapter/tags.py`：typed model 投影为 tags
- `adapter/command.py`：从 message event 提取命令投影

这一层理解协议语义，但不负责连接管理和生命周期。


### 4.3 运行时层

负责 websocket IO 和事件桥接。

包含：

- `runtime/transport.py`：连接、重连、收发文本、ping/pong、echo future
- `runtime/bridge.py`：把 transport 收到的数据发布给 app；把高层 outbound 请求交给 transport

运行时层不负责 facade 注册语法，不负责 DI 装饰。


### 4.4 上下文与 DI 层

负责给 handler 暴露稳定的应用层能力。

包含：

- `context/event.py`
- `context/message.py`
- `context/command.py`
- `context/api.py`
- `di/providers.py`
- `di/registry.py`
- `di/rewrite.py`

这里的关键原则是：

- 公开一组受控、稳定、语义清晰的注入类型
- 自动注入只是“公开类型 -> 对应 dependency”的装饰阶段改写
- 真实解析仍交给 `fastevents`


### 4.5 Facade 层

负责用户入口和 app-bound helper。

包含：

- `facade/on.py`
- `facade/command.py`
- `facade/session.py`
- `facade/api.py`
- `app.py`

其中：

- facade helper 只是能力组合，不拥有 lifecycle
- `FastNapCat` 是唯一 lifecycle owner 和 composition root


## 5. 模块边界与依赖方向

推荐依赖方向如下：

- `models` 不依赖框架其他层
- `api` / `message` 依赖 `models`
- `adapter` 依赖 `models`、`api`
- `runtime` 依赖 `adapter`、`models`、`api`
- `context` 依赖 `models` 和稳定 runtime 抽象
- `di` 依赖 `context`、`models`、稳定 runtime 抽象、`fastevents`
- `facade` 依赖 `di`、稳定 runtime 抽象、`fastevents`
- `app` 负责最终组装所有对象

必须禁止的依赖：

- `di` 反向 import `FastNapCat`
- `runtime` 依赖 facade
- `models` 依赖 `fastevents`
- facade 假设某个 extension 有独立生命周期


## 6. 核心对象设计

### 6.1 FastNapCat

`FastNapCat` 是唯一宿主对象，负责：

- 创建 `FastEvents` app
- 创建 bus
- 创建 transport
- 创建 runtime bridge
- 创建 API client 和 facade helper
- 编排启动与关闭顺序

建议持有：

- `self.app`
- `self.bus`
- `self.transport`
- `self.bridge`
- `self.api`
- `self.on`
- `self.commands`
- `self.session`


### 6.2 NapCatTransport

职责：

- 管理 websocket 连接与重连
- 发送文本包
- 接收文本包
- 维护 `echo -> Future` 等待表
- 维护最小连接状态

不负责：

- handler 注册
- tags 生成
- MessageContext 注入
- facade 生命周期


### 6.3 RuntimeBridge

职责：

- 消费 transport 收到的原始文本
- 调用 adapter 完成 decode / tags / command projection
- 把结果发布到 `FastEvents`
- 接收 API / message / log 等 outbound 请求并调用 transport

设计重点：

- bridge 是 transport 和 app 之间的桥
- bridge 自己不提供用户 facade


### 6.4 InboundAdapter

建议拆成三个明确步骤：

- `decode_payload(payload)`
- `build_tags(model)`
- `build_projections(model)`

其中 command 不应是独立 transport 事件，而应是 message event 的投影信息。


### 6.5 InjectionRegistry / FacadeBinder

`InjectionRegistry` 负责定义一组允许自动注入的公开类型，例如：

- `NapCatEventContext`
- `MessageContext`
- `CommandContext`
- `APIClient`

`FacadeBinder` 负责在装饰阶段，把这些公开类型转换为 `dependency()` 请求。

这一步只做轻量改写，不重做运行时注入器。


## 7. 事件与 outbound 策略

### 7.1 Inbound

建议的 inbound 流程：

`ws text -> decode -> typed model -> tags/projections -> app.publish(...)`

其中：

- API 响应也进入统一事件流
- message event 附带 command projection
- tags 是内部主语义，不依赖单一路径字符串


### 7.2 Outbound

建议采用“命令式发送 + 事件式观测”模型：

- `ctx.send()` / `ctx.reply()` / `api.call()` 直接通过 transport 执行
- 同时发布 outbound intent 事件，供日志、审计、调试、旁路观察使用

不建议采用“真正发送依赖某个订阅器消费 outbound 事件”的主模型，因为这会让基础发送路径过于间接，也会给生命周期和错误处理带来额外复杂度。


## 8. DI 设计

第一版建议支持以下注入能力：

- `RuntimeEvent`
- NapCat typed payload，如 `GroupMessage`
- `NapCatEventContext`
- `MessageContext`
- `CommandContext`
- `APIClient`
- 工具依赖函数：`text()`、`images()`、`segments()`、`argv()`、`flags()`

设计原则：

- 自动注入是白名单机制，不做任意类型猜测
- 复杂能力优先封装到 typed context 中
- dependency 函数只能依赖当前 event scope 和稳定 service 引用
- 不允许依赖某个 facade 或 extension 的“已启动内部状态”


## 9. Facade 设计

Facade 只做用户体验，不做后台任务管理。

建议提供：

- `bot.on(...)`
- `bot.on.message()` / `bot.on.private()` / `bot.on.group()` / `bot.on.notice()` / `bot.on.request()`
- `bot.command()`
- `bot.listen()` / `bot.prompt()`
- `bot.api`

其中：

- `bot.on(...)` 尽量透传 `FastEvents.on(...)`
- 语义装饰器在注册时经过 `FacadeBinder`
- facade 不负责 transport 初始化与关闭


## 10. 推荐目录结构

```text
fastnapcat/
  app.py
  __init__.py
  models/
  api/
  message/
  adapter/
    __init__.py
    inbound.py
    tags.py
    command.py
  runtime/
    __init__.py
    transport.py
    bridge.py
  context/
    __init__.py
    event.py
    message.py
    command.py
    api.py
  di/
    __init__.py
    providers.py
    registry.py
    rewrite.py
  facade/
    __init__.py
    on.py
    command.py
    session.py
    api.py
```


## 11. 现有代码的保留与重写建议

### 11.1 建议保留

- `fastnapcat/models/*`
- `fastnapcat/api/*`
- `fastnapcat/message/*`
- `fastnapcat/command/parser.py` 中可复用的纯解析逻辑
- `fastnapcat/adapter/tags.py` 中的 tag 常量定义


### 11.2 建议重写

- `fastnapcat/app.py`
- `fastnapcat/runtime/ws.py`
- `fastnapcat/runtime/protocol.py`
- `fastnapcat/ext/*`
- `fastnapcat/di/compiler.py`
- `fastnapcat/di/signature.py`
- `fastnapcat/context/*` 的大部分定义


### 11.3 建议删除或废弃的思路

- 让 facade 直接持有 runtime 细节
- 在运行时层中创建和拥有 API facade
- 自己维护一套并行于 `fastevents` 的 handler 参数解析器
- 把 extension 当成带生命周期的插件单元


## 12. 里程碑

### M1 最小闭环

目标：跑通最小消息链路。

包含：

- transport 建立连接
- inbound message 能 decode 并发布到 app
- `bot.on.message()` 可注册
- `MessageContext` 可注入
- `ctx.send()` / `ctx.reply()` 可用


### M2 可用开发体验

目标：具备日常开发所需能力。

包含：

- `bot.command()`
- `CommandContext`
- `bot.api`
- 工具依赖函数
- API response 等待表完善


### M3 收敛与完善

目标：补全剩余语义和文档。

包含：

- notice/request/meta
- `prompt` / `listen`
- outbound 观测事件
- 文档更新
- 示例更新
- 测试完善


## 13. 实施顺序

建议按下面顺序实施：

1. 冻结协议层，确认哪些模型和 builder 原样保留
2. 实现 `adapter/inbound.py`、`adapter/command.py`、`runtime/transport.py`
3. 实现 `runtime/bridge.py`，打通最小 inbound/outbound 流程
4. 重写 `context/*` 和 `di/providers.py`
5. 实现 `di/registry.py` 与 `di/rewrite.py`
6. 重写 facade 层
7. 重写 `FastNapCat`
8. 删除旧实现并更新文档、示例、测试


## 14. 测试计划

重写过程中至少要覆盖以下测试：

- payload decode -> typed model
- typed model -> tags
- message -> command projection
- `MessageContext` 注入
- `CommandContext` 注入
- `APIClient` 注入
- outbound API response echo 匹配
- `FastNapCat.astart()` / `astop()` 生命周期
- `bot.on.message()` / `bot.command()` 注册行为


## 15. 决策总结

这次重写的关键不是“多写几个模块”，而是明确三件事：

- `FastNapCat` 是宿主，不是 `app.ex`
- facade 是 app 能力组合，不是带生命周期的 extension
- DI 依赖 `fastevents` 原生机制，只在装饰阶段做受控改写

如果这三件事不先立稳，后续即使继续实现新功能，系统也会再次回到边界混乱的状态。
