from __future__ import annotations
from dataclasses import replace
import json
import tempfile
import unittest
from pathlib import Path
from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode, decode
from knowledge_sdk.retrieval.base import VectorHit


class Spy:
    def __init__(self): self.calls = 0
    def generate(self, question, evidence_hits, scope, actor):
        self.calls += 1
        return GeneratedAnswer(evidence_hits[0].excerpt, True)


class V11Tests(unittest.TestCase):
    def setUp(self):
        self.c = LocalKnowledgeClient()
        self.admin = Actor('admin', 'org', org_roles=('admin',))
        self.user = Actor('user', 'org', department_ids=('child',), ancestor_department_ids=('parent',))
        self.manager = Actor('manager', 'org', department_ids=('parent',), managed_department_ids=('parent',))
        self.k = self.c.create_kb(self.admin, 'Public', space_type='enterprise_public')
        self.v = self.c.ingest(self.admin, self.k.kb_id, 'Automobile maintenance requires regular oil inspection.')
    def tearDown(self): self.c.store.close()
    def acl(self, **kw): self.c.set_document_acl(self.admin, self.v.doc_id, DocumentACL(**kw))
    def readable(self, actor):
        try: self.c.retrieve(actor, self.v.doc_id); return True
        except PermissionDeniedError: return False
    def test_visibility_mapping(self):
        for vis, tier in [('private','personal'), ('team','department'), ('enterprise','enterprise_public')]:
            kb = self.c.create_kb(self.user, vis, vis)
            self.assertEqual(kb.space_type, tier)
            self.assertTrue(kb.legacy_permissions)
    def test_public_creation_requires_org_admin(self):
        with self.assertRaises(PermissionDeniedError): self.c.create_kb(self.user, 'P', space_type='enterprise_public')
    def test_public_owner_is_not_implicit_admin_after_claim_revocation(self):
        actor = Actor('admin', 'org')
        self.assertFalse(self.c.can_manage_kb(actor, self.k.kb_id))
        with self.assertRaises(PermissionDeniedError): self.c.ingest(actor, self.k.kb_id, 'bad')
    def test_public_grant_does_not_enable_upload(self):
        self.c.grant_kb_member(self.admin, self.k.kb_id, self.user.user_id, 'admin')
        self.assertFalse(self.c.can_upload_to_kb(self.user, self.k.kb_id))
    def test_public_explicit_permission(self):
        actor = Actor('service', 'org', public_kb_admin=True)
        self.assertTrue(self.c.can_manage_kb(actor, self.k.kb_id))
        self.c.ingest(actor, self.k.kb_id, 'more knowledge')
    def test_approver_is_not_public_admin(self):
        self.assertFalse(self.c.can_manage_kb(Actor('approver', 'org', roles=('admin',), org_roles=('approver',)), self.k.kb_id))
    def test_department_creation_requires_matching_manager(self):
        with self.assertRaises(PermissionDeniedError): self.c.create_kb(self.user, 'D', space_type='department', owner_department_id='parent')
        with self.assertRaises(ValidationError): self.c.create_kb(self.manager, 'D', space_type='department')
    def test_department_upload_and_read_boundary(self):
        kb = self.c.create_kb(self.manager, 'D', space_type='department', owner_department_id='parent')
        v = self.c.ingest(self.manager, kb.kb_id, 'department plan')
        self.assertTrue(self.c.retrieve(Actor('peer','org',department_ids=('parent',)),v.doc_id).text)
        self.assertFalse(self.c.can_upload_to_kb(self.user, kb.kb_id))
        self.assertFalse(self.c.can_manage_kb(self.admin, kb.kb_id))
        with self.assertRaises(PermissionDeniedError): self.c.retrieve(Actor("sibling","org",department_ids=("sibling",)),v.doc_id)
    def test_department_space_descendant_acl_boundary(self):
        kb=self.c.create_kb(self.manager,'D',space_type='department',owner_department_id='parent')
        v=self.c.ingest(self.manager,kb.kb_id,'inherited evidence')
        self.c.set_document_acl(self.manager,v.doc_id,DocumentACL(access_level='department',allowed_department_ids=['parent']))
        with self.assertRaises(PermissionDeniedError): self.c.retrieve(self.user,v.doc_id)
        self.c.set_document_acl(self.manager,v.doc_id,DocumentACL(access_level='department',allowed_department_ids=['parent'],include_sub_departments=True))
        self.assertTrue(self.c.retrieve(self.user,v.doc_id).text)

    def test_personal_owner_only_upload(self):
        kb = self.c.create_kb(self.user, 'P', space_type='personal')
        self.assertEqual(kb.owner_user_id, self.user.user_id)
        self.assertTrue(self.c.can_upload_to_kb(self.user,kb.kb_id))
        with self.assertRaises(PermissionDeniedError): self.c.ingest(self.admin,kb.kb_id,'bad')
        with self.assertRaises(PermissionDeniedError): self.c.create_kb(self.user,'P',space_type='personal',owner_user_id='someone')
    def test_cross_org_public_admin_denied(self):
        self.assertFalse(self.c.can_manage_kb(Actor('admin','other',org_roles=('admin',)), self.k.kb_id))
    def test_org_public(self):
        self.acl(access_level='org_public')
        self.assertTrue(self.readable(self.user))
        self.assertFalse(self.readable(Actor('user','other')))
    def test_department_direct_only(self):
        self.acl(access_level='department',allowed_department_ids=['parent'])
        self.assertFalse(self.readable(self.user))
        self.assertTrue(self.readable(self.manager))
        self.assertFalse(self.readable(self.admin))
    def test_department_ancestor_inheritance(self):
        self.acl(access_level='department',allowed_department_ids=['parent'],include_sub_departments=True)
        self.assertTrue(self.readable(self.user))
        self.assertFalse(self.readable(Actor('x','org',department_ids=('sibling',))))
    def test_department_empty_policy_denies_everyone(self):
        self.acl(access_level='department')
        self.assertFalse(self.readable(self.admin))
    def test_multi_department(self):
        self.acl(access_level='department',allowed_department_ids=['second'])
        self.assertTrue(self.readable(Actor('x','org',department_ids=('first','second'))))
    def test_raw_roles_distinct_from_space_roles(self):
        self.acl(access_level='role_clearance',allowed_org_roles=['analyst'])
        self.assertFalse(self.readable(Actor('x','org',roles=('analyst',))))
        self.assertTrue(self.readable(Actor('x','org',org_roles=('analyst',))))
    def test_clearance_order(self):
        self.acl(access_level='role_clearance',required_clearance='confidential')
        for level, allowed in [('',False),('public',False),('internal',False),('confidential',True),('restricted',True),('custom',False)]:
            with self.subTest(level=level): self.assertEqual(self.readable(Actor('x','org',clearance_level=level)),allowed)
    def test_custom_clearance_and_tags(self):
        self.acl(access_level='role_clearance',allowed_org_roles=['analyst'],required_clearance='custom',allowed_clearance_tags=['project-x'])
        self.assertTrue(self.readable(Actor('x','org',org_roles=('analyst',),clearance_level='custom',clearance_tags=('project-x',))))
        self.assertFalse(self.readable(Actor('x','org',org_roles=('analyst',),clearance_level='custom')))
    def test_role_clearance_empty_fails_closed(self):
        self.acl(access_level='role_clearance')
        self.assertFalse(self.readable(self.admin))
    def test_personal_acl_even_admin_cannot_bypass(self):
        v=self.c.ingest(self.admin,self.k.kb_id,'private document')
        self.c.store.put_document(replace(self.c.store.get_document(v.doc_id),owner_id='owner'))
        self.c.set_document_acl(self.admin,v.doc_id,DocumentACL(access_level='personal_only',allowed_user_ids=['friend']))
        for actor,allowed in [(self.admin,False),(Actor('owner','org'),True),(Actor('friend','org'),True),(self.user,False)]:
            with self.subTest(actor=actor):
                self.assertEqual(bool(self.c.search(actor,'private').hits),allowed)
    def test_deny_overrides_new_acl(self):
        self.acl(access_level='org_public',deny_users=['admin'])
        self.assertFalse(self.readable(self.admin))
    def test_document_acl_cannot_bypass_kb(self):
        kb=self.c.create_kb(self.admin,'Private',space_type='personal')
        v=self.c.ingest(self.admin,kb.kb_id,'hidden')
        self.c.set_document_acl(self.admin,v.doc_id,DocumentACL(access_level='org_public'))
        with self.assertRaises(PermissionDeniedError): self.c.retrieve(self.user,v.doc_id)
    def test_acl_validation(self):
        for kw in [dict(access_level='bad'),dict(include_sub_departments='yes'),dict(allowed_org_roles='admin'),dict(required_clearance=3),dict(allowed_user_ids=[''])]:
            with self.subTest(kw=kw), self.assertRaises(ValidationError): DocumentACL(**kw)
    def test_new_actor_claim_validation(self):
        for kw in [dict(org_roles='admin'),dict(ancestor_department_ids=[3]),dict(clearance_tags='x'),dict(public_kb_admin='yes')]:
            with self.subTest(kw=kw), self.assertRaises(ValidationError): Actor('x','org',**kw)
    def test_ask_extractive_refs_receipts(self):
        answer=self.c.ask(self.user,'maintenance')
        self.assertEqual(answer.status,'answered'); self.assertFalse(answer.model_called)
        self.assertIn('oil',answer.answer)
        for ref,receipt in zip(answer.citations,answer.receipts):
            self.assertTrue(self.c.verify_receipt(self.user,ref,receipt))
            self.assertIn('/versions/1',ref.source_uri) if '/versions/' in ref.source_uri else self.assertEqual(ref.version,1)
    def test_ask_explicit_generator(self):
        spy=Spy(); answer=self.c.ask(self.user,'maintenance',generator=spy)
        self.assertEqual(spy.calls,1); self.assertTrue(answer.model_called)
    def test_ask_no_match_does_not_generate(self):
        spy=Spy(); answer=self.c.ask(self.user,'unfindablezz',generator=spy)
        self.assertEqual((answer.status,answer.model_called,answer.citations,spy.calls),('refused',False,[],0))
    def test_ask_acl_filtered_does_not_generate(self):
        self.acl(access_level='personal_only'); spy=Spy()
        answer=self.c.ask(self.user,'maintenance',generator=spy)
        self.assertEqual(answer.status,'refused'); self.assertEqual(spy.calls,0)
    def test_ask_cross_org_does_not_generate(self):
        spy=Spy(); answer=self.c.ask(Actor('admin','other'),'maintenance',generator=spy)
        self.assertEqual(answer.status,'refused'); self.assertEqual(spy.calls,0)
    def test_ask_below_threshold_does_not_generate(self):
        spy=Spy(); answer=self.c.ask(self.user,'maintenance',generator=spy,min_score=1)
        self.assertEqual(answer.status,'refused'); self.assertEqual(spy.calls,0)
    def test_ask_validation(self):
        for kw in [dict(top_k=0),dict(top_k=True),dict(min_score=float('nan')),dict(min_score=-1),dict(excerpt_policy={})]:
            with self.subTest(kw=kw), self.assertRaises(ValidationError): self.c.ask(self.user,'maintenance',**kw)
    def test_ask_bad_generator_rejected(self):
        class Bad:
            def generate(self,*args): return 'unsupported'
        with self.assertRaises(ValidationError): self.c.ask(self.user,'maintenance',generator=Bad())
    def test_ask_excerpt_budget(self):
        a=self.c.ask(self.user,'maintenance',excerpt_policy=ExcerptPolicy(10,10))
        self.assertEqual(len(a.citations[0].excerpt),10)
        self.assertTrue(self.c.verify_receipt(self.user,a.citations[0],a.receipts[0]))
    def test_search_and_ingestion_do_not_generate(self):
        spy=Spy(); self.c.search(self.user,'maintenance'); self.c.list_documents(self.user)
        self.assertEqual(spy.calls,0)
    def test_scope_documents(self):
        other=self.c.ingest(self.admin,self.k.kb_id,'maintenance on bicycles')
        answer=self.c.ask(self.user,'maintenance',scope=KnowledgeScope('documents',doc_ids=(other.doc_id,)))
        self.assertEqual([r.doc_id for r in answer.citations],[other.doc_id])
    def test_scope_spaces(self):
        answer=self.c.ask(self.user,'maintenance',scope=KnowledgeScope('spaces',space_types=('department',)))
        self.assertEqual(answer.status,'refused')
        answer=self.c.ask(self.user,'maintenance',scope=KnowledgeScope('spaces',kb_ids=(self.k.kb_id,),space_types=('enterprise_public',)))
        self.assertEqual(answer.status,'answered')
    def test_scope_invalid_rejected(self):
        for kw in [dict(mode='bad'),dict(kb_ids=('x',)),dict(mode='spaces'),dict(mode='documents'),dict(mode='spaces',space_types=('bad',)),dict(mode='documents',doc_ids='x')]:
            with self.subTest(kw=kw), self.assertRaises(ValidationError): KnowledgeScope(**kw)
    def test_scope_cross_org_validation(self):
        with self.assertRaises(PermissionDeniedError): self.c.validate_scope(Actor('x','other'),KnowledgeScope('documents',doc_ids=(self.v.doc_id,)))
    def test_contract_json_roundtrip(self):
        binding=ConsumerBinding('cycle','c1',KnowledgeScope('spaces',kb_ids=(self.k.kb_id,)),'background')
        for camel in (True,False): self.assertEqual(ConsumerBinding.from_dict(json.loads(json.dumps(binding.to_dict(camel)))),binding)
        for value in [binding, KnowledgeScope(), self.c.ask(self.user,'maintenance')]:
            self.assertEqual(decode(json.loads(json.dumps(encode(value)))),value)
    def test_binding_persistence_is_actor_and_org_scoped(self):
        b=ConsumerBinding('agent','a1'); self.c.bind_consumer(self.user,b)
        self.assertEqual(self.c.get_consumer_binding(self.user,'agent','a1'),b)
        for actor in [self.admin,Actor('user','other')]:
            with self.assertRaises(NotFoundError): self.c.get_consumer_binding(actor,'agent','a1')
    def test_binding_revalidated_after_revocation(self):
        b=ConsumerBinding('cycle','c1',KnowledgeScope('documents',doc_ids=(self.v.doc_id,)))
        self.c.bind_consumer(self.user,b); self.acl(access_level='personal_only')
        with self.assertRaises(PermissionDeniedError): self.c.get_consumer_binding(self.user,'cycle','c1')
    def test_attach_binding_receipt(self):
        ref=self.c.create_ref(self.user,self.v.doc_id,excerpt='Automobile')
        b=ConsumerBinding('cycle','c1',KnowledgeScope('documents',doc_ids=(self.v.doc_id,)),'background')
        attachment=self.c.attach(self.user,ref,b)
        self.assertEqual(attachment.receipt.used_by_stage,'background')
        self.assertTrue(self.c.verify_receipt(self.user,ref,attachment.receipt,b))
        self.assertFalse(self.c.verify_receipt(self.user,ref,replace(attachment.receipt,consumer_id='forged'),b))
    def test_attach_outside_scope_denied(self):
        ref=self.c.reference(self.user,self.v.doc_id,excerpt='Automobile')
        b=ConsumerBinding('agent','x',KnowledgeScope('spaces',space_types=('department',)))
        with self.assertRaises(PermissionDeniedError): self.c.attach(self.user,ref,b)
    def test_ref_tampering_and_revocation(self):
        ref=self.c.reference(self.user,self.v.doc_id,excerpt='Automobile')
        with self.assertRaises(TamperedExcerptError): self.c.attach(self.user,replace(ref,excerpt='forged'))
        receipt=self.c.verify_ref(self.user,ref)
        self.assertFalse(self.c.verify_receipt(self.user,ref,replace(receipt,excerpt_hash='forged')))
        self.acl(access_level='personal_only')
        self.assertEqual(self.c.verify_ref(self.user,ref).status,'denied')
        with self.assertRaises(PermissionDeniedError): self.c.attach(self.user,ref)
    def test_versioned_ref_survives_update(self):
        ref=self.c.reference(self.user,self.v.doc_id,excerpt='Automobile')
        self.c.ingest(self.admin,self.k.kb_id,'Different new contents',doc_id=self.v.doc_id)
        self.assertEqual(self.c.verify_ref(self.user,ref).status,'partial')
        self.assertEqual(ref.version,1)
    def test_archive_ref_unavailable_and_ask_refused(self):
        ref=self.c.reference(self.user,self.v.doc_id)
        self.c.archive(self.admin,self.v.doc_id)
        self.assertEqual(self.c.verify_ref(self.user,ref).status,'unavailable')
        self.assertEqual(self.c.ask(self.user,'maintenance').status,'refused')
    def test_binding_ask_cannot_broaden_scope(self):
        b=ConsumerBinding('agent','a',KnowledgeScope('spaces',space_types=('department',)))
        spy=Spy(); a=self.c.ask(self.user,'maintenance',binding=b,generator=spy)
        self.assertEqual(a.status,'refused'); self.assertEqual(spy.calls,0)
        self.assertEqual(a.binding_applied,b)
    def test_generator_access_revocation_detected(self):
        client=self.c; admin=self.admin; doc_id=self.v.doc_id
        class Revoke:
            def generate(self,*args):
                client.set_document_acl(admin,doc_id,DocumentACL(access_level='personal_only'))
                return GeneratedAnswer('should not be returned',True)
        a=self.c.ask(self.user,'maintenance',generator=Revoke())
        self.assertEqual(a.status,'refused'); self.assertEqual(a.answer,''); self.assertTrue(a.model_called)
    def test_sqlite_roundtrip_and_old_rows(self):
        with tempfile.TemporaryDirectory() as td:
            store=SQLiteStore(Path(td)/'kb.db'); c=LocalKnowledgeClient(store)
            kb=c.create_kb(self.admin,'Public',space_type='enterprise_public')
            v=c.ingest(self.admin,kb.kb_id,'persistent evidence')
            c.set_document_acl(self.admin,v.doc_id,DocumentACL(access_level='department',allowed_department_ids=['parent'],include_sub_departments=True))
            store.close(); store=SQLiteStore(Path(td)/'kb.db'); c=LocalKnowledgeClient(store)
            self.assertFalse(c.store.get_kb(kb.kb_id).legacy_permissions)
            self.assertTrue(c.retrieve(self.user,v.doc_id).text)
            store.db.execute('INSERT INTO knowledge_bases VALUES(?,?,?)',('old','org',json.dumps({'__type__':'KnowledgeBase','kb_id':'old','org_id':'org','name':'old','owner_id':'user','visibility':'team'})))
            self.assertEqual(c.store.get_kb('old').space_type,'department')
            self.assertTrue(c.store.get_kb('old').legacy_permissions)
            store.close()


