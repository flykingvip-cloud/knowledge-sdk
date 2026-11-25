import unittest
from knowledge_sdk import LocalKnowledgeClient, Actor, ValidationError
from knowledge_sdk.ingestion.parsers import ParserRegistry
from knowledge_sdk.ingestion.chunkers.hierarchical import HierarchicalChunker
from knowledge_sdk.ingestion.fingerprint import normalize_text

WHITESPACE = ''.join(chr(n) for n in range(0x110000) if chr(n).isspace())
INPUTS = [('extreme.txt', '超长Cafe\u0301' * 2000),
          ('nested.md', '# A\n## B\n### C\n| A | B |\n|---|---|\n| 嵌套 <table><tr><td>x</td></tr></table> | y |\n\n' + 'word ' * 2000),
          ('data.csv', 'name,value\r\n"临床,研究","Cafe\u0301\n第二行"\r\n'),
          ('unicode.txt', 'A' + WHITESPACE + 'B\ufeffC Cafe\u0301 临床')]


class ParserEdges(unittest.TestCase):
    def test_deterministic_extremes_and_offsets(self):
        registry=ParserRegistry.defaults();chunker=HierarchicalChunker(size=100,overlap=10)
        self.assertEqual(len(WHITESPACE),29)
        for filename,text in INPUTS:
            with self.subTest(filename=filename):
                layout=registry.parse_layout(text.encode(),filename)
                self.assertEqual(layout,registry.parse_layout(text.encode(),filename))
                chunks=chunker.split(layout.full_text,'fixed-doc',1)
                self.assertTrue(chunks)
                self.assertEqual(chunks,chunker.split(layout.full_text,'fixed-doc',1))
                for c in chunks:
                    self.assertEqual(c.text,layout.full_text[c.start_offset:c.end_offset]);self.assertTrue(c.text.strip());self.assertLessEqual(len(c.text),100)
        self.assertEqual(normalize_text('A'+WHITESPACE+'B\ufeffC'),'A B\ufeffC')
    def test_invalid_truncated_and_oversized_fail_closed(self):
        registry=ParserRegistry.defaults()
        for filename,raw in [('x.txt',b'\xe4\xb8'),('x.md',b'\xff'),('x.csv',b'a,b\n"unterminated,x'),('x.csv',b'a\n'+b'x'*140000),('x.txt',b'x'*(32*1024*1024+1))]:
            with self.subTest(filename=filename,size=len(raw)),self.assertRaises(ValidationError):registry.parse_layout(raw,filename)
    def test_empty_no_garbage_or_side_effects(self):
        c=LocalKnowledgeClient();self.addCleanup(c.store.close);a=Actor('a','t');c.create_kb(a,'k',kb_id='k')
        for text in ('',WHITESPACE):
            with self.assertRaises(ValidationError):c.ingest(a,'k',text,doc_id='d')
            self.assertFalse(c.list_documents(a,'k'))
            self.assertEqual(HierarchicalChunker().split(text,'d',1),[])
        with self.assertRaises(ValidationError):c.ingest(a,'k','\ud800',doc_id='d')
