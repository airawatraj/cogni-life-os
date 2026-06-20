# Production Readiness

Status: local production candidate, not production or iCloud activated.

## Passed Locally

- Local development vault creation
- Path traversal prevention
- Atomic write with read-back verification
- Conflict record creation on stale writes
- Text source preservation
- Visible task records
- Rebuildable SQLite full-text index
- Integrity scan
- Versioned backup with hash verification
- Private local API token gate
- Local Cogni-Brain endpoint integration verified
- Live Cogni-Brain adversarial, routing, final-content, and actual tool-call contract passes with `reasoning_effort=none`, `chat_template_kwargs.enable_thinking=false`, and JSON response mode where needed
- Held-out layered lexical retrieval benchmarks pass at 10k, 50k, and 100k local synthetic notes

## Live Model Observation

Endpoint discovery reports `Cogni-Brain` served by vLLM with root `Intel/Qwen3.5-122B-A10B-int4-AutoRound` and `max_model_len` 262144. The v5 live contract evidence shows 10/10 scenarios passing, including prompt-injection quarantine, confidentiality refusal, personal/work routing, and actual OpenAI-compatible `tool_calls`.

## Residual Risks

- Live Cogni-Brain multimodal behavior must be proven against the actual endpoint.
- iCloud integration tests are intentionally not run in this session.
- Production iCloud vault activation remains a deferred external gate.
- Video understanding remains fail-closed and is not claimed as supported.
- Model-based embedding retrieval is not implemented or validated.
