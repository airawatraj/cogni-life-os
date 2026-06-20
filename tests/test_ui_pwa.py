import base64
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path

from cogni_life_os.config import Settings
from cogni_life_os.ingest import capture_text
from cogni_life_os.server import APP_HTML, SERVICE_WORKER, app_status, chat_turn, handle_upload, list_tasks, manifest, qr_svg, read_static, transcribe_audio, voice_status
from cogni_life_os.vault import Vault
from cogni_life_os.indexer import Index


class UiPwaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.token = "ui-test-token"
        self.settings = Settings(
            vault_path=root / "vault",
            runtime_path=root / "runtime",
            backup_path=root / "backups",
            evidence_path=root / "evidence",
            service_token=self.token,
        )
        self.vault = Vault(self.settings.vault_path)
        self.vault.init()
        self.index = Index(self.settings.runtime_path / "index.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_authentication_required_for_api(self):
        self.assertIn('id="loginForm"', APP_HTML)
        self.assertIn('localStorage.getItem("cogni_token")', APP_HTML)
        self.assertIn('"Authorization": "Bearer " + state.token', APP_HTML)
        self.assertIn("Authentication failed. Check the service token.", APP_HTML)

    def test_capture_search_file_upload_and_tasks_flow(self):
        captured = capture_text(self.vault, "Kitchen filter replacement is due Friday", channel="pwa")
        self.index.rebuild(self.vault)
        self.assertTrue(captured.source_id.startswith("source-"))

        results = self.index.search("kitchen filter")
        self.assertTrue(results)
        self.assertIn("path", results[0])

        upload = {
            "filename": "receipt.txt",
            "data_base64": base64.b64encode(b"Receipt for household supplies").decode("ascii"),
            "channel": "pwa",
        }
        uploaded = handle_upload(self.vault, self.index, self.settings, upload)
        self.assertEqual(uploaded["extraction"]["status"], "complete")

        tasks = list_tasks(self.vault)
        self.assertTrue(tasks)

    def test_shell_contains_chat_capture_sources_proposals_and_responsive_layout(self):
        self.assertIn('id="chatForm"', APP_HTML)
        self.assertIn('id="captureBtn"', APP_HTML)
        self.assertIn('id="uploadInput"', APP_HTML)
        self.assertIn("async function sendChat", APP_HTML)
        self.assertIn("Sources", APP_HTML)
        self.assertIn("Proposed action", APP_HTML)
        self.assertIn('id="voiceBtn" type="button"', APP_HTML)
        self.assertIn('id="conversationMode"', APP_HTML)
        self.assertIn("startRecording", APP_HTML)
        self.assertIn("stopRecording", APP_HTML)
        self.assertIn("encodeWav", APP_HTML)
        self.assertIn("/api/transcribe", APP_HTML)
        self.assertIn("speechSynthesis", APP_HTML)
        self.assertIn("@media (max-width: 860px)", APP_HTML)
        self.assertIn("viewport-fit=cover", APP_HTML)
        self.assertNotIn("<h2>Dashboard</h2>", APP_HTML)
        self.assertNotIn("benchmark", APP_HTML.lower())

    def test_pwa_manifest_and_offline_shell(self):
        data = manifest()
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["start_url"], "/")
        self.assertTrue(data["icons"])
        self.assertIn("/static/branding/cogni-chat-new-logo-round.ico", {item["src"] for item in data["icons"]})
        self.assertIn("/static/icons/cogni-pwa-192.jpg", {item["src"] for item in data["icons"]})
        self.assertEqual(data["scope"], "/")
        self.assertIn("/static/branding/cogni-logo.jpeg", SERVICE_WORKER)
        self.assertIn("caches.match", SERVICE_WORKER)

    def test_branding_assets_are_served_from_static_path(self):
        logo, logo_type = read_static("branding/cogni-logo.jpeg")
        favicon, favicon_type = read_static("branding/cogni-chat-new-logo-round.ico")
        icon_192, icon_type = read_static("icons/cogni-pwa-192.jpg")
        self.assertEqual(logo_type, "image/jpeg")
        self.assertEqual(favicon_type, "image/x-icon")
        self.assertEqual(icon_type, "image/jpeg")
        self.assertTrue(logo.startswith(b"\xff\xd8\xff"))
        self.assertTrue(favicon.startswith(b"\x00\x00\x01\x00"))
        self.assertTrue(icon_192.startswith(b"\xff\xd8\xff"))
        self.assertIn("/static/branding/cogni-logo.jpeg", APP_HTML)
        self.assertIn("/static/branding/cogni-chat-new-logo-round.ico", APP_HTML)

    def test_qr_url_generation_and_loopback_phone_warning(self):
        status = app_status(self.settings, self.vault, self.index, "127.0.0.1:8765")
        self.assertEqual(status["service"]["reachable_url"], "http://127.0.0.1:8765")
        self.assertTrue(status["service"]["loopback_only"])
        self.assertEqual(status["service"]["phone_warning"], "Phone access unavailable: service is bound to 127.0.0.1")
        self.assertIn('"/qr.svg?url=" + encodeURIComponent(status.service.reachable_url || status.service.local_url)', APP_HTML)
        svg = qr_svg(status["service"]["reachable_url"])
        self.assertIn("<title>http://127.0.0.1:8765</title>", svg)
        self.assertIn("<path", svg)

    def test_source_display_and_proposal_confirmation_are_frontend_flows(self):
        self.assertIn("sourcesHtml(results)", APP_HTML)
        self.assertIn("Citation [${i + 1}]", APP_HTML)
        self.assertIn("card.querySelector(\".approve\")", APP_HTML)
        self.assertIn("card.querySelector(\".reject\")", APP_HTML)
        self.assertIn('await captureNote(text, "chat")', APP_HTML)

    def test_voice_status_is_local_and_honest(self):
        status = voice_status()
        self.assertEqual(status["stt"]["provider"], "whisper-cpp")
        self.assertFalse(status["stt"]["cloud"])
        self.assertEqual(status["tts"]["provider"], "browser speechSynthesis")
        self.assertEqual(status["tts"]["status"], "browser_fallback")

    def test_transcribe_audio_is_ephemeral_and_fails_closed_or_transcribes(self):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"\x00\x00" * 8000)
        result = transcribe_audio({"filename": "voice.wav", "data_base64": base64.b64encode(buf.getvalue()).decode("ascii")}, self.settings)
        self.assertFalse(result["preserved"])
        self.assertFalse(result["cloud"])
        self.assertEqual(result["detected_mime"], "audio/wav")
        self.assertIn(result["status"], {"complete", "no_text", "error"})

    def test_chat_turn_uses_model_contract_or_reports_unavailable(self):
        capture_text(self.vault, "Household router password is stored in the secure note", channel="pwa")
        self.index.rebuild(self.vault)
        result = chat_turn(self.settings, self.index, {"message": "router password", "input": "voice"})
        self.assertIn(result["status"], {"completed", "unavailable"})
        self.assertEqual(result["input"], "voice")
        self.assertTrue(result["sources"])
        self.assertIn("reply", result)


if __name__ == "__main__":
    unittest.main()
