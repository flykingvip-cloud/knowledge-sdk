from __future__ import annotations
from typing import Protocol
from pathlib import Path
from ...exceptions import ValidationError
class Parser(Protocol):
    def parse(self, data: bytes) -> str: ...
class ParserRegistry:
    def __init__(self): self.parsers = {}
    def register(self, extensions, parser):
        for ext in extensions: self.parsers[ext.lower().lstrip(".")] = parser
    def parse(self, data, filename):
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in self.parsers: raise ValidationError("Unsupported format: " + ext)
        return self.parsers[ext].parse(data)
    @classmethod
    def defaults(cls):
        from .builtin import TextParser, HTMLParser, CSVParser, PDFParser
        from .office import OfficeParser
        r = cls(); r.register(["txt","md","markdown"],TextParser()); r.register(["html","htm"],HTMLParser())
        r.register(["csv"],CSVParser()); r.register(["pdf"],PDFParser())
        for ext in ("docx","pptx","xlsx"): r.register([ext],OfficeParser(ext))
        return r
