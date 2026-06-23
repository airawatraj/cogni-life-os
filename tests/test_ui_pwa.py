import base64
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path

from cogni_life_os.config import Settings
from cogni_life_os.ingest import capture_text
from cogni_life_os.server import APP_HTML, SERVICE_WORKER, app_status, chat_turn, handle_upload, list_tasks, manifest, qr_svg, read_static, save_vault_config, transcribe_audio, validate_vault_path, voice_status
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
            local_config_path=root / "config.json",
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
        self.assertNotIn('id="conversationMode"', APP_HTML)
        self.assertNotIn('aria-label="Conversation mode"', APP_HTML)
        self.assertNotIn('<option value="text">Text</option>', APP_HTML)
        self.assertNotIn('<option value="voice">Voice</option>', APP_HTML)
        self.assertNotIn('<option value="listen">Listen</option>', APP_HTML)
        self.assertNotIn('<option value="mute">Mute</option>', APP_HTML)
        self.assertIn("startRecording", APP_HTML)
        self.assertIn("stopRecording", APP_HTML)
        self.assertIn("encodeWav", APP_HTML)
        self.assertIn("/api/transcribe", APP_HTML)
        self.assertIn("speechSynthesis", APP_HTML)
        self.assertIn("@media (max-width: 860px)", APP_HTML)
        self.assertIn("[hidden] { display: none !important; }", APP_HTML)
        self.assertIn("viewport-fit=cover", APP_HTML)
        self.assertIn("grid-template-rows: auto minmax(0, 1fr) auto auto", APP_HTML)
        self.assertIn(".playback-bar {", APP_HTML)
        self.assertNotIn("<h2>Dashboard</h2>", APP_HTML)
        self.assertNotIn("benchmark", APP_HTML.lower())

    def test_media_controls_use_accessible_inline_svg_icons(self):
        controls = [
            'aria-label="Add attachment"',
            'aria-label="Hold to talk"',
            'aria-label="Send"',
            'aria-label="Enable spoken replies"',
            'aria-label="Clear conversation"',
            'aria-label="Remove selected attachment"',
            'aria-label="Pause speech"',
            'aria-label="Resume speech"',
            'aria-label="Stop speech"',
            'aria-label="Replay speech"',
            'aria-label="Cancel recording"',
            'aria-label="Refresh service status"',
        ]
        for label in controls:
            self.assertIn(label, APP_HTML)
        self.assertGreaterEqual(APP_HTML.count("<svg viewBox="), len(controls))
        self.assertIn('id="sendBtn"', APP_HTML)
        self.assertIn("ICON_STOP_GENERATION", APP_HTML)
        self.assertIn("setSendResponding(true)", APP_HTML)
        self.assertIn('id="chatCamera" type="file" accept="image/*" capture="environment"', APP_HTML)
        self.assertIn('id="chatPhoto" type="file" accept="image/*"', APP_HTML)
        self.assertIn('id="chatDocument" type="file"', APP_HTML)
        self.assertIn("grid-template-columns: auto auto minmax(0, 1fr) auto", APP_HTML)
        self.assertEqual(APP_HTML.count('id="attachmentBtn"'), 1)
        self.assertNotIn('aria-label="Attach image"', APP_HTML)
        self.assertNotIn('aria-label="Attach document"', APP_HTML)
        self.assertIn("Take photo", APP_HTML)
        self.assertIn("Choose photo", APP_HTML)
        self.assertIn("Choose document", APP_HTML)

    def test_playback_controls_visibility_and_recording_states(self):
        self.assertIn('data-speech-action="pause"', APP_HTML)
        self.assertIn('data-speech-action="resume"', APP_HTML)
        self.assertIn('data-speech-action="stop"', APP_HTML)
        self.assertIn('data-speech-action="replay"', APP_HTML)
        self.assertIn("PLAYBACK_CONTROLS_HTML", APP_HTML)
        self.assertIn('.icon-btn.recording', APP_HTML)
        self.assertIn('.icon-btn.processing', APP_HTML)
        self.assertIn('.icon-btn.error', APP_HTML)
        self.assertIn('setMicState("recording")', APP_HTML)
        self.assertIn('setMicState("processing")', APP_HTML)
        self.assertIn('setMicState("error")', APP_HTML)

    def test_spoken_reply_preference_and_mute_stop_speech(self):
        self.assertIn('localStorage.getItem("cogni_spoken_replies")', APP_HTML)
        self.assertIn('localStorage.setItem("cogni_spoken_replies"', APP_HTML)
        self.assertIn('localStorage.getItem("cogni_conversation_mode")', APP_HTML)
        self.assertIn("function setSpeakerEnabled(enabled)", APP_HTML)
        self.assertIn("if (!state.spokenReplies) stopSpeech();", APP_HTML)
        self.assertIn('state.spokenReplies ? ICON_SPEAKER_ON : ICON_SPEAKER_MUTED', APP_HTML)
        self.assertIn('"Mute spoken replies"', APP_HTML)
        self.assertIn('canSpeak()', APP_HTML)

    def test_thinking_indicator_and_cancellation_flow(self):
        self.assertIn("function thinkingHtml()", APP_HTML)
        self.assertIn("Cogni is thinking", APP_HTML)
        self.assertIn("thinkingPulse", APP_HTML)
        self.assertIn('addMessage("assistant", thinkingHtml(), "", {thinking: true})', APP_HTML)
        self.assertIn("updateMessage(placeholderId", APP_HTML)
        self.assertIn("removeMessage(placeholderId)", APP_HTML)
        self.assertIn("new AbortController()", APP_HTML)
        self.assertIn("stopPendingRequest()", APP_HTML)
        self.assertIn('button.setAttribute("aria-label", isResponding ? "Stop generation" : "Send")', APP_HTML)

    def test_attachment_menu_preview_and_document_upload_flow(self):
        self.assertIn('class="attachment-preview" id="attachmentPreview"', APP_HTML)
        self.assertIn('id="attachmentPreviewImage"', APP_HTML)
        self.assertIn('id="attachmentMenu" role="menu"', APP_HTML)
        self.assertIn("function setPendingImage(file)", APP_HTML)
        self.assertIn("URL.createObjectURL(file)", APP_HTML)
        self.assertIn("function setPendingDocument(file)", APP_HTML)
        self.assertIn('$("removeAttachmentBtn").addEventListener("click", clearPendingAttachment)', APP_HTML)
        self.assertIn("messageImageHtml(m.image)", APP_HTML)
        self.assertIn("imagePayload(attachment.file)", APP_HTML)
        self.assertIn("Remove selected attachment", APP_HTML)

    def test_clear_conversation_is_browser_session_only(self):
        self.assertIn('aria-label="Clear conversation"', APP_HTML)
        self.assertIn("function clearConversation()", APP_HTML)
        self.assertIn('confirm("Clear the current browser conversation?', APP_HTML)
        self.assertIn("stopSpeech();", APP_HTML)
        self.assertIn("stopPendingRequest();", APP_HTML)
        self.assertIn("state.messages = []", APP_HTML)
        self.assertNotIn("captureNote(", APP_HTML.split("function clearConversation()", 1)[1].split("function speakIfEnabled", 1)[0])
        before = {p.relative_to(self.vault.root): p.read_bytes() for p in self.vault.root.rglob("*") if p.is_file()}
        after = {p.relative_to(self.vault.root): p.read_bytes() for p in self.vault.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

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
        self.assertIsNone(status["service"]["reachable_url"])
        self.assertIsNone(status["service"]["phone_url"])
        self.assertTrue(status["service"]["loopback_only"])
        self.assertEqual(status["service"]["phone_warning"], "Phone access unavailable while the service is local-only.")
        self.assertIn("status.service.phone_url", APP_HTML)
        self.assertIn('id="launchQr" hidden', APP_HTML)
        svg = qr_svg("http://192.168.1.44:8765")
        self.assertIn("<title>http://192.168.1.44:8765</title>", svg)
        self.assertIn("<path", svg)
        self.assertNotIn("cogni_token", svg)

    def test_lan_mode_qr_uses_private_lan_address_and_not_token(self):
        import cogni_life_os.server as server

        original = server.detect_lan_ip
        server.detect_lan_ip = lambda: "192.168.1.50"
        try:
            status = app_status(self.settings, self.vault, self.index, "127.0.0.1:8765", ("0.0.0.0", 8765))
        finally:
            server.detect_lan_ip = original
        self.assertEqual(status["service"]["mode"], "lan")
        self.assertEqual(status["service"]["phone_url"], "http://192.168.1.50:8765")
        self.assertNotIn("127.0.0.1", status["service"]["phone_url"])
        self.assertNotIn(self.token, status["service"]["phone_url"])
        self.assertIn("LAN access exposes the service to devices on the same network.", status["service"]["warning"])

    def test_settings_contains_vault_access_and_diagnostics_controls(self):
        self.assertIn("<h2>Vault</h2>", APP_HTML)
        self.assertIn("<h2>Model</h2>", APP_HTML)
        self.assertIn("<h2>Voice</h2>", APP_HTML)
        self.assertIn("<h2>Access</h2>", APP_HTML)
        self.assertIn("<h2>Diagnostics</h2>", APP_HTML)
        self.assertIn('id="refreshStatusBtn"', APP_HTML)
        self.assertNotIn('id="refreshBtn"', APP_HTML)
        self.assertIn('id="vaultPathInput"', APP_HTML)
        self.assertIn('id="validateVaultBtn"', APP_HTML)
        self.assertIn('id="saveVaultBtn"', APP_HTML)
        self.assertIn('id="rebuildIndexBtn"', APP_HTML)

    def test_vault_path_validation_and_icloud_warning(self):
        good = self.vault.root
        (good / "note.md").write_text("# Note\n", encoding="utf-8")
        result = validate_vault_path(str(good))
        self.assertTrue(result["valid"])
        self.assertTrue(result["readable"])
        self.assertTrue(result["writable"])
        expanded = validate_vault_path("~/definitely-not-a-cogni-test-vault")
        self.assertTrue(expanded["path"].startswith(str(Path.home())))
        missing = validate_vault_path(str(good / "missing"))
        self.assertFalse(missing["valid"])
        icloud = good.parent / "iCloud Drive" / "Vault"
        icloud.mkdir(parents=True)
        (icloud / "x.md").write_text("# iCloud note\n", encoding="utf-8")
        icloud_result = validate_vault_path(str(icloud))
        self.assertTrue(icloud_result["valid"])
        self.assertTrue(icloud_result["icloud"])
        self.assertIn("file availability and sync conflicts remain controlled by iCloud", icloud_result["icloud_warning"])

    def test_saving_new_vault_rebuilds_index_without_moving_or_deleting_sources(self):
        old_note = capture_text(self.vault, "old indexed vault", channel="pwa")
        self.index.rebuild(self.vault)
        new_root = Path(self.tmp.name) / "new-vault"
        new_root.mkdir()
        source = new_root / "source.md"
        source.write_text("# New vault\n\nnew indexed vault\n", encoding="utf-8")
        before = source.read_bytes()
        new_vault, result = save_vault_config(self.settings, self.index, self.vault, str(new_root), confirm_switch=True)
        self.assertEqual(new_vault.root, new_root.resolve())
        self.assertEqual(result["index_count"], 1)
        self.assertFalse(result["moved_source_files"])
        self.assertFalse(result["deleted_source_files"])
        self.assertEqual(source.read_bytes(), before)
        self.assertTrue((self.vault.root / old_note.source_path).exists())
        results = self.index.search("new indexed vault")
        self.assertTrue(results)
        self.assertEqual(results[0]["path"], "source.md")

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
