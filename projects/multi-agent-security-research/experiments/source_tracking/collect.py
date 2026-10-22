"""Collect public GitHub research metadata at a fixed, reproducible revision."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

REVISION = "462267451ad935166d8e1b2aad5c2abb8ccbad28"
BLOB = "c95baa6c7391ad9a6601dca0a5e3b9f20966d487"
ENDPOINT = f"https://api.github.com/repos/Sicherheit-in-Multiagentensystemen/multi-agent-security-research/git/blobs/{BLOB}"


def collect(destination: Path, count: int = 20) -> dict:
    """Persist original public fields and collection parameters, without secrets."""
    headers = {"User-Agent": "course-project04-source-tracking"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    response = httpx.get(ENDPOINT, headers=headers, timeout=30)
    response.raise_for_status()
    payload = base64.b64decode(response.json()["content"])
    # Verify the Git blob object, not just the API's declared SHA.
    digest = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
    if digest != BLOB:
        raise ValueError("Public catalog does not match its pinned Git blob")
    catalog = json.loads(payload)
    rows = []
    for paper in catalog[:count]:
        rows.append({
            "case_id": paper["id"], "title": paper["title"], "url": paper["url"],
            "text": (f"文献标题：{paper['title']}\n研究内容：{paper['summary']}\n"
                     f"研究问题：{paper['question']}\n适用边界：{paper['limit']}\n"
                     f"研究范围：{paper['scope']}；研究方法：{paper['method']}；发表记录：{paper['venue']}。\n"
                     "本记录是公开资料库整理的研究说明，并非论文全文；论文作者报告与独立复现结果需要分别核验。"),
            "expected_claim": paper["summary"], "catalog_revision": REVISION,
        })
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "corpus.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    manifest = {"collected_at_utc": datetime.now(timezone.utc).isoformat(), "endpoint": ENDPOINT,
                "revision": REVISION, "blob_sha1": BLOB, "corpus_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "count": len(rows), "selection": f"first {count} catalog entries, original order",
                "topic": "multi-agent systems security", "material_type": "public curated metadata, not full papers"}
    (destination / "collection.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
