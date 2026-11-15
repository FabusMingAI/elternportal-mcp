"""PDF extraction worker. Invoked as a bounded subprocess, never as an MCP server."""

from __future__ import annotations

import io
import json
import sys


def extract(data: bytes) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf")
    texts, length = [], 0
    for page in reader.pages[:50]:
        text = (page.extract_text() or "")[:20000]
        texts.append(text)
        length += len(text)
        if length >= 200000:
            break
    text = "\n\n".join(texts)[:200000]
    return {
        "text": text,
        "pages": len(reader.pages),
        "ocr_required": not text.strip(),
        "truncated": len(reader.pages) > len(texts) or length >= 200000,
    }


def main():
    try:
        if sys.platform != "win32":
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
            resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        data = sys.stdin.buffer.read(25 * 1024**2 + 1)
        if len(data) > 25 * 1024**2:
            raise ValueError("pdf_too_large")
        result = extract(data)
    except Exception:
        result = {"error": "pdf_extraction_failed"}
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
