from __future__ import annotations

import html
import io
import re
import shutil
import struct
import subprocess
import tempfile
import wave
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path


MAX_EXTRACT_BYTES = 25 * 1024 * 1024
WHISPER_MODEL = Path(__file__).resolve().parents[1] / ".cogni" / "models" / "ggml-tiny.en.bin"


@dataclass(frozen=True)
class ExtractionResult:
    status: str
    extracted_text: str
    detected_mime: str
    extractor: str
    extractor_version: str | None
    confidence: float | None
    warnings: list[str]
    error_code: str | None
    error_details: str | None
    timeout: bool = False
    source_hash: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def detect_mime(data: bytes, filename: str = "") -> str:
    lower = filename.lower()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
        return "image/tiff"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    if data.startswith(b"PK\x03\x04") and lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower.endswith(".txt") or _looks_text(data):
        return "text/plain"
    return "application/octet-stream"


def sanitize_filename(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._")
    return clean or "upload.bin"


def extract(data: bytes, filename: str = "") -> ExtractionResult:
    from .ids import sha256_bytes

    source_hash = sha256_bytes(data)
    if len(data) > MAX_EXTRACT_BYTES:
        return ExtractionResult("error", "", "application/octet-stream", "size_guard", None, None, [], "UPLOAD_TOO_LARGE", "file exceeds extraction limit", source_hash=source_hash)
    mime = detect_mime(data, filename)
    try:
        if mime == "text/plain":
            return ExtractionResult("complete", data.decode("utf-8"), mime, "utf8_text", _version("python3"), 1.0, [], None, None, source_hash=source_hash)
        if mime == "image/png":
            width, height = _png_dimensions(data)
            ocr = _ocr_image(data, filename or "image.png")
            text = ocr.extracted_text or f"PNG image {width}x{height}"
            return ExtractionResult(ocr.status, text, mime, ocr.extractor, ocr.extractor_version, ocr.confidence, ocr.warnings, ocr.error_code, ocr.error_details, ocr.timeout, source_hash)
        if mime == "image/jpeg":
            dims = _jpeg_dimensions(data)
            ocr = _ocr_image(data, filename or "image.jpg")
            text = ocr.extracted_text or (f"JPEG image {dims[0]}x{dims[1]}" if dims else "JPEG image")
            return ExtractionResult(ocr.status, text, mime, ocr.extractor, ocr.extractor_version, ocr.confidence, ocr.warnings, ocr.error_code, ocr.error_details, ocr.timeout, source_hash)
        if mime == "image/tiff":
            ocr = _ocr_image(data, filename or "image.tif")
            return ExtractionResult(ocr.status, ocr.extracted_text, mime, ocr.extractor, ocr.extractor_version, ocr.confidence, ocr.warnings, ocr.error_code, ocr.error_details, ocr.timeout, source_hash)
        if mime == "application/pdf":
            pdf = _extract_pdf_text(data)
            if pdf.extracted_text:
                return ExtractionResult("complete", pdf.extracted_text, mime, pdf.extractor, pdf.extractor_version, 0.9, pdf.warnings, None, None, pdf.timeout, source_hash)
            scanned = _ocr_scanned_pdf(data)
            if scanned.extracted_text:
                return ExtractionResult("complete", scanned.extracted_text, mime, scanned.extractor, scanned.extractor_version, scanned.confidence, pdf.warnings + scanned.warnings, None, None, scanned.timeout, source_hash)
            return ExtractionResult("error", "", mime, scanned.extractor, scanned.extractor_version, 0.0, pdf.warnings + scanned.warnings, scanned.error_code or "SCANNED_PDF_OCR_UNAVAILABLE", scanned.error_details, scanned.timeout, source_hash)
        if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            docx = _extract_docx_text(data)
            return ExtractionResult("complete", docx, mime, "docx_xml", "zipfile", 0.8, [], None, None, source_hash=source_hash)
        if mime == "audio/wav":
            return _transcribe_wav(data, source_hash)
        return ExtractionResult("unsupported", "", mime, "mime_detector", None, None, [], "UNSUPPORTED_TYPE", f"unsupported MIME type: {mime}", source_hash=source_hash)
    except Exception as exc:
        return ExtractionResult("error", "", mime, "contained_extractor", None, None, [], "MALFORMED_FILE", str(exc), source_hash=source_hash)


def _looks_text(data: bytes) -> bool:
    if not data:
        return True
    sample = data[:4096]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ValueError("missing PNG IHDR")
    return struct.unpack(">II", data[16:24])


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    idx = 2
    while idx + 9 < len(data):
        if data[idx] != 0xFF:
            idx += 1
            continue
        marker = data[idx + 1]
        idx += 2
        if marker in (0xC0, 0xC2):
            length = struct.unpack(">H", data[idx : idx + 2])[0]
            if idx + length <= len(data):
                height, width = struct.unpack(">HH", data[idx + 3 : idx + 7])
                return width, height
        else:
            length = struct.unpack(">H", data[idx : idx + 2])[0]
            idx += length
    return None


def _version(cmd: str) -> str | None:
    exe = shutil.which(cmd)
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=3)
        return (out.stdout or out.stderr).splitlines()[0][:120]
    except Exception:
        return exe


