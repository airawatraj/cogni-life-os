from __future__ import annotations

import json
import os
import resource
import tempfile
import threading
import time
from pathlib import Path

from .ids import utc_now
from .indexer import Index
from .ingest import capture_binary, capture_text
from .integrity import scan
from .vault import Vault


def run(duration_seconds: float = 2.0, operations: int = 200) -> dict:
    started = time.monotonic()
    start_fd = len(os.listdir("/dev/fd"))
    start_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    errors: list[str] = []
    duplicate_side_effects = 0
    op_count = 0
    with tempfile.TemporaryDirectory() as tmp:
        vault = Vault(Path(tmp) / "vault")
        vault.init()
        index = Index(Path(tmp) / "index.sqlite3")
        stop = threading.Event()
        search_count = 0

        def reader():
            nonlocal search_count
            while not stop.is_set():
                try:
                    index.search("soak")
                    search_count += 1
                except Exception as exc:
                    errors.append(f"reader:{type(exc).__name__}:{exc}")

        thread = threading.Thread(target=reader)
        thread.start()
        seen_sources = set()
        i = 0
        while time.monotonic() - started < duration_seconds and op_count < operations:
            try:
                result = capture_text(vault, f"soak duplicate payload {i % 20}")
                if result.source_id in seen_sources and not result.duplicate:
                    duplicate_side_effects += 1
                seen_sources.add(result.source_id)
                if i % 25 == 0:
                    capture_binary(vault, b"%PDF-1.4\nBT (Soak PDF) Tj ET\n%%EOF", f"soak-{i}.pdf")
                if i % 20 == 0:
                    index.rebuild(vault)
                op_count += 1
            except Exception as exc:
                errors.append(f"writer:{type(exc).__name__}:{exc}")
            i += 1
        stop.set()
        thread.join(timeout=5)
        index.rebuild(vault)
        integrity = scan(vault)
        end_fd = len(os.listdir("/dev/fd"))
        end_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {
            "timestamp": utc_now(),
            "duration_seconds": round(time.monotonic() - started, 3),
            "operations_requested": operations,
            "operations_completed": op_count,
            "unique_sources": len(seen_sources),
            "reader_searches": search_count,
            "errors": errors,
            "duplicate_side_effects": duplicate_side_effects,
            "file_descriptor_growth": end_fd - start_fd,
            "max_rss_growth": end_rss - start_rss,
            "integrity": integrity,
            "passed": not errors and duplicate_side_effects == 0 and integrity["status"] == "pass" and end_fd - start_fd <= 4,
        }
