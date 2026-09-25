import contextvars
import sys
import types
from typing import Any, Optional

from agents.graph.state import AgentContext

_current_context: contextvars.ContextVar[Optional[AgentContext]] = contextvars.ContextVar(
    "current_agent_context", default=None
)
_current_writer: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "current_stream_writer", default=None
)
_global_context: Optional[AgentContext] = None


def set_current_context(ctx: AgentContext):
    global _global_context
    _global_context = ctx
    return _current_context.set(ctx)


def get_current_context() -> AgentContext:
    ctx = _current_context.get()
    if ctx is not None:
        return ctx
    if _global_context is not None:
        return _global_context

    # Fallback to default services from settings
    from agents.config import Settings
    from agents.services import build_services

    settings = Settings()
    ctx = AgentContext(services=build_services(settings), location=settings.job_location)
    set_current_context(ctx)
    return ctx


def set_active_stream_writer(writer: Any):
    return _current_writer.set(writer)


def get_active_stream_writer() -> Optional[Any]:
    w = _current_writer.get()
    if w is not None:
        return w
    try:
        from langgraph.utils.runnable import var_child_runnable_config
        conf = var_child_runnable_config.get()
        if conf and isinstance(conf, dict):
            writer = conf.get("configurable", {}).get("__pregel_stream_writer")
            if writer:
                return writer
    except Exception:
        pass
    return None


class Runtime:
    """Provides access to the active AgentContext across nodes and conditional edges."""

    def __init__(self, config: Any = None):
        if isinstance(config, Runtime):
            self._context = config._context
        elif isinstance(config, dict) and "configurable" in config and "context" in config["configurable"]:
            self._context = config["configurable"]["context"]
        elif isinstance(config, AgentContext):
            self._context = config
        else:
            self._context = None

        if isinstance(config, dict) and "configurable" in config and "__pregel_stream_writer" in config["configurable"]:
            set_active_stream_writer(config["configurable"]["__pregel_stream_writer"])

    @property
    def context(self) -> AgentContext:
        if self._context:
            return self._context
        try:
            from langgraph.utils.runnable import var_child_runnable_config
            conf = var_child_runnable_config.get()
            if conf and isinstance(conf, dict) and "context" in conf.get("configurable", {}):
                return conf["configurable"]["context"]
        except Exception:
            pass
        return get_current_context()


def get_runtime(runtime: Any = None) -> Runtime:
    if isinstance(runtime, Runtime):
        return runtime
    return Runtime(runtime)


# Register shim for 'langgraph.runtime' only if missing
if "langgraph.runtime" not in sys.modules:
    shim_runtime = types.ModuleType("langgraph.runtime")
    shim_runtime.Runtime = Runtime
    shim_runtime.get_runtime = get_runtime
    sys.modules["langgraph.runtime"] = shim_runtime

# Ensure StateSnapshot.interrupts exists on langgraph.types.StateSnapshot
try:
    from langgraph.types import StateSnapshot
    if not hasattr(StateSnapshot, "interrupts"):
        def _get_interrupts(self):
            result = []
            for t in getattr(self, "tasks", ()):
                if hasattr(t, "interrupts") and t.interrupts:
                    result.extend(t.interrupts)
            return tuple(result)

        StateSnapshot.interrupts = property(_get_interrupts)
except Exception:
    pass

# Patch langgraph.pregel.loop.map_command to properly handle empty resume lists (e.g. Command(resume=[]))
try:
    import langgraph.pregel.loop as loop_mod
    orig_map_command = loop_mod.map_command

    def patched_map_command(cmd, pending_writes):
        yield from orig_map_command(cmd, pending_writes)
        if cmd.resume is not None and not cmd.resume:
            yield (loop_mod.NULL_TASK_ID, loop_mod.RESUME, cmd.resume)

    loop_mod.map_command = patched_map_command
except Exception:
    pass
