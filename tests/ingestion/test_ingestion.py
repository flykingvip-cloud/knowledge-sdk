from __future__ import annotations
import io
import zipfile
from knowledge_sdk import *
from knowledge_sdk.ingestion.parsers import ParserRegistry
from knowledge_sdk.ingestion.chunkers import FixedChunker, HierarchicalChunker
from knowledge_sdk.ingestion.chunkers.delta import chunk_delta
from knowledge_sdk.ingestion.fingerprint import fingerprints, classify
from tests.helpers import ClientCase
class IngestionTests(ClientCase):
    def test_raw_dedup(self):
        v=self.c.ingest(self.a,self.k.kb_id,self.v.text,filename="guide.md",doc_id=self.v.doc_id)
        self.assertEqual(v.version,1)
    def test_semantic_dedup(self):
        v=self.c.ingest(self.a,self.k.kb_id,self.v.text.replace(" ","  "),doc_id=self.v.doc_id)
        self.assertEqual(v.version,1)
        self.assertEqual(classify(self.v,*fingerprints(b"different",self.v.text)),"raw_only")
    def test_new_immutable_version(self):
        v=self.c.ingest(self.a,self.k.kb_id,"second",doc_id=self.v.doc_id)
        self.assertEqual(v.version,2); self.assertEqual(self.c.get_document(self.a,v.doc_id,1).text,self.v.text)
    def test_empty_and_unknown_format(self):
        for text,filename in [(" ","a.txt"),("x","a.exe")]:
            with self.assertRaises(ValidationError): self.c.ingest(self.a,self.k.kb_id,text,filename)
    def test_invalid_utf8(self):
        with self.assertRaises(ValidationError): self.c.ingest(self.a,self.k.kb_id,b"\xff")
    def test_text_markdown(self):
        r=ParserRegistry.defaults(); self.assertEqual(r.parse(b"# Heading","a.md"),"# Heading")
        self.assertEqual(r.parse(b"\xef\xbb\xbfhello","a.txt"),"hello")
    def test_html_ignores_scripts(self):
        text=ParserRegistry.defaults().parse(b"<h1>Hello</h1><script>secret</script><p>A &amp; B</p>","a.html")
        self.assertIn("A & B",text); self.assertNotIn("secret",text)
    def test_csv_quoted_fields(self):
        text=ParserRegistry.defaults().parse(b'name,value\n"hello, world",2',"a.csv")
        self.assertIn("hello, world | 2",text)
    def test_pdf_graceful_failure(self):
        with self.assertRaises(ValidationError): ParserRegistry.defaults().parse(b"not a PDF","a.pdf")
    def test_office_formats(self):
        fixtures={
            "docx":{"word/document.xml":'<w:document xmlns:w="word"><w:p><w:r><w:t>Document title</w:t></w:r></w:p></w:document>'},
            "pptx":{"ppt/slides/slide2.xml":'<p xmlns:a="drawing"><a:p><a:r><a:t>Slide two</a:t></a:r></a:p></p>',"ppt/slides/slide1.xml":'<p xmlns:a="drawing"><a:p><a:r><a:t>Slide one</a:t></a:r></a:p></p>'},
            "xlsx":{"xl/sharedStrings.xml":'<sst><si><t>Shared cell</t></si></sst>',"xl/worksheets/sheet1.xml":'<worksheet><row><c t="s"><v>0</v></c><c><v>42</v></c><c t="inlineStr"><is><t>Inline</t></is></c></row></worksheet>'}}
        for ext,files in fixtures.items():
            data=io.BytesIO()
            with zipfile.ZipFile(data,"w") as z:
                for name,text in files.items(): z.writestr(name,text)
            text=ParserRegistry.defaults().parse(data.getvalue(),"a."+ext)
            self.assertTrue(text)
            if ext=="pptx": self.assertLess(text.index("one"),text.index("two"))
            if ext=="xlsx": self.assertIn("Shared cell | 42 | Inline",text)
    def test_office_invalid(self):
        with self.assertRaises(ValidationError): ParserRegistry.defaults().parse(b"x","a.docx")
    def test_custom_parser(self):
        class Custom:
            def parse(self,data): return "custom"
        r=ParserRegistry(); r.register(["custom"],Custom()); self.assertEqual(r.parse(b"x","a.custom"),"custom")
    def test_fixed_offsets_and_overlap(self):
        text="😀abcdefghijk"; chunks=FixedChunker(5,2).split(text,"doc",1)
        self.assertEqual(chunks[0].text[-2:],chunks[1].text[:2])
        for c in chunks: self.assertEqual(text[c.start_offset:c.end_offset],c.text)
    def test_chunk_invalid_config(self):
        for args in [(0,0),(5,5),(5,-1)]:
            with self.assertRaises(ValidationError): FixedChunker(*args)
    def test_heading_paths_and_delta(self):
        h=HierarchicalChunker(); text="# A\nText\n## B\nDetail"
        chunks=h.split(text,"doc",1)
        self.assertEqual(chunks[1].section_path,["A","B"])
        self.assertEqual(chunks[1].text,text[chunks[1].start_offset:chunks[1].end_offset])
        newer=h.split(text+" changed","doc",2); delta=chunk_delta(chunks,newer)
        self.assertEqual(len(delta["unchanged"]),1); self.assertEqual(len(delta["added"]),1); self.assertEqual(len(delta["removed"]),1)
