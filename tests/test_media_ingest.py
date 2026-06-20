import io
import shutil
import struct
import subprocess
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path

from cogni_life_os.ingest import capture_binary
from cogni_life_os.media import detect_mime, extract, sanitize_filename
from cogni_life_os.vault import Vault


PNG_1X1 = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 1, 1) + b"\x08\x02\x00\x00\x00" + b"\x00\x00\x00\x00"


class MediaIngestTests(unittest.TestCase):
    def test_mime_detection_and_filename_sanitization(self):
        self.assertEqual(detect_mime(PNG_1X1, "x.png"), "image/png")
        self.assertEqual(sanitize_filename("../bad name.pdf"), "bad_name.pdf")

    def test_png_extraction_uses_real_tesseract_or_fails_closed(self):
        result = extract(PNG_1X1, "tiny.png")
        if shutil.which("tesseract"):
            self.assertIn(result.status, {"complete", "no_text", "error"})
            self.assertEqual(result.extractor, "tesseract")
        else:
            self.assertEqual(result.error_code, "OCR_ENGINE_UNAVAILABLE")
        self.assertEqual(result.detected_mime, "image/png")
        self.assertIsNotNone(result.source_hash)

    def test_pdf_text_extraction(self):
        pdf = b"%PDF-1.4\nBT (Hello PDF) Tj ET\n%%EOF"
        result = extract(pdf, "doc.pdf")
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.extracted_text, "Hello PDF")
        self.assertIn(result.extractor, {"pdftotext", "pdf_literal_text"})

    def test_docx_extraction(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("word/document.xml", "<w:document><w:t>Hello DOCX</w:t></w:document>")
        result = extract(buf.getvalue(), "file.docx")
        self.assertEqual(result.status, "complete")
        self.assertIn("Hello DOCX", result.extracted_text)

    def test_wav_transcription_uses_whisper_or_fails_closed(self):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"\x00\x00" * 8000)
        result = extract(buf.getvalue(), "voice.wav")
        self.assertEqual(result.detected_mime, "audio/wav")
        if shutil.which("whisper-cli") and (Path(__file__).resolve().parents[1] / ".cogni" / "models" / "ggml-tiny.en.bin").exists():
            self.assertIn(result.status, {"no_text", "complete"})
            self.assertEqual(result.extractor, "whisper-cpp")
        else:
            self.assertEqual(result.status, "error")
            self.assertIn(result.error_code, {"TRANSCRIPTION_ENGINE_UNAVAILABLE", "TRANSCRIPTION_MODEL_UNAVAILABLE"})

    def test_real_tesseract_ocr_fixture_when_available(self):
        if not shutil.which("tesseract") or not shutil.which("text2image"):
            self.skipTest("tesseract/text2image not installed")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "ocr.txt"
            source.write_text("COGNI OCR TEST\n", encoding="utf-8")
            outputbase = Path(tmp) / "ocr"
            subprocess.run(
                [
                    "text2image",
                    "--text",
                    str(source),
                    "--outputbase",
                    str(outputbase),
                    "--font",
                    "Arial",
                    "--ptsize",
                    "24",
                    "--xsize",
                    "1000",
                    "--ysize",
                    "240",
                    "--margin",
                    "20",
                    "--degrade_image=false",
                    "--rotate_image=false",
                    "--white_noise=false",
                    "--smooth_noise=false",
                    "--blur=false",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            image = Path(str(outputbase) + ".tif")
            result = extract(image.read_bytes(), "ocr.tif")
            self.assertEqual(result.status, "complete")
            self.assertIn("COGNI", result.extracted_text.upper())
            self.assertEqual(result.extractor, "tesseract")

    def test_real_whisper_transcription_fixture_when_available(self):
        model = Path(__file__).resolve().parents[1] / ".cogni" / "models" / "ggml-tiny.en.bin"
        if not shutil.which("whisper-cli") or not shutil.which("espeak") or not model.exists():
            self.skipTest("whisper-cli, espeak, or model unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "speech.wav"
            subprocess.run(["espeak", "-s", "130", "-w", str(wav), "hello world"], check=True, timeout=20)
            result = extract(wav.read_bytes(), "speech.wav")
            self.assertEqual(result.status, "complete")
            self.assertIn("HELLO", result.extracted_text.upper())
            self.assertEqual(result.extractor, "whisper-cpp")

    def test_scanned_pdf_ocr_fixture_when_available(self):
        required = ["text2image", "tiff2pdf", "tesseract", "pdftoppm"]
        if any(not shutil.which(item) for item in required):
            self.skipTest("scanned PDF OCR tools unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "scan.txt"
            source.write_text("SCANNED COGNI TEXT\n", encoding="utf-8")
            outputbase = Path(tmp) / "scan"
            subprocess.run(
                [
                    "text2image",
                    "--text",
                    str(source),
                    "--outputbase",
                    str(outputbase),
                    "--font",
                    "Arial",
                    "--ptsize",
                    "24",
                    "--xsize",
                    "1000",
                    "--ysize",
                    "240",
                    "--margin",
                    "20",
                    "--degrade_image=false",
                    "--rotate_image=false",
                    "--white_noise=false",
                    "--smooth_noise=false",
                    "--blur=false",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            pdf = Path(tmp) / "scan.pdf"
            subprocess.run(["tiff2pdf", "-o", str(pdf), str(outputbase) + ".tif"], check=True, capture_output=True, timeout=15)
            result = extract(pdf.read_bytes(), "scan.pdf")
            self.assertEqual(result.status, "complete")
            self.assertIn("COGNI", result.extracted_text.upper())
            self.assertEqual(result.extractor, "pdftoppm+tesseract")

    def test_binary_source_preserves_bytes_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            first = capture_binary(vault, b"%PDF-1.4\nBT (Receipt) Tj ET\n%%EOF", "../receipt.pdf")
            second = capture_binary(vault, b"%PDF-1.4\nBT (Receipt) Tj ET\n%%EOF", "../receipt.pdf")
            self.assertFalse(first["duplicate"])
            self.assertTrue(second["duplicate"])
            self.assertEqual((vault.root / first["attachment_path"]).read_bytes(), b"%PDF-1.4\nBT (Receipt) Tj ET\n%%EOF")
            self.assertEqual(first["extraction"]["extracted_text"], "Receipt")


if __name__ == "__main__":
    unittest.main()
