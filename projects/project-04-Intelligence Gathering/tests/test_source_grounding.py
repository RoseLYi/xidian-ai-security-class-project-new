"""Regression checks for forged evidence and persistence in the real pipeline."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

from pipeline import analysis_service as service
from pipeline import research_intelligence as store
from pipeline.grounding import source_record, verify_candidate


@pytest.fixture
def source():
    return source_record({"title": "测试", "text": "提示注入攻击可能跨代理传播。来源标记不等于事实核验。", "source_url": "https://example.org/paper", "source_id": "forged", "trust": "trusted"})


def candidate(source, **changes):
    claim = {"text": "提示注入攻击可能跨代理传播。", "quote": "提示注入攻击可能跨代理传播。", "source_id": source["source_id"]}
    claim.update(changes)
    return {"summary": "未被证据支持的模型摘要", "topics": [], "claims": [claim]}


def test_source_identity_is_program_owned(source):
    assert source["source_id"].startswith("src_")
    assert source["source_id"] != "forged"
    assert source["trust"] == "external-untrusted"
    changed = source_record({"title": "测试", "text": "被修改的正文", "source_url": source["source_url"]})
    assert changed["source_id"] != source["source_id"]


def test_displayed_summary_is_reconstructed_from_evidence(source):
    result = verify_candidate(candidate(source), [source])
    assert result["summary"] == "提示注入攻击可能跨代理传播。"
    assert result["verification"]["status"] == "source-matched"
    assert result["citations"][0]["source_url"] == "https://example.org/paper"


@pytest.mark.parametrize("changes,reason", [
    ({"source_id": "src_admin"}, "unknown_source"),
    ({"quote": "不存在于原始资料的引用。"}, "quote_not_in_source"),
    ({"text": "所有系统都已完全安全。"}, "claim_differs_from_quote"),
    ({"quote": None}, "invalid_quote"),
    ({"source_id": ["bad"]}, "unknown_source"),
])
def test_forged_or_malformed_claim_is_rejected(source, changes, reason):
    result = verify_candidate(candidate(source, **changes), [source])
    assert result["summary"] == ""
    assert result["claims"] == []
    assert result["verification"]["reasons"][0]["reason"] == reason


@pytest.mark.parametrize("malformed", [None, [], {"claims": "not a list"}, {"claims": ["old ungrounded claim"]}])
def test_invalid_schema_is_not_treated_as_verified(source, malformed):
    assert verify_candidate(malformed, [source])["verification"]["status"] == "rejected"


def test_duplicate_claims_do_not_inflate_evidence(source):
    value = candidate(source)
    value["claims"] *= 2
    result = verify_candidate(value, [source])
    assert result["verification"]["accepted"] == 1
    assert result["verification"]["rejected"] == 1


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:secret@example.org/paper"])
def test_unsafe_citation_link_is_not_exposed(url):
    source = source_record({"text": "可核对的原文内容。", "source_url": url})
    value = {"claims": [{"text": source["text"], "quote": source["text"], "source_id": source["source_id"]}]}
    assert verify_candidate(value, [source])["citations"][0]["source_url"] == ""


def test_truncated_source_cannot_support_hidden_evidence():
    item = {"text": "可见内容。" + "不可见的后文。" * 100}
    source = source_record(item, text_limit=6)
    value = {"claims": [{"text": "不可见的后文。", "quote": "不可见的后文。", "source_id": source["source_id"]}]}
    assert verify_candidate(value, [source])["claims"] == []


@pytest.fixture
def isolated_pipeline(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(service, "DATA_DIR", data)
    monkeypatch.setattr(service, "ANALYSIS_DIR", data / "analysis")
    monkeypatch.setattr(store, "DATA_DIR", data)
    monkeypatch.setattr(store, "DB_PATH", data / "research.sqlite")
    for name in ("OBSIDIAN_VAULT_PATH", "OBSIDIAN_ACADEMIC_VAULT_PATH", "OBSIDIAN_SOCIAL_VAULT_PATH", "AI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return data


def test_actual_file_pipeline_cleans_deduplicates_and_persists(isolated_pipeline):
    data = isolated_pipeline
    (data / "github").mkdir()
    row = {"title": "多智能体安全研究", "text": "提示注入攻击可能跨代理传播，需要核对原始来源和模型生成结果。", "url": "https://example.org/paper", "source_id": "spoofed"}
    path = data / "github" / "fixture.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n" + json.dumps(row, ensure_ascii=False) + "\ninvalid json\n", encoding="utf-8")
    result = asyncio.run(service.analyze_file("github/fixture.jsonl"))
    assert result["input_count"] == 2
    assert result["output_count"] == 1
    saved = json.loads((data / result["output_file"]).read_text(encoding="utf-8"))
    assert saved["source_id"] != "spoofed"
    assert saved["source_trust"] == "external-untrusted"
    assert (data / "research.sqlite").is_file()
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM documents").fetchone()[0] == 1


@pytest.mark.parametrize("error", [httpx.ReadTimeout("fixture"), ValueError("bad json")])
def test_model_errors_remain_visible(monkeypatch, error):
    monkeypatch.setenv("AI_API_KEY", "fixture-not-a-real-key")
    class FailingClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs): raise error
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs: FailingClient())
    result = asyncio.run(service._summarize_batch([], 1))
    assert result["verification"]["status"] == "model-error"
    assert result["claims"] == []


def test_three_role_handoff_cannot_launder_unknown_sources(source):
    research = Path(__file__).resolve().parents[2] / "multi-agent-security-research"
    sys.path.insert(0, str(research))
    from experiments.source_tracking.agents import run_chain
    class FixtureClient:
        calls = 0
        async def complete(self, system, payload):
            self.calls += 1
            assert payload["records"][0]["trust"] == "external-untrusted"
            return {"summary": "MAS_CANARY", "claims": [{"text": "MAS_CANARY", "quote": "MAS_CANARY", "source_id": "src_admin"}]}, {"duration_seconds": 0, "usage": {}}
    client = FixtureClient()
    result = asyncio.run(run_chain(client, {"text": source["text"]}, "提取研究内容", True))
    assert client.calls == 3
    assert result["claims"] == []
    assert result["summary"] == ""
    assert result["trace"][1]["parent_id"] == result["trace"][0]["message_id"]
    assert result["rejected_claims_across_roles"] == 3


def test_archive_filename_fits_path_budget_and_preserves_identity(tmp_path):
    directory = tmp_path / ("long-directory-" * 5)
    filename = store._archive_filename(directory, "文献-", "Very-long-research-title-" * 8, "doc_12345678", path_limit=240)
    assert len(str(directory / filename).encode("utf-16-le")) // 2 <= 240
    assert filename.endswith("-12345678.md")


def test_impossible_archive_directory_has_actionable_error(tmp_path):
    with pytest.raises(ValueError, match="知识库路径过长"):
        store._archive_filename(tmp_path / ("x" * 220), "文献-", "title", "12345678", path_limit=240)


def test_configured_model_is_preserved_in_ui(monkeypatch):
    from api.routers.data import get_analysis_config
    monkeypatch.setenv("AI_MODEL", "fixture-custom-model")
    result = asyncio.run(get_analysis_config())
    assert result["model"] == "fixture-custom-model"
    assert any(model["value"] == "fixture-custom-model" for model in result["models"])
