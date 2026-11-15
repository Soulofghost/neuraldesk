import io
import csv
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any

def parse_uploaded_file(filename: str, content_bytes: bytes) -> Dict[str, Any]:
    ext = Path(filename).suffix.lower()
    
    if ext in [".txt", ".md", ".markdown"]:
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin-1", errors="replace")
        return {"text": text.strip(), "file_type": "markdown" if ext in [".md", ".markdown"] else "text"}

    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            pages_text = []
            for i, page in enumerate(reader.pages):
                extracted = page.extract_text()
                if extracted:
                    pages_text.append(f"--- Page {i + 1} ---\n{extracted.strip()}")
            full_text = "\n\n".join(pages_text).strip()
            if not full_text:
                full_text = f"[PDF Document: {filename}] (Embedded visual content or scanned pages)"
            return {"text": full_text, "file_type": "pdf"}
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {e}")

    elif ext == ".docx":
        try:
            # DOCX is an OpenXML ZIP archive containing word/document.xml
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            # w:t elements contain text
            paragraphs = []
            for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                texts = [t.text for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if t.text]
                if texts:
                    paragraphs.append("".join(texts))
            full_text = "\n\n".join(paragraphs).strip()
            return {"text": full_text or f"[DOCX Document: {filename}]", "file_type": "docx"}
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX: {e}")

    elif ext in [".csv", ".tsv"]:
        try:
            decoded = content_bytes.decode("utf-8", errors="replace")
            delimiter = "\t" if ext == ".tsv" else ","
            reader = csv.reader(io.StringIO(decoded), delimiter=delimiter)
            rows = list(reader)
            if not rows:
                return {"text": "", "file_type": "csv"}
            header = rows[0]
            summary_lines = [f"Columns ({len(header)}): {', '.join(header)}", f"Total Records: {len(rows) - 1}"]
            # Include first 50 rows as formatted text
            for i, r in enumerate(rows[1:51], start=1):
                row_str = " | ".join(f"{h}: {val}" for h, val in zip(header, r) if val)
                summary_lines.append(f"Row {i}: {row_str}")
            return {"text": "\n".join(summary_lines), "file_type": "csv"}
        except Exception as e:
            raise ValueError(f"Failed to parse spreadsheet: {e}")

    elif ext == ".json":
        try:
            decoded = content_bytes.decode("utf-8", errors="replace")
            return {"text": decoded, "file_type": "json"}
        except Exception as e:
            raise ValueError(f"Failed to parse JSON file: {e}")

    else:
        raise ValueError(f"Unsupported file extension '{ext}'. Supported: .pdf, .docx, .md, .txt, .csv, .json")
