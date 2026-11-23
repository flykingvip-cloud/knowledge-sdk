from __future__ import annotations
import csv
import io
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser as BaseHTMLParser
from ...exceptions import ValidationError
class TextParser:
    def parse(self, data):
        try: return data.decode("utf-8-sig")
        except UnicodeDecodeError as exc: raise ValidationError("Expected UTF-8 text") from exc
class _HTML(BaseHTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.parts=[]; self.hidden=0
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style"): self.hidden+=1
        if tag in ("p","div","br","h1","h2","h3","li","tr"): self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script","style"): self.hidden=max(0,self.hidden-1)
        if tag in ("p","div","li"): self.parts.append("\n")
    def handle_data(self, text):
        if not self.hidden: self.parts.append(text)
class HTMLParser:
    def parse(self, data):
        parser=_HTML(); parser.feed(TextParser().parse(data)); return "".join(parser.parts).strip()
class CSVParser:
    def parse(self,data):
        return "\n".join(" | ".join(row) for row in csv.reader(io.StringIO(TextParser().parse(data))))
class PDFParser:
    """No silent binary-to-text fallback. Scans require an explicit OCR plugin."""
    def parse(self,data):
        if shutil.which("pdftotext"):
            with tempfile.TemporaryDirectory() as tmp:
                from pathlib import Path
                path=Path(tmp)/"input.pdf"; path.write_bytes(data)
                try:
                    result=subprocess.run(["pdftotext","-layout",str(path),"-"],capture_output=True,timeout=60)
                    if result.returncode==0:
                        text=result.stdout.decode("utf-8").strip()
                        if text: return text
                except (subprocess.SubprocessError,UnicodeDecodeError): pass
        try:
            from pypdf import PdfReader
            text="\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages).strip()
            if text: return text
        except ImportError: pass
        except Exception as exc: raise ValidationError("Invalid or unreadable PDF") from exc
        raise ValidationError("PDF text unavailable; install pdftotext/pypdf or register OCR parser")