class DepartmentTests(unittest.TestCase):
    def test_ancestors_order_independent(self):
        nodes=[{'id':'root','parentId':None},{'id':'parent','parentId':'root'},{'id':'child','parentId':'parent'}]
        self.assertEqual(expand_department_ancestors(('child',),nodes),('parent','root'))
        self.assertEqual(expand_department_ancestors(('child',),reversed(nodes)),('parent','root'))
    def test_multi_department_ancestors(self):
        self.assertEqual(expand_department_ancestors(('a','b'),[{'id':'a','parentId':'root'},{'id':'root'},{'id':'b','parentId':'root'}]),('root',))
    def test_tree_rejects_cycle_orphan_duplicate_and_foreign_edges(self):
        cases=[[{'id':'a','parentId':'a'}],[{'id':'a','parentId':'b'},{'id':'b','parentId':'a'}],[{'id':'a','parentId':'missing'}],[{'id':'a'},{'id':'a'}],[{'id':'a','parentId':'b','organizationId':'o1'},{'id':'b','organizationId':'o2'}]]
        for nodes in cases:
            with self.subTest(nodes=nodes), self.assertRaises(ValidationError): expand_department_ancestors((),nodes)
    def test_unknown_user_department(self):
        with self.assertRaises(ValidationError): expand_department_ancestors(('missing',),[])
    def test_empty_forest(self): self.assertEqual(expand_department_ancestors((),[]),())


