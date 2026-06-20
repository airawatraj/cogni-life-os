# Residual Risks

- iCloud behavior, production iCloud activation, physical iPhone use, remote private transport, and real cross-device conflict testing remain `DEFERRED_EXTERNAL_GATE`.
- Video inspection remains `RESIDUAL_RISK`; the local tool fails closed and does not claim support.
- Live Cogni-Brain multimodal endpoint probing remains limited; local multimodal extraction is verified with local tools.
- OCR and speech transcription quality depends on installed local engines and small-model accuracy. The evidence uses Tesseract and whisper-cpp tiny English model.
- Scanned PDF OCR is bounded to the first three pages in this local production candidate to control runtime and resource use.
- The local HTTP service is loopback-only for this phase and must not be exposed on LAN.
- Live Cogni-Brain adversarial, routing, final-content, and actual tool-call probes pass against the local endpoint only when reasoning is disabled with the discovered vLLM/Qwen parameters. Broader live multimodal behavior at that endpoint remains unproven.
- Retrieval uses layered lexical retrieval with SQLite FTS/BM25 and deterministic ranking; it remains disposable and rebuildable from Markdown.
- Model-based embedding retrieval is not implemented or validated.
