from __future__ import annotations
from typing import Protocol
from pathlib import Path
from ...exceptions import ValidationError
from .layout import LayoutParser, LayoutParseResult, ParsedSpan, text_layout
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
    def parse_layout(self,data,filename=""):
        if not isinstance(data,bytes) or not isinstance(filename,str): raise ValidationError("Invalid parser input")
        ext=Path(filename).suffix.lower().lstrip(".")
        if ext not in self.parsers:raise ValidationError("Unsupported format: "+ext)
        parser=self.parsers[ext]
        if callable(getattr(parser,"parse_layout",None)):
            result=parser.parse_layout(data,filename)
            if not isinstance(result,LayoutParseResult):raise ValidationError("Expected LayoutParseResult")
            # Revalidate at the plugin boundary, even if a hostile mutable plugin
            # used object.__setattr__ on an otherwise frozen result.
            return LayoutParseResult(result.full_text,result.spans,result.parser_id,result.parser_version,result.warnings)
        return text_layout(parser.parse(data),type(parser).__name__,"1.0")

    @classmethod
    def defaults(cls):
        from .builtin import TextParser, MarkdownParser, HTMLParser, CSVParser, PDFParser
        from .office import OfficeParser
        r = cls(); r.register(["txt"],TextParser()); r.register(["md","markdown"],MarkdownParser()); r.register(["html","htm"],HTMLParser())
        r.register(["csv"],CSVParser()); r.register(["pdf"],PDFParser())
        for ext in ("docx","pptx","xlsx"): r.register([ext],OfficeParser(ext))
        return r