def _ocr_image(data: bytes, filename: str) -> ExtractionResult:
    from .ids import sha256_bytes

    tesseract = shutil.which("tesseract")
    source_hash = sha256_bytes(data)
    if not tesseract:
        return ExtractionResult("error", "", detect_mime(data, filename), "tesseract", None, 0.0, [], "OCR_ENGINE_UNAVAILABLE", "tesseract not installed", source_hash=source_hash)
    suffix = Path(filename).suffix or ".png"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / f"input{suffix}"
            image.write_bytes(data)
            proc = subprocess.run([tesseract, str(image), "stdout", "--psm", "6"], capture_output=True, text=True, timeout=15)
            if proc.returncode != 0:
                return ExtractionResult("error", "", detect_mime(data, filename), "tesseract", _version("tesseract"), 0.0, [], "OCR_FAILED", proc.stderr.strip(), source_hash=source_hash)
            text = proc.stdout.strip()
            return ExtractionResult("complete" if text else "no_text", text, detect_mime(data, filename), "tesseract", _version("tesseract"), 0.75 if text else 0.2, [] if text else ["OCR returned no text"], None, None, source_hash=source_hash)
    except subprocess.TimeoutExpired:
        return ExtractionResult("error", "", detect_mime(data, filename), "tesseract", _version("tesseract"), 0.0, [], "OCR_TIMEOUT", "tesseract timed out", True, source_hash)


def _extract_pdf_text(data: bytes) -> ExtractionResult:
    from .ids import sha256_bytes

    source_hash = sha256_bytes(data)
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                pdf = Path(tmp) / "input.pdf"
                out = Path(tmp) / "out.txt"
                pdf.write_bytes(data)
                proc = subprocess.run([pdftotext, "-layout", str(pdf), str(out)], capture_output=True, text=True, timeout=15)
                if proc.returncode == 0:
                    return ExtractionResult("complete", out.read_text(encoding="utf-8", errors="ignore").strip(), "application/pdf", "pdftotext", _version("pdftotext"), 0.9, [], None, None, source_hash=source_hash)
                literal = _extract_pdf_literal(data)
                if literal:
                    return ExtractionResult("complete", literal, "application/pdf", "pdf_literal_text", None, 0.55, ["pdftotext failed; literal fallback used"], None, None, source_hash=source_hash)
                return ExtractionResult("error", "", "application/pdf", "pdftotext", _version("pdftotext"), 0.0, [], "PDF_TEXT_FAILED", proc.stderr.strip(), source_hash=source_hash)
        except subprocess.TimeoutExpired:
            return ExtractionResult("error", "", "application/pdf", "pdftotext", _version("pdftotext"), 0.0, [], "PDF_TEXT_TIMEOUT", "pdftotext timed out", True, source_hash)
    text = _extract_pdf_literal(data)
    return ExtractionResult("complete" if text else "no_text", text, "application/pdf", "pdf_literal_text", None, 0.55 if text else 0.0, ["pdftotext unavailable"] if not pdftotext else [], None, None, source_hash=source_hash)


def _extract_pdf_literal(data: bytes) -> str:
    chunks = re.findall(rb"\(([^()]*)\)\s*Tj", data)
    return "\n".join(chunk.decode("latin-1", errors="ignore") for chunk in chunks).strip()


