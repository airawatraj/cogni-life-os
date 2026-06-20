from __future__ import annotations

import hashlib
import json
import math
import tempfile
import time
from pathlib import Path
from typing import Any

from .ids import utc_now
from .indexer import Index
from .vault import Vault


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "retrieval"


TOPICS = {
    "vehicle_renewal": [
        ("30-concepts/vehicle-protection.md", "Vehicle Protection Schedule", "Alias: auto cover. The vehicle protection plan rollover date is 2026-08-14. Prior 2025 paperwork is stale and superseded."),
    ],
    "ancient_modern": [
        ("30-concepts/ancient-modern-evidence.md", "Ancient Modern Evidence", "Ancient records and modern laboratory trials can be compared when both describe repeatable observations and decision frameworks."),
    ],
    "nova_contradiction": [
        ("40-projects/project-nova-accepted.md", "Project Nova Accepted Position", "Project Nova has an approval note saying the launch risk was accepted by the review group."),
        ("40-projects/project-nova-rejected.md", "Project Nova Rejected Position", "Project Nova also has a contradiction note saying the launch risk was rejected pending more evidence."),
    ],
    "atlas_work": [
        ("40-projects/atlas-client-roadmap.md", "Atlas Client Roadmap", "Atlas is a confidential work project. The client launch risk belongs in the work domain and must not cross into personal notes."),
    ],
    "atlas_person": [
        ("20-entities/atlas-person.md", "Atlas Person", "Atlas is also a personal contact name in a birthday reminder, unrelated to the client roadmap."),
    ],
    "personal_health": [
        ("50-actions/dermatology-followup.md", "Dermatology Follow Up", "Personal health reminder: arrange the skin specialist appointment and keep it out of work records."),
    ],
    "confidential_work": [
        ("40-projects/client-plan-risk.md", "Client Plan Risk", "Confidential workplace note: the customer roadmap risk is internal only and should not be published outside the work boundary."),
    ],
    "multilingual_alias": [
        ("20-entities/surya-dev.md", "Surya Dev", "Alias: Suryadev; transliteration: Surya Dev. Calendar context for the community event."),
    ],
}


def build_corpus(vault: Vault, size: int) -> dict[str, list[str]]:
    vault.init()
    expected: dict[str, list[str]] = {topic: [] for topic in TOPICS}
    expected["no_answer"] = []
    for topic, notes in TOPICS.items():
        for rel, title, body in notes:
            _write_note(vault, rel, title, topic, body)
            expected[topic].append(rel)
    for i in range(size):
        topic = ""
        if i % 997 == 0:
            topic = "vehicle_renewal"
            title = f"Vehicle Protection Clone {i}"
            body = f"Auto cover duplicate. Vehicle plan rollover date 2026-08-{(i % 28) + 1:02d}. Old renewal mail from 2025 is stale."
        elif i % 1231 == 0:
            topic = "ancient_modern"
            title = f"Ancient Modern Clone {i}"
            body = "Ancient records and modern trials describe comparable evidence patterns without copying benchmark questions."
        elif i % 1543 == 0:
            topic = "confidential_work"
            title = f"Confidential Work Clone {i}"
            body = "Customer roadmap risk remains workplace confidential and outside personal scope."
        elif i % 1877 == 0:
            topic = "nova_contradiction"
            title = f"Project Nova Conflict Clone {i}"
            body = "Project Nova contradiction: one decision accepts launch risk while another rejects the same approval."
        elif i % 811 == 0:
            title = f"Vehicle Card Distractor {i}"
            body = "Vehicle card paperwork mentions a policy number but not the protection rollover date."
        elif i % 887 == 0:
            title = f"Ancient Furniture Distractor {i}"
            body = "Ancient table restoration with modern glue, unrelated to conceptual evidence."
        elif i % 919 == 0:
            title = f"Atlas Distractor {i}"
            body = "Atlas map shelf note with no client roadmap, person, or project boundary."
        else:
            title = f"Noise Note {i}"
            body = f"Irrelevant household, reading, garden, and admin filler note number {i}."
        rel = f"30-concepts/bench-{i:06d}.md"
        _write_note(vault, rel, title, topic or "noise", body)
        if topic:
            expected[topic].append(rel)
    return expected


