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
class MarkdownParser(TextParser):
    def parse_layout(self,data,filename=""):
        import re
        from .layout import ParsedSpan,LayoutParseResult
        from ...contracts.anchors import SelectorKind,SectionQuoteSelector,digest
        text=self.parse(data);spans=[];headings={};offset=0;block_start=None;block_end=None;fence=None
        def flush():
            nonlocal block_start,block_end
            if block_start is not None:
                body=text[block_start:block_end]
                if body.strip():
                    selector=SectionQuoteSelector(tuple(headings[k] for k in sorted(headings)),digest(body),block_start,block_end)
                    spans.append(ParsedSpan(body,block_start,block_end,SelectorKind.SECTION_QUOTE,section_quote=selector))
            block_start=block_end=None
        for line in text.splitlines(keepends=True):
            body=line.rstrip("\r\n");heading=re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*#*\s*$",body) if fence is None else None
            marker=re.match(r"^ {0,3}(`{3,}|~{3,})",body)
            if marker:
                if fence is None:fence=marker[1][0]
                elif marker[1][0]==fence:fence=None
            if heading:
                flush();level=len(heading[1]);headings={k:v for k,v in headings.items() if k<level};headings[level]=heading[2]
            elif not body.strip():flush()
            else:
                if fence is None and re.match(r"^\s*(?:[-+*]|[0-9]+[.)])[ \t]+",body):flush()
                if block_start is None:block_start=offset
                block_end=offset+len(body)
            offset+=len(line)
        flush()
        return LayoutParseResult(text,tuple(spans),"markdown-stdlib","1.0")


class _HTML(BaseHTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0;self.position=0;self.headings=[];self.active_heading=None
    def append(self,value):self.parts.append(value);self.position+=len(value)
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.hidden+=1
        if tag in ("p","div","br","h1","h2","h3","li","tr"):self.append("\n")
        if not self.hidden and len(tag)==2 and tag[0]=='h' and tag[1] in '123456':
            self.active_heading=(int(tag[1]),self.position)
    def handle_endtag(self,tag):
        if self.active_heading and tag=='h'+str(self.active_heading[0]):
            level,start=self.active_heading;self.headings.append((start,self.position,level));self.active_heading=None
        if tag in ("script","style"):self.hidden=max(0,self.hidden-1)
        if tag in ("p","div","li"):self.append("\n")
    def handle_data(self,text):
        if not self.hidden:self.append(text)


class HTMLParser:
    def parse(self,data):
        parser=_HTML();parser.feed(TextParser().parse(data));return "".join(parser.parts).strip()
    def parse_layout(self,data,filename=""):
        import re
        from .layout import ParsedSpan,LayoutParseResult
        from ...contracts.anchors import SelectorKind,SectionQuoteSelector,digest
        parser=_HTML();parser.feed(TextParser().parse(data));raw="".join(parser.parts);text=raw.strip()
        trim=len(raw)-len(raw.lstrip());headings=[];paths={};events=[]
        for start,end,level in sorted(parser.headings):
            paths={k:v for k,v in paths.items() if k<level}
            title=raw[start:end].strip()
            if title:paths[level]=title
            a=max(0,start-trim);b=min(len(text),end-trim)
            if a<b:headings.append((a,b))
            events.append((b,tuple(paths[k] for k in sorted(paths))))
        spans=[]
        for line in re.finditer(r'[^\r\n]+',text):
            intervals=[(line.start(),line.end())]
            for a,b in headings:
                intervals=[piece for x,y in intervals for piece in ((x,min(y,a)),(max(x,b),y)) if piece[0]<piece[1]] if any(a<y and b>x for x,y in intervals) else intervals
            for a,b in intervals:
                body=text[a:b]
                if not body.strip():continue
                path=()
                for pos,candidate in events:
                    if pos<=a:path=candidate
                selector=SectionQuoteSelector(path,digest(body),a,b)
                spans.append(ParsedSpan(body,a,b,SelectorKind.SECTION_QUOTE,section_quote=selector))
        return LayoutParseResult(text,tuple(spans),"html-stdlib","1.0")


def excel_col(number):
    result=""
    while number:
        number,remainder=divmod(number-1,26);result=chr(65+remainder)+result
    return result


class CSVParser:
    def parse(self,data):
        return "\n".join(" | ".join(row) for row in csv.reader(io.StringIO(TextParser().parse(data))))
    def parse_layout(self,data,filename=""):
        from pathlib import Path
        from .layout import ParsedSpan,LayoutParseResult
        from ...contracts.anchors import SelectorKind,TableCellSelector
        rows=list(csv.reader(io.StringIO(TextParser().parse(data))))
        parts=[" | ".join(row) for row in rows];text="\n".join(parts)
        headers=None;unit_index=None;spans=[];offset=0;data_row=0
        for row,body in zip(rows,parts):
            nonempty=bool(row) and any(cell.strip() for cell in row)
            if nonempty and headers is None:
                headers=tuple(([row[0].lstrip('\ufeff')]+row[1:]))
                unit_index=next((i for i,h in enumerate(headers) if h.strip().lower() in ('unit','units')),None)
            elif nonempty:
                data_row+=1
                selector=TableCellSelector(Path(filename).stem or 'default',data_row,data_row,headers or (),
                                           'A'+str(data_row+1)+':'+excel_col(len(row))+str(data_row+1),
                                           row[unit_index] if unit_index is not None and unit_index<len(row) else '')
                spans.append(ParsedSpan(body,offset,offset+len(body),SelectorKind.TABLE_CELL,table_cell=selector))
            offset+=len(body)+1
        return LayoutParseResult(text,tuple(spans),"csv-stdlib","1.0")


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