def _extract_docx_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        total = sum(info.file_size for info in zf.infolist())
        if total > MAX_EXTRACT_BYTES:
            raise ValueError("docx expanded size exceeds limit")
        if "word/document.xml" not in names:
            raise ValueError("docx missing word/document.xml")
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", xml)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _ocr_scanned_pdf(data: bytes) -> ExtractionResult:
    from .ids import sha256_bytes

    source_hash = sha256_bytes(data)
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return ExtractionResult("error", "", "application/pdf", "pdftoppm+tesseract", None, 0.0, [], "PDF_RASTERIZER_UNAVAILABLE", "pdftoppm not installed", source_hash=source_hash)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "input.pdf"
            prefix = Path(tmp) / "page"
            pdf.write_bytes(data)
            proc = subprocess.run([pdftoppm, "-png", "-r", "200", "-f", "1", "-l", "3", str(pdf), str(prefix)], capture_output=True, text=True, timeout=20)
            if proc.returncode != 0:
                return ExtractionResult("error", "", "application/pdf", "pdftoppm+tesseract", _version("pdftoppm"), 0.0, [], "PDF_RASTERIZE_FAILED", proc.stderr.strip(), source_hash=source_hash)
            texts = []
            for image in sorted(Path(tmp).glob("page-*.png")):
                ocr = _ocr_image(image.read_bytes(), image.name)
                if ocr.extracted_text:
                    texts.append(ocr.extracted_text)
            text = "\n".join(texts).strip()
            return ExtractionResult("complete" if text else "no_text", text, "application/pdf", "pdftoppm+tesseract", f"{_version('pdftoppm')} | {_version('tesseract')}", 0.7 if text else 0.2, [] if text else ["scanned PDF OCR returned no text"], None, None, source_hash=source_hash)
    except subprocess.TimeoutExpired:
        return ExtractionResult("error", "", "application/pdf", "pdftoppm+tesseract", _version("pdftoppm"), 0.0, [], "PDF_OCR_TIMEOUT", "scanned PDF OCR timed out", True, source_hash)


def _transcribe_wav(data: bytes, source_hash: str) -> ExtractionResult:
    whisper = shutil.which("whisper-cli")
    with wave.open(io.BytesIO(data)) as wav:
        duration = wav.getnframes() / float(wav.getframerate() or 1)
    if not whisper:
        return ExtractionResult("error", "", "audio/wav", "whisper-cpp", None, 0.0, [f"WAV duration {duration:.2f}s"], "TRANSCRIPTION_ENGINE_UNAVAILABLE", "whisper-cli is not installed", source_hash=source_hash)
    if not WHISPER_MODEL.exists():
        return ExtractionResult("error", "", "audio/wav", "whisper-cpp", _version("whisper-cli"), 0.0, [f"WAV duration {duration:.2f}s"], "TRANSCRIPTION_MODEL_UNAVAILABLE", f"missing model: {WHISPER_MODEL}", source_hash=source_hash)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "input.wav"
            out_base = Path(tmp) / "transcript"
            wav_path.write_bytes(data)
            proc = subprocess.run(
                [whisper, "-m", str(WHISPER_MODEL), "-f", str(wav_path), "-otxt", "-of", str(out_base), "-nt", "-np", "-t", "4", "--no-gpu"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            transcript_path = Path(str(out_base) + ".txt")
            text = transcript_path.read_text(encoding="utf-8", errors="ignore").strip() if transcript_path.exists() else proc.stdout.strip()
            if proc.returncode != 0:
                return ExtractionResult("error", "", "audio/wav", "whisper-cpp", _version("whisper-cli"), 0.0, [f"WAV duration {duration:.2f}s"], "TRANSCRIPTION_FAILED", proc.stderr.strip(), source_hash=source_hash)
            return ExtractionResult("complete" if text else "no_text", text, "audio/wav", "whisper-cpp", _version("whisper-cli"), 0.7 if text else 0.2, [f"WAV duration {duration:.2f}s"], None, None, source_hash=source_hash)
    except subprocess.TimeoutExpired:
        return ExtractionResult("error", "", "audio/wav", "whisper-cpp", _version("whisper-cli"), 0.0, [f"WAV duration {duration:.2f}s"], "TRANSCRIPTION_TIMEOUT", "whisper-cli timed out", True, source_hash)
