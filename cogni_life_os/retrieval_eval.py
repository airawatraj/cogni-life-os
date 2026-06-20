from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from .ids import utc_now
from .indexer import Index
from .vault import Vault


def build_corpus(vault: Vault, size: int) -> dict[str, list[str]]:
    vault.init()
    expected = {
        "insurance renewal": [],
        "policy admin": [],
        "ancient modern comparison": [],
        "old wisdom new science": [],
        "confidential work project": [],
        "client roadmap risk": [],
    }
    for i in range(size):
        if i == 0 or i % 997 == 0:
            topic = "insurance renewal"
            body = f"# Insurance Renewal {i}\n\nAlias: policy admin. The current insurance renewal date is 2026-07-{(i % 28) + 1:02d}. Older stale claim: insurance renewal was 2025-01-01.\n"
        elif i == 1 or i % 1231 == 0:
            topic = "ancient modern comparison"
            body = f"# Ancient Modern Comparison {i}\n\nA comparison between ancient knowledge and modern knowledge for decision frameworks. Paraphrase: old wisdom new science.\n"
        elif i == 2 or i % 1543 == 0:
            topic = "confidential work project"
            body = f"# Confidential Work Project {i}\n\nConfidential work project risk with personal overlap. Client roadmap risk. Do not leak externally.\n"
        elif i % 811 == 0:
            topic = ""
            body = f"# Insurance Card Distractor {i}\n\nThis mentions insurance card paperwork but not renewal or policy admin.\n"
        elif i % 887 == 0:
            topic = ""
            body = f"# Ancient Furniture Distractor {i}\n\nAncient table restoration with modern glue, not knowledge comparison.\n"
        else:
            topic = ""
            body = f"# Noise Note {i}\n\nIrrelevant household, learning, and admin filler note number {i}.\n"
        rel = Path("30-concepts") / f"bench-{i:06d}.md"
        note_id = f"bench-{i:06d}"
        text = f"---\nid: {note_id}\ntype: benchmark_note\naliases: [\"alias-{i}\"]\n---\n\n{body}"
        target = vault.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        if topic:
            expected[topic].append(str(rel))
            if topic == "insurance renewal":
                expected["policy admin"].append(str(rel))
            if topic == "ancient modern comparison":
                expected["old wisdom new science"].append(str(rel))
            if topic == "confidential work project":
                expected["client roadmap risk"].append(str(rel))
    return expected


def evaluate_size(size: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        vault = Vault(Path(tmp) / "vault")
        expected = build_corpus(vault, size)
        index = Index(Path(tmp) / "index.sqlite3")
        start = time.monotonic()
        count = index.rebuild(vault)
        rebuild_seconds = time.monotonic() - start
        queries = []
        false_positive_total = 0
        for query, relevant in expected.items():
            q_start = time.monotonic()
            results = index.search(query, limit=10)
            latency = time.monotonic() - q_start
            result_paths = [item["path"] for item in results]
            hits = [path for path in result_paths if path in relevant]
            false_positive_total += len([path for path in result_paths if path not in relevant])
            precision = len(hits) / max(len(result_paths), 1)
            recall = len(hits) / max(min(len(relevant), 10), 1)
            reciprocal_rank = 0.0
            for rank, path in enumerate(result_paths, 1):
                if path in relevant:
                    reciprocal_rank = 1.0 / rank
                    break
            queries.append(
                {
                    "query": query,
                    "relevant_count": len(relevant),
                    "precision_at_10": precision,
                    "recall_at_10": recall,
                    "mrr": reciprocal_rank,
                    "false_positive_rate": (len(result_paths) - len(hits)) / max(len(result_paths), 1),
                    "citation_correctness": precision,
                    "latency_ms": round(latency * 1000, 3),
                    "citations": result_paths,
                }
            )
        inc_rel = "30-concepts/incremental-update.md"
        (vault.root / inc_rel).write_text("---\nid: incremental-update\ntype: benchmark_note\n---\n\n# Incremental Update\n\npolicy admin incremental update\n", encoding="utf-8")
        inc_start = time.monotonic()
        index.update_note(vault, inc_rel)
        incremental_latency_ms = round((time.monotonic() - inc_start) * 1000, 3)
        return {
            "size": size,
            "indexed_notes": count,
            "rebuild_seconds": round(rebuild_seconds, 3),
            "incremental_update_latency_ms": incremental_latency_ms,
            "false_positive_total": false_positive_total,
            "queries": queries,
            "passed": count >= size and all(q["precision_at_10"] >= 0.5 and q["mrr"] > 0 for q in queries) and incremental_latency_ms < 250,
        }


def run(sizes: list[int]) -> dict:
    results = [evaluate_size(size) for size in sizes]
    return {"timestamp": utc_now(), "sizes": sizes, "results": results, "passed": all(item["passed"] for item in results)}