class VectorACLTests(unittest.TestCase):
    def test_untrusted_vector_candidates_are_sqlite_filtered_for_every_consumer(self):
        class Embed:
            def embed(self,texts): return [[1.0] for _ in texts]
        class Index:
            candidates=[]
            def search(self,vector,limit): return self.candidates
            def delete_document(self,doc_id): pass
            def upsert(self,points): pass
        index=Index(); c=LocalKnowledgeClient(vector_index=index,embedder=Embed())
        admin=Actor('admin','org',org_roles=('admin',)); user=Actor('u','org')
        kb=c.create_kb(admin,'P',space_type='enterprise_public')
        v=c.ingest(admin,kb.kb_id,'secret automobile maintenance')
        chunk=c.store.get_chunks(v.doc_id,1)[0]
        index.candidates=[VectorHit(v.doc_id,1,chunk.chunk_id,999)]
        c.set_document_acl(admin,v.doc_id,DocumentACL(access_level='personal_only'))
        spy=Spy()
        self.assertEqual(c.search(user,'synonym',mode='vector').hits,[])
        self.assertEqual(c.ask(user,'synonym',mode='vector',generator=spy).status,'refused')
        self.assertEqual(spy.calls,0)
        self.assertEqual(c.search(Actor('admin','other'),'synonym',mode='vector').hits,[])
        with self.assertRaises(PermissionDeniedError): c.retrieve(user,v.doc_id)
        with self.assertRaises(PermissionDeniedError): c.create_ref(user,v.doc_id)
        self.assertTrue(c.ask(admin,'synonym',mode='vector').citations)
        index.candidates=[VectorHit(v.doc_id,99,chunk.chunk_id,999),VectorHit(v.doc_id,1,'fake',999),VectorHit('nonexistent',1,'fake',999)]
        self.assertEqual(c.ask(admin,'synonym',mode='vector',generator=spy).status,'refused')
        self.assertEqual(spy.calls,0); c.store.close()
