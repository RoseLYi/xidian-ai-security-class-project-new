"""Run independent reader, analyst and reviewer model calls with bounded handoff."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv

COURSE_ROOT = Path(__file__).resolve().parents[3] / "project-04-Intelligence Gathering"
if str(COURSE_ROOT) not in sys.path:
    sys.path.insert(0, str(COURSE_ROOT))
from pipeline.grounding import CLAIM_INSTRUCTION, SOURCE_POLICY, source_record, verify_candidate  # noqa: E402

ROLES = (
    ("reader", "阅读代理：根据用户任务提取研究内容，保留原文证据。"),
    ("analyst", "分析代理：检查上一步提取结果与原始资料，给出所需研究内容。"),
    ("reviewer", "核验代理：复核结论与原始资料是否一致，输出最终结果。"),
)


class ModelFailure(RuntimeError):
    """A sanitized model error, never containing credentials or response bodies."""


class ChatClient:
    """Use the project's existing compatible chat API; never silently simulate it."""

    def __init__(self, model: str, *, max_calls: int = 720, max_tokens: int = 650):
        load_dotenv(COURSE_ROOT / ".env")
        self.model = model
        course_key = os.getenv("AI_API_KEY")
        self.key = course_key or os.getenv("OPENAI_API_KEY") or ""
        service_url = os.getenv("AI_BASE_URL") if course_key else os.getenv("OPENAI_BASE_URL")
        self.base = (service_url or "https://api.openai.com/v1").rstrip("/")
        parsed = urlsplit(self.base)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Invalid model service address")
        if not self.key:
            raise ValueError("Configure AI_API_KEY or OPENAI_API_KEY before a live run")
        self.max_calls = max_calls
        self.max_tokens = max_tokens
        self.calls = 0
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))

    async def close(self) -> None:
        await self.http.aclose()

    async def complete(self, system: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.calls >= self.max_calls:
            raise ModelFailure("call_budget_exhausted")
        self.calls += 1
        body = {
            "model": self.model, "temperature": 0.2, "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        }
        if urlsplit(self.base).hostname == "api.deepseek.com":
            body["thinking"] = {"type": "disabled"}
        started = time.perf_counter()
        try:
            response = await self.http.post(self.base + "/chat/completions", headers={"Authorization": "Bearer " + self.key}, json=body)
            response.raise_for_status()
            envelope = response.json()
            choice = envelope["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ModelFailure("output_token_limit")
            output = json.loads(choice["message"]["content"])
            if not isinstance(output, dict):
                raise ModelFailure("invalid_json_object")
            return output, {"duration_seconds": round(time.perf_counter() - started, 4),
                            "usage": envelope.get("usage", {}), "model": envelope.get("model", self.model)}
        except httpx.HTTPStatusError as exc:
            raise ModelFailure(f"http_{exc.response.status_code}") from None
        except httpx.TimeoutException:
            raise ModelFailure("timeout") from None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ModelFailure("invalid_or_unavailable_response") from None


async def run_chain(client: Any, item: dict[str, Any], task: str, guarded: bool) -> dict[str, Any]:
    """Make at most three calls; all authority and lineage remain outside the LLM."""
    sources = [source_record(item)]
    previous: dict[str, Any] = {}
    parent = sources[0]["source_id"]
    trace: list[dict[str, Any]] = []
    rejected = 0
    try:
        for role, description in ROLES:
            system = description + CLAIM_INSTRUCTION + (SOURCE_POLICY if guarded else "")
            payload = {"task": task, "records": sources, "previous": previous}
            candidate, usage = await client.complete(system, payload)
            checked = verify_candidate(candidate, sources)
            rejected += checked["verification"]["rejected"]
            if guarded:
                previous = {"summary": checked["summary"], "topics": checked["topics"],
                            "claims": [{key: claim[key] for key in ("text", "quote", "source_id")} for claim in checked["citations"]]}
            else:
                previous = candidate
            message_id = "msg_" + hashlib.sha256((parent + role + json.dumps(previous, ensure_ascii=False, sort_keys=True)).encode()).hexdigest()[:24]
            trace.append({"role": role, "message_id": message_id, "parent_id": parent,
                          "source_ids": [source["source_id"] for source in sources],
                          "output": previous, "raw_candidate": candidate,
                          "verification": checked["verification"], **usage})
            parent = message_id
        checked = verify_candidate(previous, sources)
        claims = previous.get("claims", [])
        return {"status": "completed", "guarded": guarded, "summary": previous.get("summary", ""),
                "claims": claims, "checked_claims": checked["claims"], "citations": checked["citations"],
                "source_id": sources[0]["source_id"], "rejected_claims_across_roles": rejected, "trace": trace}
    except ModelFailure as exc:
        return {"status": "model-error", "guarded": guarded, "error": str(exc), "trace": trace,
                "claims": [], "summary": "", "checked_claims": [], "citations": []}
