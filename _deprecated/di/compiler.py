"""Handler compilation helpers for [`fastnapcat`](fastnapcat/__init__.py)."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastevents import RuntimeEvent

from fastnapcat.command.models import CommandArgs
from fastnapcat.context.message import MessageContext
from fastnapcat.di.providers import (
    build_command_args_dependency,
    build_logger_dependency,
    build_message_context_dependency,
    message_text,
)

if TYPE_CHECKING:
    from _deprecated.runtime.ws import NapCatWSRuntime


Handler = Callable[..., Awaitable[Any]]


def compile_handler(
    callback: Handler, runtime: "NapCatWSRuntime | None" = None, api: Any | None = None
) -> Handler:
    if runtime is None and getattr(api, "bridge", None) is not None:
        runtime = getattr(api, "bridge")
    signature = inspect.signature(callback)
    command_model: type[CommandArgs] | None = None
    needs_message_context = False
    text_param_name: str | None = None
    logger_param_name: str | None = None

    for parameter in signature.parameters.values():
        annotation = parameter.annotation
        if annotation is MessageContext:
            needs_message_context = True
            continue
        if inspect.isclass(annotation) and issubclass(annotation, CommandArgs):
            command_model = annotation
            continue
        if (
            parameter.default is not inspect.Signature.empty
            and getattr(parameter.default, "dependency", None) is not None
        ):
            if getattr(parameter.default.dependency, "name", None) == "message_text":
                text_param_name = parameter.name
            elif getattr(parameter.default.dependency, "name", None) == "logger":
                logger_param_name = parameter.name

    message_dep = (
        build_message_context_dependency(runtime)
        if needs_message_context and runtime is not None
        else None
    )
    command_dep = (
        build_command_args_dependency(command_model)
        if command_model is not None
        else None
    )
    logger_dep = (
        build_logger_dependency(runtime)
        if logger_param_name is not None and runtime is not None
        else None
    )

    if logger_dep is not None:

        async def compiled(
            event: RuntimeEvent,
            message_ctx: MessageContext | None = (
                message_dep() if message_dep is not None else None
            ),
            command_args: CommandArgs | None = (
                command_dep() if command_dep is not None else None
            ),
            text: str = message_text(),
            log: Any = logger_dep(),
        ) -> Any:
            kwargs: dict[str, Any] = {}
            for parameter in signature.parameters.values():
                annotation = parameter.annotation
                if annotation is MessageContext:
                    kwargs[parameter.name] = message_ctx
                elif (
                    inspect.isclass(annotation)
                    and command_model is not None
                    and issubclass(annotation, CommandArgs)
                ):
                    kwargs[parameter.name] = command_args
                elif annotation is RuntimeEvent:
                    kwargs[parameter.name] = event
                elif text_param_name == parameter.name:
                    kwargs[parameter.name] = text
                elif logger_param_name == parameter.name:
                    kwargs[parameter.name] = log
            return await callback(**kwargs)

        return compiled

    async def compiled(
        event: RuntimeEvent,
        message_ctx: MessageContext | None = (
            message_dep() if message_dep is not None else None
        ),
        command_args: CommandArgs | None = (
            command_dep() if command_dep is not None else None
        ),
        text: str = message_text(),
    ) -> Any:
        kwargs: dict[str, Any] = {}
        for parameter in signature.parameters.values():
            annotation = parameter.annotation
            if annotation is MessageContext:
                kwargs[parameter.name] = message_ctx
            elif (
                inspect.isclass(annotation)
                and command_model is not None
                and issubclass(annotation, CommandArgs)
            ):
                kwargs[parameter.name] = command_args
            elif annotation is RuntimeEvent:
                kwargs[parameter.name] = event
            elif text_param_name == parameter.name:
                kwargs[parameter.name] = text
        return await callback(**kwargs)

    return compiled
