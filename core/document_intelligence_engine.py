import json
import os
from pathlib import Path
from typing import Any, Dict

import pdfplumber
import pytesseract
from PIL import Image
from openai import OpenAI


class DocumentIntelligenceEngine:
    """
    Analiza documentos e imágenes.
    - PDF: extrae texto
    - Imagen: OCR
    - TXT/MD/JSON/CSV: lectura directa
    - Devuelve resumen, riesgos, oportunidades y acciones
    """

    def __init__(self, analysis_dir: str = "data/document_analysis") -> None:
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.analysis_dir = Path(analysis_dir)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

    def _extract_pdf(self, path: str) -> str:
        chunks = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    chunks.append(text)
        return "\n".join(chunks).strip()

    def _extract_image(self, path: str) -> str:
        img = Image.open(path)
        return pytesseract.image_to_string(img).strip()

    def _extract_text_file(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8", errors="ignore").strip()

    def extract_text(self, path: str) -> str:
        lower = path.lower()

        if lower.endswith(".pdf"):
            return self._extract_pdf(path)

        if lower.endswith(".png") or lower.endswith(".jpg") or lower.endswith(".jpeg") or lower.endswith(".webp"):
            return self._extract_image(path)

        if lower.endswith(".txt") or lower.endswith(".md") or lower.endswith(".json") or lower.endswith(".csv"):
            return self._extract_text_file(path)

        return ""

    def analyze(self, path: str) -> Dict[str, Any]:
        text = self.extract_text(path)

        if not text:
            return {
                "status": "no_text_extracted",
                "path": path,
                "summary": None,
                "raw_text_preview": "",
            }

        prompt = f"""
You are a premium intelligence analyst for JARVIS OS.

Analyze this content and return a JSON object with:
- summary
- key_points
- risks
- opportunities
- recommended_actions

Content:
{text[:14000]}
"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=900,
        )

        content = (response.choices[0].message.content or "{}").strip()

        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {
                "summary": content,
                "key_points": [],
                "risks": [],
                "opportunities": [],
                "recommended_actions": [],
            }

        result = {
            "status": "ok",
            "path": path,
            "analysis": parsed,
            "raw_text_preview": text[:2000],
        }

        output_path = self.analysis_dir / (Path(path).stem + "_analysis.json")
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        return result