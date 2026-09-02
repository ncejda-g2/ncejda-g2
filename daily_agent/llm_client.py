"""Small, structured LiteLLM client with phase-level usage accounting."""

from __future__ import annotations

import json
import os
import time
from typing import Any

import aiohttp
from jsonschema import Draft202012Validator


llm_usage_log: list[dict[str, Any]] = []


def reset_llm_usage_log() -> None:
    llm_usage_log.clear()


def extract_response_cost(
    data: dict[str, Any], headers: aiohttp.typedefs.LooseHeaders
) -> float | None:
    candidates = [
        data.get("usage", {}).get("cost"),
        data.get("_hidden_params", {}).get("response_cost"),
        data.get("response_cost"),
    ]
    if hasattr(headers, "get"):
        candidates.extend(
            [
                headers.get("x-litellm-response-cost"),
                headers.get("x-litellm-response-cost-original"),
            ]
        )
    for candidate in candidates:
        try:
            if candidate is not None:
                return float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _record_usage(
    *,
    phase: str,
    model: str,
    attempt: int,
    data: dict[str, Any],
    headers: aiohttp.typedefs.LooseHeaders,
    duration_ms: int,
) -> None:
    raw_usage = data.get("usage") or {}
    prompt_details = raw_usage.get("prompt_tokens_details") or {}
    completion_details = raw_usage.get("completion_tokens_details") or {}
    input_tokens = int(
        raw_usage.get("prompt_tokens", raw_usage.get("input_tokens", 0)) or 0
    )
    output_tokens = int(
        raw_usage.get("completion_tokens", raw_usage.get("output_tokens", 0)) or 0
    )
    llm_usage_log.append(
        {
            "phase": phase,
            "model": model,
            "attempt": attempt,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": int(
                raw_usage.get("total_tokens", input_tokens + output_tokens) or 0
            ),
            "cache_read_input_tokens": int(
                raw_usage.get("cache_read_input_tokens", 0)
                or prompt_details.get("cached_tokens", 0)
                or 0
            ),
            "cache_creation_input_tokens": int(
                raw_usage.get("cache_creation_input_tokens", 0) or 0
            ),
            "reasoning_tokens": int(
                completion_details.get("reasoning_tokens", 0) or 0
            ),
            "cost_usd": extract_response_cost(data, headers),
            "duration_ms": duration_ms,
            "raw_usage": raw_usage,
        }
    )


def _parse_json_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ValueError(f"expected string or object response content, got {type(content)}")
    text = content.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3]
    parsed = json.loads(text.strip())
    if not isinstance(parsed, dict):
        raise ValueError("structured response must be a JSON object")
    return parsed


async def call_structured_llm(
    session: aiohttp.ClientSession,
    *,
    phase: str,
    system: str,
    user: str,
    schema_name: str,
    schema: dict[str, Any],
    model: str,
    max_tokens: int = 2500,
    temperature: float = 0.2,
    reasoning_effort: str | None = None,
    service_tier: str | None = None,
    attempts: int = 2,
) -> dict[str, Any]:
    """Call LiteLLM with JSON Schema output and validate the returned object.

    A malformed-but-billed response is still recorded. Retrying is intentionally
    bounded because a failed structure should not turn into an unbounded spend.
    """
    base_url = os.environ.get("LITELLM_BASE_URL")
    api_key = os.environ.get("LITELLM_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError("LITELLM_BASE_URL and LITELLM_API_KEY must be set")

    validator = Draft202012Validator(schema)
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        # The proxy counts reasoning tokens inside max_tokens for GPT-5.6 Luna.
        # Give high/xhigh/max enough headroom to emit the required JSON after
        # reasoning, while keeping the caller's normal budgets unchanged for
        # other models and lower-effort Luna calls.
        effective_max_tokens = max_tokens
        if model.startswith("openai/gpt-5.6-luna") and reasoning_effort in {
            "high",
            "xhigh",
            "max",
        }:
            effective_max_tokens = max_tokens * 3
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": effective_max_tokens,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort
        if service_tier is not None:
            payload["service_tier"] = service_tier
        started = time.monotonic()
        try:
            async with session.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=180),
            ) as response:
                body = await response.text()
                duration_ms = round((time.monotonic() - started) * 1000)
                if response.status != 200:
                    raise RuntimeError(
                        f"LLM HTTP {response.status} during {phase}: {body[:500]}"
                    )
                data = json.loads(body)
                _record_usage(
                    phase=phase,
                    model=model,
                    attempt=attempt,
                    data=data,
                    headers=response.headers,
                    duration_ms=duration_ms,
                )
                parsed = _parse_json_content(data["choices"][0]["message"]["content"])
                errors = sorted(validator.iter_errors(parsed), key=lambda error: error.path)
                if errors:
                    details = "; ".join(error.message for error in errors[:3])
                    raise ValueError(f"invalid structured response for {phase}: {details}")
                return parsed
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                print(f"WARNING: {phase} attempt {attempt} failed; retrying: {exc}")

    assert last_error is not None
    raise last_error


def summarize_llm_usage() -> dict[str, Any]:
    numeric_fields = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "reasoning_tokens",
        "duration_ms",
    )
    totals = {
        field: sum(int(call.get(field, 0) or 0) for call in llm_usage_log)
        for field in numeric_fields
    }
    costs = [
        float(call["cost_usd"])
        for call in llm_usage_log
        if call.get("cost_usd") is not None
    ]
    totals["cost_usd"] = round(sum(costs), 6)
    totals["cost_reported_calls"] = len(costs)
    totals["call_count"] = len(llm_usage_log)
    return totals
