# Residual Risks

- iCloud behavior, production iCloud activation, physical iPhone use, remote private transport, and real cross-device conflict testing remain `DEFERRED_EXTERNAL_GATE`.
- Video inspection remains `RESIDUAL_RISK`; the local tool fails closed and does not claim support.
- Live Cogni-Brain multimodal endpoint probing remains limited; local multimodal extraction is verified with local tools.
- OCR and speech transcription quality depends on installed local engines and small-model accuracy. The evidence uses Tesseract and whisper-cpp tiny English model.
- Scanned PDF OCR is bounded to the first three pages in this local candidate to control runtime and resource use.
- The PWA service is loopback-only local HTTP for this phase and must not be exposed on LAN.
- Live Cogni-Brain gate is currently `FAIL`: latest evidence shows reasoning-only responses without final `content` for most expanded scenarios.
