# Local Requirement Matrix

| Requirement ID | Requirement | Implementation | Tests | Evidence | Class | Status | Residual Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | Development vault is local, disposable, non-iCloud | `config.py`, `vault.py` | `test_vault_security.py` | `.cogni/local-candidate-evidence-v5/deterministic-tests.txt` | local | PASS | none |
| 4.2 | iCloud integration test vault | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires iCloud |
| 4.3 | Production iCloud vault activation | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires explicit later activation |
| 7 | Atomic writes, conflict checks, path safety | `path_safety.py`, `vault.py` | `test_vault_security.py` | `.cogni/local-candidate-evidence-v5/deterministic-tests.txt` | local | PASS | none |
| 7 | iCloud-specific conflict behavior | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires iCloud sync |
| 8 | Private local API auth and loopback bind | `server.py`, `auth.py` | `test_server_security.py` | `.cogni/local-candidate-evidence-v5/regression-gates.txt` | local | PASS | local HTTP only |
| 9 | Text and binary source preservation | `ingest.py`, `server.py` | `test_core.py`, `test_media_ingest.py`, `test_upload_api.py` | `.cogni/local-candidate-evidence-v5/deterministic-tests.txt` | local | PASS | none |
| 10 | Image/screenshot/receipt OCR | `media.py` | `test_media_ingest.py` | `.cogni/local-candidate-evidence-v5/real-multimodal-tests.txt` | local/live local tool | PASS | optional OCR engine absence is reported as SKIP, not PASS |
| 10 | Text PDF extraction | `media.py` | `test_media_ingest.py` | `.cogni/local-candidate-evidence-v5/real-multimodal-tests.txt` | local tool | PASS | none |
| 10 | Scanned PDF OCR | `media.py` | `test_media_ingest.py` | `.cogni/local-candidate-evidence-v5/real-multimodal-tests.txt` | local tool | PASS | portable fixture rendering; first three pages bounded |
| 10 | DOCX extraction | `media.py` | `test_media_ingest.py` | `.cogni/local-candidate-evidence-v5/real-multimodal-tests.txt` | local | PASS | basic document XML extraction |
| 10 | WAV transcription | `media.py` | `test_media_ingest.py` | `.cogni/local-candidate-evidence-v5/real-multimodal-tests.txt` | local tool/model | PASS | optional speech dependency absence is reported as SKIP, not PASS |
| 10 | Video understanding | `tools.py` | none | residual risks | local | RESIDUAL_RISK | intentionally unsupported/fail-closed |
| 11 | Durable bounded agent state and restart recovery | `durable_agent.py` | `test_durable_agent.py` | `.cogni/local-candidate-evidence-v5/regression-gates.txt` | local | PASS | model-loop integration remains conservative |
| 13 | Typed tools with real local behavior | `tools.py` | `test_tools.py` | `.cogni/local-candidate-evidence-v5/deterministic-tests.txt` | local | PASS | video remains unsupported |
| 16 | Retrieval and rebuildable indexes | `indexer.py`, `retrieval_eval.py`, `tests/fixtures/retrieval/*` | `test_retrieval_eval.py` plus 10k/50k/100k held-out benchmark | `.cogni/local-candidate-evidence-v5/retrieval-10k-50k-100k.json` | local | PASS | held-out benchmark is synthetic but separated from tuning and includes no-answer, contradiction, scope, aliases, stale/current, and distractors |
| 20 | Live Cogni-Brain contract | `model_contract.py` | `test_model_contract.py` plus live adversarial/tool evidence | `.cogni/local-candidate-evidence-v5/live-model-contract.json` | live | PASS | final-content mode depends on vLLM/Qwen parameters `reasoning_effort=none` and `chat_template_kwargs.enable_thinking=false`; live multimodal remains unverified |
| 22 | Backup and full restore rehearsal | `backup.py` | `test_backup_restore.py` | `.cogni/local-candidate-evidence-v5/regression-gates.txt` | local | PASS | none |
| 20/21 | Soak, concurrency, resource stability | `soak.py`, `indexer.py` | `test_soak.py`, `test_resource_cleanup.py` | `.cogni/local-candidate-evidence-v5/soak-120s.json`, `.cogni/local-candidate-evidence-v5/sqlite-resource-tests.txt` | local | PASS | evidence duration controlled by command env |
| 23 | Accurate docs, residual risk register, and evidence manifest | `docs/*`, `evidence_manifest.py` | `test_evidence_manifest.py` | `.cogni/local-candidate-evidence-v5/manifest.json`, `.cogni/local-candidate-evidence-v5/matrix-validation.json` | local | PASS | docs must be updated with future changes |
| 24 | Physical iPhone validation | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires device |
| 24 | Remote private transport | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires TLS/network deployment |
