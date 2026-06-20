# Local Requirement Matrix

| Requirement ID | Requirement | Implementation | Tests | Evidence | Class | Status | Residual Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | Development vault is local, disposable, non-iCloud | `config.py`, `vault.py` | `test_vault_security.py` | deterministic tests | local | PASS | none |
| 4.2 | iCloud integration test vault | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires iCloud |
| 4.3 | Production iCloud vault activation | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires explicit later activation |
| 7 | Atomic writes, conflict checks, path safety | `path_safety.py`, `vault.py` | `test_vault_security.py` | deterministic tests | local | PASS | none |
| 7 | iCloud-specific conflict behavior | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires iCloud sync |
| 8 | Private local PWA/API auth and loopback bind | `server.py`, `auth.py` | `test_server_security.py` | API smoke evidence | local | PASS | local HTTP only |
| 9 | Text and binary source preservation | `ingest.py`, `server.py` | `test_core.py`, `test_media_ingest.py`, `test_upload_api.py` | deterministic tests | local | PASS | none |
| 10 | Image/screenshot/receipt OCR | `media.py` | `test_media_ingest.py` | real multimodal tests | local/live local tool | PASS | OCR quality depends on Tesseract |
| 10 | Text PDF extraction | `media.py` | `test_media_ingest.py` | real multimodal tests | local tool | PASS | none |
| 10 | Scanned PDF OCR | `media.py` | `test_media_ingest.py` | real multimodal tests | local tool | PASS | first three pages bounded |
| 10 | DOCX extraction | `media.py` | `test_media_ingest.py` | real multimodal tests | local | PASS | basic document XML extraction |
| 10 | WAV transcription | `media.py` | `test_media_ingest.py` | real multimodal tests | local tool/model | PASS | tiny Whisper model accuracy is limited |
| 10 | Video understanding | `tools.py` | none | residual risks | local | RESIDUAL_RISK | intentionally unsupported/fail-closed |
| 11 | Durable bounded agent state and restart recovery | `durable_agent.py` | `test_durable_agent.py` | deterministic tests | local | PASS | model-loop integration remains conservative |
| 13 | Typed tools with real local behavior | `tools.py` | `test_tools.py` | deterministic tests | local | PASS | video remains unsupported |
| 16 | Retrieval and rebuildable indexes | `indexer.py`, `retrieval_eval.py` | `test_retrieval_eval.py` | retrieval evidence | local | PASS | benchmark synthetic but includes scale gates |
| 20 | Live Cogni-Brain contract | `model_contract.py` | `test_model_contract.py` plus live evidence | `.cogni/local-candidate-evidence-v3/live-model-evaluation.json` | live | FAIL | DGX endpoint returned reasoning-only responses for 7/8 scenarios; no final `content` to validate |
| 22 | Backup and full restore rehearsal | `backup.py` | `test_backup_restore.py` | deterministic evaluation | local | PASS | none |
| 20/21 | Soak, concurrency, resource stability | `soak.py`, `indexer.py` | `test_soak.py`, `test_resource_cleanup.py` | soak evidence | local | PASS | evidence duration controlled by command env |
| 23 | Accurate docs and residual risk register | `docs/*` | evidence bundle listing | bundle | local | PASS | docs must be updated with future changes |
| 24 | Physical iPhone validation | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires device |
| 24 | Remote private transport | none | none | deferred gates | external | DEFERRED_EXTERNAL_GATE | requires TLS/network deployment |
