"""B02 uses an offline, injected layout fixture, NOT a PDF/OCR implementation."""
import json
import unittest
from dataclasses import replace,FrozenInstanceError
from knowledge_sdk import *
from knowledge_sdk.contracts.anchors import digest
from knowledge_sdk.contracts.models import encode,decode
from knowledge_sdk.contracts.uri import build_uri,parse_uri,parse_uri_v2
from knowledge_sdk.ingestion.parsers import ParserRegistry
from knowledge_sdk.ingestion.parsers.builtin import TextParser,HTMLParser,CSVParser
from knowledge_sdk.contracts.reanchor import merge_anchors_for_version


class OfflinePDFLayout:
    """Host-provided deterministic layout fixture; bytes are JSON, not PDF."""
    def parse_layout(self,data,filename=''):
        payload=json.loads(data);text=payload['text'];page=payload.get('page',1)
        span=ParsedSpan(text,0,len(text),SelectorKind.PDF_BBOX,pdf_bbox=PdfBBoxSelector(page,.1,.2,.8,.4))
        return LayoutParseResult(text,(span,),'offline-host-layout-fixture','1.0')


class AnchorContracts(unittest.TestCase):
    def test_uri_roundtrip_opaque_quoted_ids(self):
        for oid,did,aid in [('org','doc','anchor'),('租户 /%','文档?#','锚 %2F/#?')]:
            uri=build_uri(oid,did,1,anchor_id=aid);parsed=parse_uri_v2(uri)
            self.assertEqual((parsed.org_id,parsed.doc_id,parsed.version,parsed.anchor_id),(oid,did,1,aid))
            with self.assertRaises(ValidationError):parse_uri(uri)
    def test_legacy_bare_chunk_unchanged(self):
        for uri,expected in [('kb://org/org/doc/doc@1',('org','doc',1,None)),('kb://org/o/doc/d@2#chunk=c%2F1',('o','d',2,'c/1'))]:
            self.assertEqual(parse_uri(uri),expected)
            self.assertEqual(parse_uri_v2(uri).chunk_id,expected[3])
        self.assertEqual(build_uri('o','d',1,''),'kb://org/o/doc/d@1')
    def test_bad_uri_redteam(self):
        for uri in ['kb://org/o/doc/d@0','kb://org/o/doc/d@-1','kb://org/o/doc/d@01','kb://org//doc/d@1','kb://org/o/doc/@1','kb://org/o/doc/d@1#','kb://org/o/doc/d@1#anchor=',
                    'kb://org/o/doc/d@1#anchor=a#chunk=c','kb://org/o/doc/d@1#chunk=a&anchor=b','kb://org/o /doc/d@1','kb://org/o/doc/d@1#anchor=%ZZ','kb://org/o/doc/d@1#anchor=%00','kb://org/o/doc/d@1#anchor=%FF','kb://org/o/doc/d@1#anchor=%41']:
            with self.subTest(uri=uri),self.assertRaises(ValidationError):parse_uri_v2(uri)
        with self.assertRaises(ValidationError):build_uri('o','d',1,'c',anchor_id='a')
        with self.assertRaises(ValidationError):build_uri('o','d',True)
    def test_quote_preserves_whitespace(self):
        self.assertEqual(TextQuoteSelector('  \n ').exact,'  \n ')
        for value in ('',None,False,[]):
            with self.assertRaises(ValidationError):TextQuoteSelector(value)
    def test_bbox_strict_boundaries(self):
        self.assertEqual(PdfBBoxSelector(1,0,0,1,1).x1,1)
        for args in [(True,0,0,1,1),(0,0,0,1,1),(1,False,0,1,1),(1,float('nan'),0,1,1),(1,0,0,float('inf'),1),(1,.8,0,.2,1),(1,0,1,1,0),(1,-.1,0,1,1)]:
            with self.subTest(args=args),self.assertRaises(ValidationError):PdfBBoxSelector(*args)
    def test_table_section_strict_types(self):
        for kw in ({'row_start':True},{'row_end':0},{'row_start':2},{'col_headers':'x'},{'col_headers':[False]},{'unit_hint':[]}):
            with self.assertRaises(ValidationError):TableCellSelector(**kw)
        for kw in ({'section_path':'x'},{'start_offset':True},{'start_offset':2,'end_offset':1},{'paragraph_hash':False}):
            with self.assertRaises(ValidationError):SectionQuoteSelector(**kw)
    def test_anchor_requires_matching_selector_and_exact_hash(self):
        args=('a','o','d',1,SelectorKind.PDF_BBOX,TextQuoteSelector('exact'),digest('exact'))
        with self.assertRaises(ValidationError):EvidenceAnchor(*args)
        a=EvidenceAnchor(*args,pdf_bbox=PdfBBoxSelector(1,0,0,1,1))
        for kw in ({'quote_sha256':'0'*64},{'version':True},{'org_id':''},{'table_cell':TableCellSelector()},{'metadata':[]}):
            with self.assertRaises(ValidationError):replace(a,**kw)
    def test_metadata_deep_frozen_and_all_json_roundtrips(self):
        raw={'nested':{'values':['secret',1]}}
        a=EvidenceAnchor('a','o','d',1,SelectorKind.PDF_BBOX,TextQuoteSelector('exact'),digest('exact'),pdf_bbox=PdfBBoxSelector(1,0,0,1,1),metadata=raw)
        raw['nested']['values'][0]='changed';self.assertEqual(a.metadata['nested']['values'][0],'secret')
        with self.assertRaises(TypeError):a.metadata['nested']['values'][0]='bad'
        with self.assertRaises(FrozenInstanceError):a.version=2
        objects=[a,a.quote,a.pdf_bbox,TableCellSelector(col_headers=['a']),SectionQuoteSelector(['h']),ParsedKBURI('o','d',1,anchor_id='a')]
        layout=ParserRegistry.defaults().parse_layout(b'# H\n\nbody','x.md');objects.extend([layout,layout.spans[0]])
        for value in objects:
            self.assertEqual(decode(json.loads(json.dumps(encode(value)))),value)
            self.assertEqual(type(value).from_dict(json.loads(json.dumps(value.to_dict()))),value)
        self.assertEqual(EvidenceAnchor.from_dict(a.to_dict()),a)
    def test_layout_rejects_bad_plugin_offsets_and_type(self):
        with self.assertRaises(ValidationError):ParsedSpan('x',True,2,SelectorKind.TEXT_OFFSET)
        span=ParsedSpan('x',0,1,SelectorKind.TEXT_OFFSET)
        with self.assertRaises(ValidationError):LayoutParseResult('y',(span,),'p','1')
        class Bad:
            def parse_layout(self,*args):return 'not-layout'
        registry=ParserRegistry();registry.register(['bad'],Bad())
        with self.assertRaises(ValidationError):registry.parse_layout(b'x','x.bad')
    def test_csv_scientific_fields_bom_newline_blank_and_unicode(self):
        raw='\ufeff化合物,activity,units\nA,>10000,nM\n\nB,inactive,mg/kg\n"C\nD",<0.01,nM\n'.encode()
        p=ParserRegistry.defaults();r=p.parse_layout(raw,'研究.csv');self.assertEqual(r.full_text,p.parse(raw,'研究.csv'))
        self.assertEqual(len(r.spans),3)
        for idx,s in enumerate(r.spans,1):
            self.assertEqual((s.table_cell.row_start,s.table_cell.cell_ref),(idx,'A%d:C%d'%(idx+1,idx+1)))
            self.assertEqual(s.table_cell.col_headers,('化合物','activity','units'))
            self.assertEqual(s.table_cell.sheet_name,'研究')
        self.assertEqual(r.spans[0].text,'A | >10000 | nM');self.assertEqual(r.spans[1].table_cell.unit_hint,'mg/kg')
        self.assertEqual(r.spans[2].text,'C\nD | <0.01 | nM')
    def test_markdown_html_preserve_old_parse_and_paths(self):
        p=ParserRegistry.defaults()
        for filename,text,legacy in [('x.md','# Policy\n\n  inactive >10000 nM  \n\n## Lab\n- do not export\n',TextParser()),('x.html','<h1>Policy</h1><p>inactive &gt;10000 nM</p><h2>Lab</h2><ul><li>do not export</li></ul><script>hidden</script>',HTMLParser())]:
            layout=p.parse_layout(text.encode(),filename);self.assertEqual(layout.full_text,legacy.parse(text.encode()))
            self.assertEqual(layout.spans[-1].section_quote.section_path,('Policy','Lab'))
            for span in layout.spans:self.assertEqual(digest(span.text),span.section_quote.paragraph_hash)
    def test_legacy_parser_fallback_and_layout_only_plugin(self):
        class Legacy:
            def parse(self,data):return '  first  \n\nsecond\n'
        r=ParserRegistry();r.register(['old'],Legacy());layout=r.parse_layout(b'x','x.old')
        self.assertEqual(layout.full_text,r.parse(b'x','x.old'));self.assertEqual(len(layout.spans),2)
        r.register(['pdf'],OfflinePDFLayout());payload=json.dumps({'text':'policy'}).encode()
        self.assertEqual(r.parse(payload,'x.pdf'),r.parse_layout(payload,'x.pdf').full_text)
    def test_new_model_fields_defaults_and_types(self):
        self.assertEqual(KnowledgeRef('o','d',1,'kb://org/o/doc/d@1').anchor_id,'')
        self.assertFalse(SearchResponse([],'keyword').candidate_budget_exhausted)
        with self.assertRaises(ValidationError):SearchResponse([],'keyword',candidate_budget_exhausted=1)
        with self.assertRaises(ValidationError):KnowledgeRef('o','d',1,'kb://org/o/doc/d@1',anchor_id=False)


