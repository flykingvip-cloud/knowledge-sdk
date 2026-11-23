from __future__ import annotations
from knowledge_sdk import *
from knowledge_sdk.retrieval.excerpt import make_excerpt
from knowledge_sdk.ingestion.chunkers import FixedChunker
from tests.helpers import ClientCase
class ExcerptTests(ClientCase):
    def test_default_800_budget(self):
        e=make_excerpt("a"*1000)
        self.assertEqual(len(e["excerpt"]),800); self.assertTrue(e["truncated"]); self.assertEqual(e["remaining_chars"],200)
    def test_enterprise_1600_budget(self):
        e=make_excerpt("中"*2000,enterprise=True)
        self.assertEqual(len(e["excerpt"]),1600); self.assertEqual(e["remaining_chars"],400)
    def test_unicode_safety(self):
        e=make_excerpt("😀"*900); self.assertEqual(e["excerpt"].encode().decode(),"😀"*800)
    def test_normalization_before_budget(self):
        self.assertEqual(make_excerpt("  A\n B\t C  ")["excerpt"],"A B C")
    def test_denied_is_fail_closed(self):
        e=make_excerpt("SECRET"*1000,allowed=False,query="SECRET",partial_notice="sensitive")
        self.assertEqual(e["excerpt"],""); self.assertEqual(e["highlights"],[]); self.assertEqual(e["remaining_chars"],0)
        self.assertEqual(e["partial_notice"],""); self.assertTrue(e["masking_summary"])
    def test_notices_and_highlights(self):
        e=make_excerpt("Hello knowledge",query="knowledge",partial_notice="Incomplete",masking_summary="Two fields removed")
        self.assertEqual(e["highlights"],[[6,15]]); self.assertEqual(e["partial_notice"],"Incomplete"); self.assertTrue(e["masking_summary"])
    def test_search_preview_and_paged_read_are_separate(self):
        self.c.chunker=FixedChunker(5000,0)
        text="knowledge "+"😀"*2000
        v=self.c.ingest(self.a,self.k.kb_id,text)
        hit=next(h for h in self.c.search(self.a,"knowledge").hits if h.doc_id==v.doc_id)
        self.assertEqual(len(hit.excerpt),800); self.assertTrue(hit.truncated)
        pages=[]; offset=0
        while True:
            page=self.c.retrieve(self.a,v.doc_id,offset=offset,limit=127); pages.append(page.text)
            if page.next_offset is None: break
            offset=page.next_offset
        self.assertEqual("".join(pages),text)
    def test_invalid_pagination(self):
        for offset,limit in [(-1,5),(0,0),(0,100001)]:
            with self.assertRaises(ValidationError): self.c.retrieve(self.a,self.v.doc_id,offset=offset,limit=limit)
    def test_empty_page_at_end(self):
        page=self.c.retrieve(self.a,self.v.doc_id,offset=100000)
        self.assertEqual(page.text,""); self.assertFalse(page.truncated)
    def test_custom_policy(self):
        self.assertEqual(make_excerpt("abcdef",ExcerptPolicy(3,4))["excerpt"],"abc")
        with self.assertRaises(ValidationError): ExcerptPolicy(0,4)
