from __future__ import annotations
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Protocol
from ...exceptions import ValidationError
class OCRHook(Protocol):
    def extract(self, data: bytes, filename: str) -> str: ...
class OfficeParser:
    """Text-only OOXML extraction. No macros, formulas or external links executed."""
    def __init__(self, kind): self.kind=kind
    def parse(self,data):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if sum(i.file_size for i in z.infolist()) > 64*1024*1024 or len(z.infolist()) > 10000:
                    raise ValidationError("Office archive exceeds safety limits")
                names=z.namelist()
                if self.kind=="docx": paths=["word/document.xml"]
                elif self.kind=="pptx": paths=sorted((n for n in names if re.fullmatch(r"ppt/slides/slide[0-9]+.xml",n)), key=lambda n:int(re.search(r"slide([0-9]+)",n)[1]))
                else: paths=sorted((n for n in names if re.fullmatch(r"xl/worksheets/sheet[0-9]+.xml",n)),key=lambda n:int(re.search(r"sheet([0-9]+)",n)[1]))
                def tree(p):
                    raw=z.read(p)
                    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw: raise ValidationError("DTD forbidden")
                    return ET.fromstring(raw)
                shared=[]
                if self.kind=="xlsx" and "xl/sharedStrings.xml" in names:
                    shared=["".join(e.itertext()) for e in tree("xl/sharedStrings.xml")]
                result=[]
                for p in paths:
                    root=tree(p)
                    if self.kind=="xlsx":
                        for row in root.iter():
                            if row.tag.split("}")[-1]!="row": continue
                            values=[]
                            for cell in row:
                                v=next((c.text or "" for c in cell if c.tag.split("}")[-1]=="v"),"")
                                if cell.get("t")=="s": v=shared[int(v)] if v else ""
                                elif cell.get("t")=="inlineStr": v="".join(cell.itertext())
                                values.append(v)
                            result.append(" | ".join(values))
                    else:
                        # Preserve paragraph boundaries instead of running words together.
                        for e in root.iter():
                            if e.tag.split("}")[-1]=="p":
                                result.append("".join(n.text or "" for n in e.iter() if n.tag.split("}")[-1]=="t"))
                text="\n".join(result).strip()
                if not text: raise ValidationError("Office document contains no extractable text")
                return text
        except (zipfile.BadZipFile,KeyError,ET.ParseError,ValueError,IndexError) as exc:
            raise ValidationError("Invalid Office document") from exc
