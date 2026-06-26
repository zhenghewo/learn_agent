"""
全链路追踪 — OpenTelemetry 集成，含 LLM Token 监测
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
except ImportError:
    BaseCallbackHandler = object  # type: ignore[assignment,misc]
    LLMResult = Any  # type: ignore[assignment,misc]

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False


_tracer = None
_token_handler: "OtelTokenCallbackHandler | None" = None


class OtelTokenCallbackHandler(BaseCallbackHandler):
    """LangChain 回调：将 LLM Token 用量写入当前 OTEL Span。"""

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if not _HAS_OTEL:
            return
        span = trace.get_current_span()
        if not span or not span.is_recording():
            return

        usage = _extract_usage_from_llm_result(response)
        if not usage:
            return

        prompt_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))

        span.set_attribute("llm.prompt_tokens", prompt_tokens)
        span.set_attribute("llm.completion_tokens", completion_tokens)
        span.set_attribute("llm.total_tokens", total_tokens)

        model = _extract_model_from_llm_result(response)
        if model:
            span.set_attribute("llm.model", model)


def _extract_usage_from_llm_result(response: LLMResult) -> dict[str, Any]:
    if response.llm_output and isinstance(response.llm_output, dict):
        token_usage = response.llm_output.get("token_usage")
        if isinstance(token_usage, dict):
            return token_usage

    for generations in response.generations:
        for gen in generations:
            message = getattr(gen, "message", None)
            if message is None:
                continue
            usage_meta = getattr(message, "usage_metadata", None)
            if usage_meta:
                return dict(usage_meta)
            resp_meta = getattr(message, "response_metadata", None) or {}
            token_usage = resp_meta.get("token_usage")
            if isinstance(token_usage, dict):
                return token_usage
    return {}


def _extract_model_from_llm_result(response: LLMResult) -> str | None:
    if response.llm_output and isinstance(response.llm_output, dict):
        model = response.llm_output.get("model_name") or response.llm_output.get("model")
        if model:
            return str(model)
    return None


def get_otel_callbacks() -> list[Any]:
    global _token_handler
    if _token_handler is None and _HAS_OTEL:
        _token_handler = OtelTokenCallbackHandler()
    return [_token_handler] if _token_handler else []


def init_tracer(
    service_name: str = "smart-cs-multi-agent",
    otlp_endpoint: str | None = None,
) -> None:
    global _tracer

    if not _HAS_OTEL:
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        except ImportError:
            exporter = ConsoleSpanExporter()
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)


def get_tracer():
    global _tracer
    if _tracer is None:
        if _HAS_OTEL:
            _tracer = trace.get_tracer("smart-cs-multi-agent")
        else:
            return None
    return _tracer


def attach_token_usage_from_response(span: Any, response: Any) -> None:
    """从 LangChain AIMessage 提取 token 并写入 span。"""
    if not span or not getattr(span, "is_recording", lambda: False)():
        return

    usage = getattr(response, "usage_metadata", None) or {}
    if not usage:
        resp_meta = getattr(response, "response_metadata", None) or {}
        usage = resp_meta.get("token_usage") or {}

    if not usage:
        return

    prompt_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))

    span.set_attribute("llm.prompt_tokens", prompt_tokens)
    span.set_attribute("llm.completion_tokens", completion_tokens)
    span.set_attribute("llm.total_tokens", total_tokens)


def trace_agent_call(agent_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            tracer = get_tracer()

            if tracer is None:
                return await func(*args, **kwargs)

            span_name = f"agent.{agent_name}.{func.__name__}"

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("agent.name", agent_name)
                span.set_attribute("agent.method", func.__name__)

                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000

                    span.set_attribute("agent.duration_ms", duration_ms)
                    span.set_attribute("agent.success", True)

                    if isinstance(result, dict):
                        span.set_attribute("agent.result_keys", str(list(result.keys())))
                        tokens = result.get("_token_usage")
                        if isinstance(tokens, dict):
                            span.set_attribute("llm.prompt_tokens", int(tokens.get("prompt_tokens", 0)))
                            span.set_attribute("llm.completion_tokens", int(tokens.get("completion_tokens", 0)))
                            span.set_attribute("llm.total_tokens", int(tokens.get("total_tokens", 0)))

                    return result

                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    span.set_attribute("agent.duration_ms", duration_ms)
                    span.set_attribute("agent.success", False)
                    span.set_attribute("agent.error", str(e))
                    span.record_exception(e)
                    raise

        return wrapper

    return decorator


class AgentMetrics:
    def __init__(self):
        self._call_counts: dict[str, int] = {}
        self._total_duration: dict[str, float] = {}
        self._error_counts: dict[str, int] = {}
        self._total_tokens: dict[str, int] = {}

    def record_call(
        self,
        agent_name: str,
        duration_ms: float,
        success: bool,
        *,
        total_tokens: int = 0,
    ):
        self._call_counts[agent_name] = self._call_counts.get(agent_name, 0) + 1
        self._total_duration[agent_name] = self._total_duration.get(agent_name, 0.0) + duration_ms
        self._total_tokens[agent_name] = self._total_tokens.get(agent_name, 0) + total_tokens
        if not success:
            self._error_counts[agent_name] = self._error_counts.get(agent_name, 0) + 1

    def get_summary(self) -> dict[str, Any]:
        summary = {}
        for agent_name in self._call_counts:
            calls = self._call_counts[agent_name]
            total_ms = self._total_duration[agent_name]
            errors = self._error_counts.get(agent_name, 0)
            tokens = self._total_tokens.get(agent_name, 0)
            summary[agent_name] = {
                "total_calls": calls,
                "avg_duration_ms": total_ms / calls if calls > 0 else 0,
                "error_rate": errors / calls if calls > 0 else 0,
                "total_tokens": tokens,
                "avg_tokens_per_call": tokens / calls if calls > 0 else 0,
            }
        return summary