class AnchorClientTests(unittest.TestCase):
    def setUp(self):
        self.c=LocalKnowledgeClient();self.addCleanup(self.c.store.close);self.admin=Actor('admin','o');self.user=Actor('reader','o')
        self.k=self.c.create_kb(self.admin,'policies','enterprise',kb_id='kb')
    def ingest(self,text,name='x.md',**kwargs):return self.c.ingest(self.admin,'kb',text,name,**kwargs)
    def test_b02_offline_pdf_bbox_policy_and_redaction(self):
        self.c.parsers.register(['pdf'],OfflinePDFLayout())
        v=self.ingest(json.dumps({'text':'Internal secret >10000 nM'}).encode(),'fixture.pdf',rights=ResourceRights(redaction_profile='pii'))
        with self.assertRaisesRegex(PermissionDeniedError,'redaction_hook_missing'):self.c.list_anchors(self.user,v.doc_id)
        self.c.redaction_registry.register('pii',RegexRedactionHook([('secret','[MASK]')]))
        a=self.c.list_anchors(self.user,v.doc_id)[0];self.assertEqual(a.pdf_bbox.page_no,1);self.assertIn('[MASK]',a.quote.exact)
        with self.assertRaisesRegex(PermissionDeniedError,'external_llm_prohibited'):self.c.list_anchors(self.user,v.doc_id,purpose=Purpose.GROUND_EXTERNAL_LLM)
    def test_reanchor_unchanged_duplicate_confirm_and_new_span(self):
        v=self.ingest('# H\n\nalpha exact\n\nbeta old');old={a.quote.exact:a for a in self.c.list_anchors(self.admin,v.doc_id)}
        v2=self.ingest('# H\n\nalpha exact\n\nbeta old\n\nbeta old\n\ngenuinely new',doc_id=v.doc_id)
        anchors=self.c.list_anchors(self.admin,v.doc_id);self.assertEqual(len(anchors),3)
        a=self.c.get_anchor(self.admin,v.doc_id,old['alpha exact'].anchor_id);self.assertEqual(a.reanchor_status,ReanchorStatus.ANCHORED)
        pending=self.c.get_anchor(self.admin,v.doc_id,old['beta old'].anchor_id);self.assertEqual(pending.reanchor_status,ReanchorStatus.DRIFT_PENDING)
        with self.assertRaisesRegex(PermissionDeniedError,'anchor_drift_pending'):self.c.reference(self.admin,v.doc_id,anchor_id=pending.anchor_id)
        forged=KnowledgeRef('o',v.doc_id,2,build_uri('o',v.doc_id,2,anchor_id=pending.anchor_id),[],pending.quote.exact,digest(pending.quote.exact),anchor_id=pending.anchor_id)
        self.assertEqual(self.c.consume(self.admin,forged).reason_code,'anchor_drift_pending')
        with self.assertRaises(PermissionDeniedError):self.c.confirm_anchor_reanchor(self.user,v.doc_id,2,pending.anchor_id)
        confirmed=self.c.confirm_anchor_reanchor(self.admin,v.doc_id,2,pending.anchor_id)
        self.assertEqual(confirmed.reanchor_status,ReanchorStatus.ANCHORED)
        self.assertEqual(self.c.consume(self.admin,self.c.reference(self.admin,v.doc_id,anchor_id=pending.anchor_id)).status,'consumed')
    def test_deleted_orphan_unavailable_cannot_confirm(self):
        v=self.ingest('# H\n\nold policy');a=self.c.list_anchors(self.admin,v.doc_id)[0]
        self.ingest('# H\n\nreplacement',doc_id=v.doc_id);orphan=self.c.get_anchor(self.admin,v.doc_id,a.anchor_id)
        self.assertEqual(orphan.reanchor_status,ReanchorStatus.ORPHANED)
        ref=KnowledgeRef('o',v.doc_id,2,build_uri('o',v.doc_id,2,anchor_id=a.anchor_id),[],a.quote.exact,digest(a.quote.exact),anchor_id=a.anchor_id)
        receipt=self.c.consume(self.admin,ref);self.assertEqual((receipt.status,receipt.reason_code),('unavailable','anchor_orphaned'))
        with self.assertRaises(ValidationError):self.c.confirm_anchor_reanchor(self.admin,v.doc_id,2,a.anchor_id)
    def test_path_table_headers_and_pdf_page_movement_pending(self):
        p=ParserRegistry.defaults();p.register(['pdf'],OfflinePDFLayout())
        samples=[('x.md','# A\n\nexact','# B\n\nexact'),('x.csv','a,b\nexact,value','new,b\nexact,value'),('x.pdf',json.dumps({'text':'exact','page':1}),json.dumps({'text':'exact','page':2}))]
        for filename,old,new in samples:
            first=p.parse_layout(old.encode(),filename);second=p.parse_layout(new.encode(),filename)
            anchors=build_anchors_from_layout('o','d',1,first);changed=reanchor_to_version(anchors,2,second)
            self.assertEqual(changed[0].reanchor_status,ReanchorStatus.DRIFT_PENDING)
            self.assertEqual(changed[0].parent_anchor_id,anchors[0].anchor_id)
    def test_unconfirmed_lineage_never_silently_confirms(self):
        p=ParserRegistry.defaults();l=lambda t:p.parse_layout(t.encode(),'x.md')
        a=build_anchors_from_layout('o','d',1,l('# H\n\nexact'));b=reanchor_to_version(a,2,l('# Moved\n\nexact'))
        self.assertEqual(reanchor_to_version(b,3,l('# Moved\n\nexact'))[0].reanchor_status,ReanchorStatus.DRIFT_PENDING)
    def test_stable_ids_context_bounds_unchanged_dedup(self):
        v=self.ingest('# H\n\nexact');a=self.c.list_anchors(self.admin,v.doc_id)
        same=self.ingest('# H\n\nexact',doc_id=v.doc_id);self.assertEqual(same.version,1)
        self.assertEqual(a,self.c.list_anchors(self.admin,v.doc_id))
        self.assertLessEqual(len(a[0].quote.prefix),48);self.assertLessEqual(len(a[0].quote.suffix),48)
    def test_missing_hook_all_surfaces_and_old_plain_ref(self):
        v=self.ingest('# secret\n\nsecret original');a=self.c.list_anchors(self.admin,v.doc_id)[0];ref=self.c.reference(self.admin,v.doc_id,anchor_id=a.anchor_id)
        self.c.set_document_rights(self.admin,v.doc_id,ResourceRights(redaction_profile='pii'))
        for call in (lambda:self.c.list_anchors(self.user,v.doc_id),lambda:self.c.get_anchor(self.user,v.doc_id,a.anchor_id),lambda:self.c.reference(self.user,v.doc_id,anchor_id=a.anchor_id)):
            with self.assertRaisesRegex(PermissionDeniedError,'redaction_hook_missing'):call()
        self.assertEqual(self.c.consume(self.user,ref).reason_code,'redaction_hook_missing')
        self.c.redaction_registry.register('pii',RegexRedactionHook([('secret','[MASK]')]))
        delivered=self.c.get_anchor(self.user,v.doc_id,a.anchor_id)
        self.assertNotIn('secret',json.dumps(encode(delivered)));self.assertEqual(delivered.quote_sha256,digest(delivered.quote.exact))
        self.assertEqual(self.c.store.get_anchor('o',v.doc_id,1,a.anchor_id).quote.exact,'secret original')
        self.assertEqual(self.c.consume(self.user,ref).status,'denied')
        safe=self.c.reference(self.user,v.doc_id,anchor_id=a.anchor_id);self.assertEqual(self.c.consume(self.user,safe).status,'consumed')
    def test_hook_errors_and_sensitive_selector_sidecars(self):
        v=self.ingest('secret,unit\nsecret,nM','secret.csv');a=self.c.list_anchors(self.admin,v.doc_id)[0]
        authoritative=replace(self.c.store.get_anchor('o',v.doc_id,1,a.anchor_id),metadata={'secret-key':'secret-value',**dict(a.metadata)})
        self.c.store.update_anchor(authoritative);self.c.set_document_rights(self.admin,v.doc_id,ResourceRights(redaction_profile='pii'))
        class Fail:
            def redact(self,*args):raise RuntimeError('secret must not leak')
        self.c.redaction_registry.register('pii',Fail())
        with self.assertRaisesRegex(PermissionDeniedError,'^redaction_failed$'):self.c.get_anchor(self.admin,v.doc_id,a.anchor_id)
        self.c.redaction_registry.register('pii',RegexRedactionHook([('secret','[MASK]')]))
        safe=self.c.get_anchor(self.admin,v.doc_id,a.anchor_id);self.assertNotIn('secret',json.dumps(encode(safe)))
    def test_ref_identity_and_conflicting_selectors_rejected(self):
        v=self.ingest('# H\n\nexact');a=self.c.list_anchors(self.admin,v.doc_id)[0];ref=self.c.reference(self.admin,v.doc_id,anchor_id=a.anchor_id)
        with self.assertRaises(ValidationError):self.c.reference(self.admin,v.doc_id,chunk_ids=['x'],anchor_id=a.anchor_id)
        for broken in (replace(ref,anchor_id=''),replace(ref,source_uri=build_uri('o',v.doc_id,1)),replace(ref,chunk_ids=['x']),replace(ref,excerpt='forged',excerpt_hash=digest('forged'))):
            with self.assertRaises(TamperedExcerptError):self.c.consume(self.admin,broken)
    def test_live_rights_and_agent_recheck_confirmation(self):
        v=self.ingest('# H\n\nexact');a=self.c.list_anchors(self.admin,v.doc_id)[0];ref=self.c.reference(self.admin,v.doc_id,anchor_id=a.anchor_id)
        agent=AgentIdentity('a','o',allowed_kb_ids=('other',))
        with self.assertRaisesRegex(PermissionDeniedError,'agent_scope_denied'):self.c.list_anchors(self.admin,v.doc_id,agent=agent)
        self.c.set_document_rights(self.admin,v.doc_id,ResourceRights(revoked=True))
        self.assertEqual(self.c.consume(self.admin,ref).reason_code,'resource_revoked')
    def test_bad_layout_is_atomic_and_no_source_pollution(self):
        class Bad:
            def parse_layout(self,*args):raise ValidationError('bad layout')
        self.c.parsers.register(['bad'],Bad())
        with self.assertRaises(ValidationError):self.ingest(b'bad','x.bad')
        self.assertEqual(self.c.store.list_documents('o'),[])

    def test_store_anchor_identity_is_rechecked_at_delivery_boundary(self):
        from unittest.mock import patch
        v=self.ingest('# H\n\nexact');anchor=self.c.list_anchors(self.admin,v.doc_id)[0]
        for change in ({'org_id':'other'},{'doc_id':'other'},{'version':2}):
            forged=replace(anchor,**change)
            with patch.object(self.c.store,'get_anchors',return_value=[forged]):
                with self.assertRaisesRegex(PermissionDeniedError,'anchor_identity_mismatch'):self.c.list_anchors(self.admin,v.doc_id)
            with patch.object(self.c.store,'get_anchor',return_value=forged):
                with self.assertRaisesRegex(PermissionDeniedError,'anchor_identity_mismatch'):self.c.get_anchor(self.admin,v.doc_id,anchor.anchor_id)