def evaluate_size(size: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        vault = Vault(Path(tmp) / "vault")
        expected = build_corpus(vault, size)
        index = Index(Path(tmp) / "index.sqlite3")
        started = time.monotonic()
        count = index.rebuild(vault)
        rebuild_seconds = time.monotonic() - started
        tuning = _evaluate_queries(vault, index, _load_query_set("tuning.json"), expected)
        heldout = _evaluate_queries(vault, index, _load_query_set("heldout.json"), expected)
        inc_rel = "30-concepts/incremental-update.md"
        (vault.root / inc_rel).write_text("---\nid: incremental-update\ntype: benchmark_note\n---\n\n# Incremental Update\n\nAuto cover rollover update for local indexing.\n", encoding="utf-8")
        inc_start = time.monotonic()
        index.update_note(vault, inc_rel)
        incremental_latency_ms = round((time.monotonic() - inc_start) * 1000, 3)
        embedding = {
            "approach": "deterministic local lexical concept vectors",
            "model": "none",
            "cloud_api": False,
            "authoritative": False,
            "index_size_bytes": 0,
            "rebuild_seconds": 0.0,
            "reason": "SQLite candidates are expanded with deterministic local concept terms; no vector model binary is required for this benchmark.",
        }
        passed = (
            count >= size
            and tuning["passed"]
            and heldout["passed"]
            and incremental_latency_ms < 250
        )
        return {
            "size": size,
            "indexed_notes": count,
            "rebuild_seconds": round(rebuild_seconds, 3),
            "incremental_update_latency_ms": incremental_latency_ms,
            "embedding_index": embedding,
            "dataset_hashes": _dataset_hashes(),
            "tuning": tuning,
            "heldout": heldout,
            "passed": passed,
        }


def run(sizes: list[int]) -> dict[str, Any]:
    results = [evaluate_size(size) for size in sizes]
    return {
        "timestamp": utc_now(),
        "sizes": sizes,
        "benchmark_design": {
            "markdown_authoritative": True,
            "indexes_disposable": True,
            "tuning_file": str(FIXTURE_ROOT / "tuning.json"),
            "heldout_file": str(FIXTURE_ROOT / "heldout.json"),
            "heldout_queries_not_in_source_code": True,
        },
        "results": results,
        "passed": all(item["passed"] for item in results),
    }


def _evaluate_queries(vault: Vault, index: Index, query_set: dict[str, Any], expected: dict[str, list[str]]) -> dict[str, Any]:
    query_results = []
    for item in query_set["queries"]:
        q_start = time.monotonic()
        citations = index.search(item["query"], limit=10)
        latency_ms = round((time.monotonic() - q_start) * 1000, 3)
        relevant = [path for topic in item["expected_topics"] for path in expected.get(topic, [])]
        result_paths = [citation["path"] for citation in citations]
        metrics = _metrics(vault, result_paths, relevant, item)
        query_results.append({"id": item["id"], "query": item["query"], "challenge": item["challenge"], "expected_topics": item["expected_topics"], "latency_ms": latency_ms, "citations": result_paths, **metrics})
    aggregate = _aggregate(query_results)
    passed = (
        aggregate["precision_at_5"] >= 0.65
        and aggregate["recall_at_5"] >= 0.65
        and aggregate["mrr"] >= 0.75
        and aggregate["citation_correctness"] >= 0.75
        and (aggregate["no_answer_accuracy"] is None or aggregate["no_answer_accuracy"] >= 0.99)
    )
    return {"name": query_set["name"], "sha256": _file_hash(FIXTURE_ROOT / query_set["file"]), "queries": query_results, "aggregate": aggregate, "failure_examples": [q for q in query_results if not q["passed"]][:5], "passed": passed}


def _metrics(vault: Vault, result_paths: list[str], relevant: list[str], item: dict[str, Any]) -> dict[str, Any]:
    if not relevant:
        no_answer_ok = len(result_paths) == 0
        return {
            "relevant_count": 0,
            "precision_at_5": 1.0 if no_answer_ok else 0.0,
            "precision_at_10": 1.0 if no_answer_ok else 0.0,
            "recall_at_5": 1.0 if no_answer_ok else 0.0,
            "recall_at_10": 1.0 if no_answer_ok else 0.0,
            "mrr": 1.0 if no_answer_ok else 0.0,
            "ndcg_at_10": 1.0 if no_answer_ok else 0.0,
            "false_positive_rate": 0.0 if no_answer_ok else 1.0,
            "citation_correctness": 1.0 if no_answer_ok else 0.0,
            "grounded_answer_accuracy": 1.0 if no_answer_ok else 0.0,
            "alias_accuracy": None,
            "entity_resolution_accuracy": None,
            "personal_work_routing_accuracy": None,
            "contradiction_retrieval": None,
            "stale_current_selection_accuracy": None,
            "no_answer_accuracy": 1.0 if no_answer_ok else 0.0,
            "passed": no_answer_ok,
        }
    top5 = result_paths[:5]
    hits = [path for path in result_paths if path in relevant]
    hits5 = [path for path in top5 if path in relevant]
    precision10 = len(hits) / max(len(result_paths), 1)
    precision5 = len(hits5) / max(len(top5), 1)
    recall10 = len(set(hits)) / max(min(len(set(relevant)), 10), 1)
    recall5 = len(set(hits5)) / max(min(len(set(relevant)), 5), 1)
    mrr = next((1.0 / rank for rank, path in enumerate(result_paths, 1) if path in relevant), 0.0)
    citation_correctness = _citation_correctness(vault, result_paths, relevant)
    challenge = item["challenge"]
    return {
        "relevant_count": len(relevant),
        "precision_at_5": precision5,
        "precision_at_10": precision10,
        "recall_at_5": recall5,
        "recall_at_10": recall10,
        "mrr": mrr,
        "ndcg_at_10": _ndcg(result_paths, relevant),
        "false_positive_rate": (len(result_paths) - len(hits)) / max(len(result_paths), 1),
        "citation_correctness": citation_correctness,
        "grounded_answer_accuracy": 1.0 if hits and citation_correctness > 0 else 0.0,
        "alias_accuracy": 1.0 if challenge == "alias" and hits else None,
        "entity_resolution_accuracy": 1.0 if challenge == "entity_resolution" and hits else None,
        "personal_work_routing_accuracy": 1.0 if challenge == "personal_work_scope" and hits else None,
        "contradiction_retrieval": 1.0 if challenge == "contradiction" and len(set(hits)) >= min(2, len(set(relevant))) else None,
        "stale_current_selection_accuracy": 1.0 if challenge == "stale_current" and hits else None,
        "no_answer_accuracy": None,
        "passed": precision10 >= 0.5 and mrr > 0 and citation_correctness > 0,
    }


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ["precision_at_5", "precision_at_10", "recall_at_5", "recall_at_10", "mrr", "ndcg_at_10", "false_positive_rate", "citation_correctness", "grounded_answer_accuracy", "alias_accuracy", "entity_resolution_accuracy", "personal_work_routing_accuracy", "contradiction_retrieval", "stale_current_selection_accuracy", "no_answer_accuracy"]
    aggregate: dict[str, Any] = {}
    for field in fields:
        values = [item[field] for item in results if item[field] is not None]
        aggregate[field] = round(sum(values) / len(values), 4) if values else None
    aggregate["passed_queries"] = sum(1 for item in results if item["passed"])
    aggregate["total_queries"] = len(results)
    return aggregate


def _citation_correctness(vault: Vault, result_paths: list[str], relevant: list[str]) -> float:
    if not result_paths:
        return 0.0
    valid = 0
    for path in result_paths:
        note = vault.root / path
        if path in relevant and note.exists() and "id:" in note.read_text(encoding="utf-8"):
            valid += 1
    return valid / len(result_paths)


def _ndcg(result_paths: list[str], relevant: list[str]) -> float:
    def gain(paths: list[str]) -> float:
        return sum((1.0 / math.log2(rank + 1)) for rank, path in enumerate(paths, 1) if path in relevant)
    ideal = gain(relevant[:10])
    return gain(result_paths[:10]) / ideal if ideal else 0.0


def _write_note(vault: Vault, rel: str, title: str, topic: str, body: str) -> None:
    note_id = Path(rel).stem
    path = vault.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nid: {note_id}\ntype: benchmark_note\ntags: [\"{topic}\"]\n---\n\n# {title}\n\n{body}\n", encoding="utf-8")


def _load_query_set(filename: str) -> dict[str, Any]:
    data = json.loads((FIXTURE_ROOT / filename).read_text(encoding="utf-8"))
    data["file"] = filename
    return data


def _dataset_hashes() -> dict[str, str]:
    return {name: _file_hash(FIXTURE_ROOT / name) for name in ["tuning.json", "heldout.json"]}


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
