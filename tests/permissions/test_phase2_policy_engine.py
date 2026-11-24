from __future__ import annotations
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import tempfile
import unittest

from knowledge_sdk import (Actor, KnowledgeBase, Document, DocumentACL, ResourceRights,
    AgentIdentity, Purpose, PolicyAction, DecisionEffect, GovernanceTier, PolicyRule,
    PolicyContext, PolicyDecision, DefaultPolicyEngine, intersect_decisions,
    RedactionRegistry, RegexRedactionHook, LocalKnowledgeClient, SQLiteStore,
    PermissionDeniedError, ValidationError, KnowledgeScope, ConsumerBinding, GeneratedAnswer)
from knowledge_sdk.contracts.models import encode, decode
from knowledge_sdk.ingestion.fingerprint import sha256

READ=Purpose.READ
ALLOW=DecisionEffect.ALLOW
DENY=DecisionEffect.DENY
MASK=DecisionEffect.ALLOW_WITH_REDACTION
A=PolicyAction
NOW=PolicyContext(now='2026-11-24T12:00:00+08:00')


class StrictPolicyContractTests(unittest.TestCase):
    def test_defaults_and_rights_export_correction(self):
        self.assertEqual(ResourceRights().allowed_purposes,(READ,Purpose.GROUND_INTERNAL_LLM,Purpose.EXPORT))
        self.assertTrue(ResourceRights().allow_export)
        self.assertFalse(ResourceRights().allow_external_llm)
        self.assertFalse(ResourceRights().allow_eval_and_train)
        self.assertEqual(AgentIdentity(' a ',' org ').agent_id,'a')
        self.assertEqual(AgentIdentity('a','org').allowed_purposes,(READ,Purpose.GROUND_INTERNAL_LLM))

    def test_all_policy_model_and_enum_nested_json_roundtrips(self):
        values=(AgentIdentity('a','org',allowed_purposes=['read','export'],allowed_kb_ids=['k']),
                ResourceRights(retention_until='2027-01-01T00:00:00Z'),
                PolicyRule('r','org','allow_with_redaction',actions=['read_content','search_index'],redaction_profile='pii'),
                PolicyContext(now='2026-11-24T12:00:00+08:00'),
                PolicyDecision('allow','ok','7',audit_summary={'stages':['one',{'n':1}]}))
        for value in values:
            encoded=encode(value)
            self.assertEqual(decode(json.loads(json.dumps(encoded))),value)
            self.assertEqual(type(value).from_dict(value.to_dict()),value)
        for enum in (READ,A.READ_CONTENT,ALLOW,GovernanceTier.L1_AGILE):
            self.assertEqual(type(encode(enum)),str)
            self.assertEqual(json.loads(json.dumps(encode(enum))),enum.value)

    def test_agent_rejects_unknown_fields_and_wrong_types(self):
        for data in ({'agent_id':'a','org_id':'o','admin':True}, {'agent_id':'','org_id':'o'},
                     {'agent_id':True,'org_id':'o'}, {'agent_id':'a','org_id':[]},
                     {'agent_id':'a','org_id':'o','allowed_purposes':'read'},
                     {'agent_id':'a','org_id':'o','allowed_purposes':['invalid']},
                     {'agent_id':'a','org_id':'o','allowed_kb_ids':'k'},
                     {'agent_id':'a','org_id':'o','max_clearance_level':True},
                     {'agent_id':'a','org_id':'o','profile_version':1}):
            with self.subTest(data=data), self.assertRaises(ValidationError): AgentIdentity.from_dict(data)

    def test_resource_rights_strict_booleans_strings_and_time(self):
        for key in ('allow_external_llm','allow_export','allow_eval_and_train','revoked'):
            for value in (1,0,'false',None,[]):
                with self.subTest(key=key,value=value), self.assertRaises(ValidationError): ResourceRights(**{key:value})
        for value in ('2026-01-01','2026-01-01T00:00:00','wrong',True,[],1):
            with self.subTest(value=value), self.assertRaises(ValidationError): ResourceRights(retention_until=value)
        for key in ('redaction_profile','license_id','license_terms_version','revocation_reason'):
            with self.assertRaises(ValidationError): ResourceRights(**{key:False})
        with self.assertRaises(ValidationError): ResourceRights(allowed_purposes='read')
        with self.assertRaises(ValidationError): ResourceRights(redaction_profile='one,,two')

    def test_rule_context_decision_strict_fields(self):
        for kw in ({'priority':True},{'actions':[]},{'actions':'read_content'},{'purposes':[]},
                   {'condition_meta':{'unsupported':True}},{'effect':MASK}, {'match_users':'u'},
                   {'scope_kb_id':False},{'required_clearance':[]},{'effect':'bogus'}):
            args={'rule_id':'r','org_id':'o','effect':ALLOW}; args.update(kw)
            with self.subTest(kw=kw), self.assertRaises(ValidationError): PolicyRule(**args)
        with self.assertRaises(ValidationError): PolicyContext(include_archived=1)
        with self.assertRaises(ValidationError): PolicyContext(now='2026-01-01')
        with self.assertRaises(ValidationError): PolicyDecision(ALLOW,'ok',0)
        with self.assertRaises(ValidationError): PolicyDecision(MASK,'mask','0')
        with self.assertRaises(ValidationError): PolicyDecision(ALLOW,'ok','0',audit_summary={'x':object()})
        with self.assertRaises(ValidationError): PolicyRule.from_dict({'rule_id':'r','org_id':'o','effect':'allow','future_field':1})

    def test_frozen_defensive_snapshots(self):
        purposes=['read']; agent=AgentIdentity('a','o',allowed_purposes=purposes)
        purposes.append('export'); self.assertEqual(agent.allowed_purposes,(READ,))
        raw={'items':[{'n':1}]}; decision=PolicyDecision(ALLOW,'ok','0',audit_summary=raw)
        raw['items'][0]['n']=99
        self.assertEqual(decision.audit_summary['items'][0]['n'],1)
        with self.assertRaises(FrozenInstanceError): agent.app_id='x'
        with self.assertRaises(TypeError): decision.audit_summary['new']=1
        with self.assertRaises(TypeError): decision.audit_summary['items'][0]['n']=2
        with self.assertRaises(FrozenInstanceError): decision.allowed=False

    def test_client_protocol_lists_current_policy_method_parameters(self):
        import inspect
        from knowledge_sdk import KnowledgeClient
        for name in ('evaluate_policy','set_document_rights','retrieve','ask','create_ref','inspect_document','create_kb'):
            self.assertEqual(list(inspect.signature(getattr(KnowledgeClient,name)).parameters),
                             list(inspect.signature(getattr(LocalKnowledgeClient,name)).parameters))

    def test_document_extensions_and_legacy_json(self):
        old={'__type__':'Document','doc_id':'d','org_id':'o','kb_id':'k','owner_id':'u','title':'old'}
        d=decode(old)
        self.assertEqual((d.lifecycle_state,d.valid_from,d.valid_to,d.rights),('published',None,None,None))
        kb=decode({'__type__':'KnowledgeBase','kb_id':'k','org_id':'o','name':'old','owner_id':'u'})
        self.assertEqual(kb.governance_tier,'l1_agile')
        document=replace(d,rights={'allowed_purposes':['read'],'allow_export':False},valid_from='2026-01-01T00:00:00Z',valid_to='2027-01-01T00:00:00Z')
        self.assertIsInstance(document.rights,ResourceRights)
        self.assertEqual(decode(json.loads(json.dumps(encode(document)))),document)
        for kw in ({'lifecycle_state':True},{'lifecycle_state':'invalid'},{'rights':False},
                   {'valid_from':'2027-01-01T00:00:00Z','valid_to':'2026-01-01T00:00:00Z'},
                   {'valid_to':'2026-01-01'}):
            with self.subTest(kw=kw), self.assertRaises(ValidationError): replace(d,**kw)
        with self.assertRaises(ValidationError): replace(kb,governance_tier='future')


class EightGatePolicyTests(unittest.TestCase):
    def setUp(self):
        self.actor=Actor('u','org',org_roles=('scientist',),department_ids=('lab',),clearance_level='restricted',policy_generation='actor-gen')
        self.kb=KnowledgeBase('k','org','invisible KB title','admin',visibility='enterprise')
        self.doc=Document('d','org','k','owner','invisible title',visibility='enterprise')
        self.acl=DocumentACL()
        self.engine=DefaultPolicyEngine()
    def decide(self,**kw):
        args=dict(actor=self.actor,agent=None,kb=self.kb,document=self.doc,acl=self.acl,context=NOW)
        args.update(kw); return self.engine.evaluate(**args)
    def reason(self,expected,**kw):
        result=self.decide(**kw); self.assertEqual(result.reason_code,expected); return result

    def test_01_tenant_mismatch_actor_document_agent(self):
        self.reason('tenant_mismatch',actor=Actor('u','other'))
        self.reason('tenant_mismatch',document=replace(self.doc,org_id='other'))
        self.reason('tenant_mismatch',agent=AgentIdentity('a','other'))
    def test_02_revoked_lifecycle_and_rights(self):
        self.reason('resource_revoked',document=replace(self.doc,lifecycle_state='revoked'))
        self.reason('resource_revoked',document=replace(self.doc,rights=ResourceRights(revoked=True)))
    def test_02_archived_requires_explicit_context(self):
        d=replace(self.doc,archived=True)
        self.reason('resource_archived',document=d)
        self.reason('ok',document=d,context=replace(NOW,include_archived=True))
    def test_02_controlled_lifecycle_owner_manager_exceptions(self):
        kb=replace(self.kb,governance_tier='l2_controlled');d=replace(self.doc,lifecycle_state='draft')
        for action in (A.READ_CONTENT,A.SEARCH_INDEX,A.EXPORT_PACK): self.reason('lifecycle_not_published',kb=kb,document=d,action=action)
        self.reason('ok',kb=kb,document=d,actor=replace(self.actor,user_id='owner'))
        self.reason('ok',kb=kb,document=d,member_role='admin')
    def test_02_validity_timezone_inclusive_and_fail_closed(self):
        self.reason('outside_validity_window',document=replace(self.doc,valid_from='2027-01-01T00:00:00Z'))
        self.reason('outside_validity_window',document=replace(self.doc,valid_to='2025-01-01T00:00:00Z'))
        self.reason('ok',document=replace(self.doc,valid_from='2026-11-24T04:00:00Z',valid_to='2026-11-24T12:00:00+08:00'))
        d=replace(self.doc); d.valid_from='not-a-time'
        self.reason('outside_validity_window',document=d)
    def test_03_acl_deny_overrides_owner_admin_and_allow_rules(self):
        self.engine=DefaultPolicyEngine([PolicyRule('allow','org',ALLOW,priority=1)])
        for acl in (DocumentACL(deny_users=['u']),DocumentACL(deny_roles=['legacy']),DocumentACL(deny_departments=['lab'])):
            self.reason('explicit_acl_deny',actor=replace(self.actor,roles=('legacy',),user_id='u'),document=replace(self.doc,owner_id='u'),member_role='admin',acl=acl)
    def test_03_policy_deny_always_beats_priority_one_allow(self):
        self.engine=DefaultPolicyEngine([PolicyRule('a','org',ALLOW,priority=1),PolicyRule('deny','org',DENY,priority=999)])
        result=self.reason('explicit_policy_deny'); self.assertEqual(result.matched_rule_ids,('deny',))
        self.assertEqual(result.audit_summary,{})
    def test_03_all_rule_selectors_are_conjunctive_and_tenant_scoped(self):
        r=PolicyRule('deny','org',DENY,scope_kb_id='k',scope_doc_id='d',match_users=('u',),match_org_roles=('scientist',),match_departments=('lab',),match_agent_ids=('agent',))
        self.engine=DefaultPolicyEngine([r]);agent=AgentIdentity('agent','org')
        self.reason('explicit_policy_deny',agent=agent)
        for change in ({'org_id':'else'},{'scope_kb_id':'else'},{'scope_doc_id':'else'},{'match_users':('else',)},
                       {'match_org_roles':('else',)},{'match_departments':('else',)},{'match_agent_ids':('else',)},
                       {'actions':(A.SEARCH_INDEX,)},{'purposes':(Purpose.EXPORT,)}):
            self.engine=DefaultPolicyEngine([replace(r,**change)])
            self.reason('ok',agent=agent)
    def test_04_private_space_boundary_cannot_be_opened_by_document_rules(self):
        self.engine=DefaultPolicyEngine([PolicyRule('all','org',ALLOW,priority=1)])
        self.reason('space_boundary_denied',kb=replace(self.kb,visibility='private'),acl=DocumentACL(access_level='org_public'))
    def test_04_manage_approve_publish_upload_require_space_capability(self):
        for action in (A.MANAGE_SPACE,A.APPROVE_RELEASE,A.PUBLISH_RELEASE,A.WRITE_DOCUMENT):
            self.reason('space_boundary_denied',action=action,document=None)
            self.reason('ok',action=action,document=None,member_role='admin')
    def test_04_document_none_still_checks_agent(self):
        self.reason('agent_scope_denied',document=None,agent=AgentIdentity('a','org',allowed_kb_ids=('else',)))
        self.reason('agent_purpose_denied',document=None,agent=AgentIdentity('a','org',allowed_purposes=()))
        self.reason('ok',document=None)
    def test_05_acl_denied_without_rules(self):
        self.reason('document_acl_denied',acl=DocumentACL(allow_users=['someone']))
    def test_05_qualified_rule_grants_only_inside_hard_boundaries(self):
        r=PolicyRule('r','org',ALLOW,match_users=('u',),required_clearance='confidential')
        self.engine=DefaultPolicyEngine([r])
        self.reason('ok',acl=DocumentACL(allow_users=['someone']))
        self.reason('document_acl_denied',acl=DocumentACL(allow_users=['someone']),actor=replace(self.actor,clearance_level='public'))
    def test_05_personal_redline_and_conservative_legacy_private_rules(self):
        self.engine=DefaultPolicyEngine([PolicyRule('all','org',ALLOW)])
        self.reason('document_acl_denied',acl=DocumentACL(access_level='personal_only'))
        self.reason('document_acl_denied',document=replace(self.doc,visibility='private'))
        self.engine=DefaultPolicyEngine([PolicyRule('target','org',ALLOW,scope_doc_id='d',match_users=('u',))])
        self.reason('ok',document=replace(self.doc,visibility='private'))
        self.reason('document_acl_denied',acl=DocumentACL(access_level='personal_only'))
    def test_06_agent_purpose_scope_and_clearance(self):
        self.reason('agent_purpose_denied',agent=AgentIdentity('a','org',allowed_purposes=()))
        self.reason('agent_scope_denied',agent=AgentIdentity('a','org',allowed_kb_ids=('another',)))
        acl=DocumentACL(access_level='role_clearance',required_clearance='confidential')
        for maximum in ('public','unknown'):
            self.reason('agent_clearance_exceeded',acl=acl,agent=AgentIdentity('a','org',max_clearance_level=maximum))
        self.reason('agent_clearance_exceeded',acl=DocumentACL(access_level='org_public',required_clearance='custom'),agent=AgentIdentity('a','org',max_clearance_level='restricted'))
        self.reason('ok',acl=acl,agent=AgentIdentity('a','org',max_clearance_level='restricted'))
    def test_07_retention_external_export_training_and_intersection(self):
        self.reason('retention_expired',document=replace(self.doc,rights=ResourceRights(retention_until='2020-01-01T00:00:00Z')))
        self.reason('external_llm_prohibited',purpose=Purpose.GROUND_EXTERNAL_LLM)
        self.reason('export_prohibited',purpose=Purpose.EXPORT,document=replace(self.doc,rights=ResourceRights(allow_export=False)))
        self.reason('training_prohibited',purpose=Purpose.EVAL_AND_TRAIN)
        self.reason('purpose_not_permitted',purpose=Purpose.EXPORT,document=replace(self.doc,rights=ResourceRights(allowed_purposes=(READ,))))
        self.reason('purpose_not_permitted',purpose=Purpose.GROUND_EXTERNAL_LLM,document=replace(self.doc,rights=ResourceRights(allow_external_llm=True)))
        rights=ResourceRights(allowed_purposes=tuple(Purpose),allow_external_llm=True,allow_eval_and_train=True)
        for purpose in Purpose: self.reason('ok',purpose=purpose,document=replace(self.doc,rights=rights))
    def test_08_all_redaction_obligations_survive_priority(self):
        self.engine=DefaultPolicyEngine([PolicyRule('allow','org',ALLOW,priority=1),
            PolicyRule('r2','org',MASK,priority=3,redaction_profile='two,one'),
            PolicyRule('r1','org',MASK,priority=2,redaction_profile='one')])
        decision=self.reason('redaction_required',document=replace(self.doc,rights=ResourceRights(redaction_profile='base,one')))
        self.assertEqual(decision.effect,MASK)
        self.assertEqual(decision.redaction_profile,'base,one,two')
        self.assertEqual(decision.matched_rule_ids,('allow','r1','r2'))
    def test_equal_priority_preserves_injected_order_and_tenant_namespaces(self):
        self.engine=DefaultPolicyEngine([PolicyRule('z','org',MASK,redaction_profile='z'),
                                        PolicyRule('a','org',MASK,redaction_profile='a'),
                                        PolicyRule('z','another',DENY)])
        result=self.reason('redaction_required')
        self.assertEqual(result.redaction_profile,'z,a')
        self.assertEqual(result.matched_rule_ids,('z','a'))

    def test_effective_generation_and_safe_audit(self):
        self.assertEqual(self.reason('ok').policy_generation,'actor-gen')
        decision=self.reason('tenant_mismatch',actor=Actor('u','other'),context=replace(NOW,policy_generation='context-gen'))
        self.assertEqual(decision.policy_generation,'context-gen')
        self.assertNotIn('invisible',json.dumps(encode(decision)))
    def test_priority_one_allow_does_not_cross_earlier_gates(self):
        self.engine=DefaultPolicyEngine([PolicyRule('all','org',ALLOW,priority=1)])
        self.reason('tenant_mismatch',actor=Actor('u','other'))
        self.reason('resource_revoked',document=replace(self.doc,lifecycle_state='revoked'))
        self.reason('explicit_acl_deny',acl=DocumentACL(deny_users=['u']))
        self.reason('space_boundary_denied',kb=replace(self.kb,visibility='private'))
    def test_intersection_four_outcomes_and_mixed_generation(self):
        allow=PolicyDecision(ALLOW,'ok','1',('a',))
        mask=PolicyDecision(MASK,'redaction_required','1',('b',),'one,two')
        deny=PolicyDecision(DENY,'resource_revoked','2',('c',))
        self.assertEqual(intersect_decisions([]).reason_code,'empty_source_decisions')
        self.assertEqual(intersect_decisions([allow,allow]).effect,ALLOW)
        merged=intersect_decisions([mask,PolicyDecision(MASK,'redaction_required','1',('b','d'),'two,three'),allow])
        self.assertEqual((merged.effect,merged.redaction_profile,merged.matched_rule_ids),(MASK,'one,two,three',('b','d','a')))
        result=intersect_decisions([allow,deny]); self.assertEqual(result.reason_code,'derived_source_denied')
        self.assertEqual(result.policy_generation,'mixed'); self.assertTrue(result.audit_summary['mixed_policy_generations'])
        result=intersect_decisions([allow,replace(allow,policy_generation='2')]); self.assertEqual(result.effect,ALLOW)
        self.assertEqual(result.policy_generation,'mixed')


class RedactionRegistryTests(unittest.TestCase):
    def test_missing_profile_and_sequential_regex(self):
        r=RedactionRegistry()
        with self.assertRaisesRegex(PermissionDeniedError,'redaction_hook_missing'): r.apply('secret','pii',READ)
        r.register('one',RegexRedactionHook([('secret','[MASK]')]))
        r.register('two',RegexRedactionHook([(r'\[MASK\]','[SAFE]')]))
        text,summary=r.apply('secret','one,two',READ)
        self.assertEqual(text,'[SAFE]'); self.assertIn('one:replacements=1',summary); self.assertIn('two:replacements=1',summary)
        with self.assertRaisesRegex(PermissionDeniedError,'redaction_hook_missing'): r.apply('secret','one,missing',READ)
    def test_fail_closed_on_hook_exception_and_wrong_returns(self):
        for result in (None,'plaintext',('only',),['text','summary'],('text',{}),('text',1)):
            class Bad:
                def redact(self,*args): return result
            registry=RedactionRegistry(); registry.register('bad',Bad())
            with self.assertRaisesRegex(PermissionDeniedError,'^redaction_failed$'): registry.apply('sensitive','bad',READ)
        class Explodes:
            def redact(self,*args): raise RuntimeError('sensitive original text')
        registry=RedactionRegistry(); registry.register('bad',Explodes())
        try: registry.apply('sensitive','bad',READ)
        except PermissionDeniedError as error:
            self.assertEqual(str(error),'redaction_failed'); self.assertTrue(error.__suppress_context__)
            self.assertIsNone(error.__cause__)
        else: self.fail('plaintext fallback')
    def test_metadata_is_defensively_copied(self):
        class Mutates:
            def redact(self,text,profile,purpose,metadata):
                metadata['nested']['value']=2; return text,'safe'
        r=RedactionRegistry();r.register('x',Mutates()); meta={'nested':{'value':1}}
        r.apply('text','x',READ,meta);self.assertEqual(meta['nested']['value'],1)


class PolicyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client=LocalKnowledgeClient(); self.addCleanup(self.client.store.close)
        self.admin=Actor('admin','org',org_roles=('admin',))
        self.user=Actor('user','org')
        self.kb=self.client.create_kb(self.admin,'public',space_type='enterprise_public')
        self.version=self.client.ingest(self.admin,self.kb.kb_id,'alpha sensitive 123-45-6789 omega',title='123-45-6789 title',metadata={'description':'123-45-6789'})
    def rights(self,**kwargs): return self.client.set_document_rights(self.admin,self.version.doc_id,ResourceRights(**kwargs))
    def register(self): self.client.redaction_registry.register('pii',RegexRedactionHook([(r'123-45-6789','[MASK]')]))
    def test_missing_hook_filters_search_and_raises_all_content_reads(self):
        ref=self.client.reference(self.user,self.version.doc_id,excerpt='alpha')
        self.rights(redaction_profile='pii')
        self.assertEqual(self.client.search(self.user,'alpha').hits,[])
        for read in (lambda:self.client.retrieve(self.user,self.version.doc_id),lambda:self.client.preview(self.user,self.version.doc_id),
                     lambda:self.client.get_document(self.user,self.version.doc_id,1),lambda:self.client.inspect_document(self.user,self.version.doc_id),
                     lambda:self.client.reference(self.user,self.version.doc_id)):
            with self.assertRaisesRegex(PermissionDeniedError,'redaction_hook_missing'): read()
        self.assertEqual(self.client.list_documents(self.user),[])
        self.assertEqual(self.client.consume(self.user,ref).reason_code,'redaction_hook_missing')
        self.assertEqual(self.client.verify_ref(self.user,ref).status,'denied')
        with self.assertRaisesRegex(PermissionDeniedError,'redaction_hook_missing'): self.client.attach(self.user,ref)
        spy=GeneratorSpy(); answer=self.client.ask(self.user,'alpha',generator=spy)
        self.assertEqual((answer.status,answer.model_called,spy.calls),('refused',False,0))
    def test_registered_mask_hits_hashes_versions_metadata_and_chunks(self):
        self.rights(redaction_profile='pii');self.register()
        hit=self.client.search(self.user,'alpha').hits[0]
        self.assertNotIn('123-45-6789',hit.excerpt+hit.title);self.assertTrue(hit.masking_summary)
        self.assertEqual(hit.excerpt_hash,sha256(hit.excerpt))
        retrieved=self.client.retrieve(self.user,self.version.doc_id);self.assertNotIn('123-45-6789',retrieved.text)
        self.assertIn('pii:',retrieved.masking_summary)
        for value in (self.client.preview(self.user,self.version.doc_id),self.client.get_document(self.user,self.version.doc_id,1),
                      self.client.get_document(self.user,self.version.doc_id),self.client.inspect_document(self.user,self.version.doc_id),
                      self.client.list_documents(self.user)):
            self.assertNotIn('123-45-6789',json.dumps(encode(value)))
        inspect=self.client.inspect_document(self.user,self.version.doc_id)
        for chunk in inspect['chunks']:
            self.assertEqual(chunk.chunk_hash,sha256(chunk.text))
            self.assertNotIn('123-45-6789',self.client.retrieve(self.user,self.version.doc_id,chunk_ids=[chunk.chunk_id]).text)
        self.assertEqual(self.client.store.get_version(self.version.doc_id,1).text,'alpha sensitive 123-45-6789 omega')
    def test_redacted_reference_receipt_and_old_plaintext_reference_rejected(self):
        old=self.client.reference(self.user,self.version.doc_id,excerpt='123-45-6789')
        self.rights(redaction_profile='pii');self.register()
        ref=self.client.reference(self.user,self.version.doc_id,excerpt='123-45-6789')
        self.assertEqual(ref.excerpt,'[MASK]');self.assertEqual(ref.excerpt_hash,sha256('[MASK]'))
        receipt=self.client.consume(self.user,ref)
        self.assertEqual(receipt.status,'partial');self.assertEqual(receipt.excerpt_hash,sha256(ref.excerpt))
        self.assertTrue(self.client.verify_receipt(self.user,ref,receipt))
        self.assertEqual(self.client.consume(self.user,old).reason_code,'redacted_excerpt_mismatch')
        self.assertEqual(self.client.attach(self.user,ref).reference.excerpt,'[MASK]')
        self.assertIn(self.client.consume(self.user,self.client.reference(self.user,self.version.doc_id)).status,('partial','consumed'))
    def test_rule_and_rights_multi_profile_generator_gets_only_safe_text(self):
        self.rights(redaction_profile='pii');self.register()
        self.client.redaction_registry.register('second',RegexRedactionHook([('sensitive','[SAFE]')]))
        self.client.policy_engine=DefaultPolicyEngine([PolicyRule('mask','org',MASK,purposes=(Purpose.GROUND_INTERNAL_LLM,),redaction_profile='second')])
        spy=GeneratorSpy();answer=self.client.ask(self.user,'alpha',generator=spy)
        self.assertEqual(answer.status,'answered');self.assertEqual(spy.calls,1)
        self.assertNotIn('123-45-6789',spy.text);self.assertNotIn('sensitive',spy.text)
        self.assertIn('[SAFE]',spy.text)
        self.assertNotIn('123-45-6789',json.dumps(encode(answer)))
    def test_non_idempotent_redaction_hook_does_not_double_mask_references(self):
        class Prefix:
            def redact(self,text,*args):return 'MASK:'+text,'prefix'
        self.rights(redaction_profile='prefix');self.client.redaction_registry.register('prefix',Prefix())
        hit=self.client.search(self.user,'alpha').hits[0]
        ref=self.client.reference(self.user,self.version.doc_id,excerpt=hit.excerpt)
        self.assertEqual(ref.excerpt,hit.excerpt)
        self.assertIn(self.client.consume(self.user,ref).status,('partial','consumed'))
    def test_hook_exception_no_plaintext_on_all_primary_flows(self):
        class Bad:
            def redact(self,*args):raise RuntimeError('123-45-6789')
        ref=self.client.reference(self.user,self.version.doc_id,excerpt='alpha')
        self.rights(redaction_profile='bad');self.client.redaction_registry.register('bad',Bad())
        self.assertEqual(self.client.search(self.user,'alpha').hits,[])
        with self.assertRaisesRegex(PermissionDeniedError,'^redaction_failed$'):self.client.retrieve(self.user,self.version.doc_id)
        self.assertEqual(self.client.consume(self.user,ref).reason_code,'redaction_failed')
        spy=GeneratorSpy();self.assertEqual(self.client.ask(self.user,'alpha',generator=spy).status,'refused');self.assertEqual(spy.calls,0)
    def test_rights_revocation_rechecked_on_every_consumption_delegate(self):
        ref=self.client.reference(self.user,self.version.doc_id,excerpt='alpha')
        receipt=self.client.consume(self.user,ref)
        self.rights(revoked=True)
        self.assertEqual(self.client.consume(self.user,ref).reason_code,'resource_revoked')
        self.assertEqual(self.client.verify_ref(self.user,ref).reason_code,'resource_revoked')
        self.assertEqual(self.client.batch_consume(self.user,[ref])[0].reason_code,'resource_revoked')
        self.assertFalse(self.client.verify_receipt(self.user,ref,receipt))
        with self.assertRaises(PermissionDeniedError):self.client.attach(self.user,ref)
    def test_agent_and_purpose_propagated_all_reads_and_bindings(self):
        agent=AgentIdentity('a','org',allowed_kb_ids=('other',))
        ref=self.client.reference(self.user,self.version.doc_id,excerpt='alpha')
        for action in (lambda:self.client.preview(self.user,self.version.doc_id,agent=agent),
                       lambda:self.client.get_document(self.user,self.version.doc_id,1,agent=agent),
                       lambda:self.client.inspect_document(self.user,self.version.doc_id,agent=agent),
                       lambda:self.client.reference(self.user,self.version.doc_id,agent=agent),
                       lambda:self.client.create_ref(self.user,self.version.doc_id,agent=agent)):
            with self.assertRaisesRegex(PermissionDeniedError,'agent_scope_denied'):action()
        self.assertEqual(self.client.search(self.user,'alpha',agent=agent).hits,[])
        self.assertEqual(self.client.consume(self.user,ref,agent=agent).reason_code,'agent_scope_denied')
        binding=ConsumerBinding('agent','a',KnowledgeScope('documents',doc_ids=(self.version.doc_id,)))
        with self.assertRaises(PermissionDeniedError):self.client.bind_consumer(self.user,binding,agent=agent)
        self.assertEqual(self.client.ask(self.user,'alpha',agent=agent).status,'refused')
        with self.assertRaisesRegex(PermissionDeniedError,'external_llm_prohibited'):
            self.client.preview(self.user,self.version.doc_id,purpose=Purpose.GROUND_EXTERNAL_LLM)
    def test_only_admin_sets_rights_and_control_fields(self):
        with self.assertRaises(PermissionDeniedError):self.client.set_document_rights(self.user,self.version.doc_id,ResourceRights(allow_external_llm=True))
        self.assertFalse(self.client.store.get_document(self.version.doc_id).rights)
        with self.assertRaises(PermissionDeniedError):self.client.ingest(self.user,self.kb.kb_id,'new',rights=ResourceRights())
        private=self.client.create_kb(self.admin,'private')
        self.client.grant_kb_member(self.admin,private.kb_id,self.user.user_id,'editor')
        for kw in ({'rights':ResourceRights()},{'lifecycle_state':'published'},{'valid_to':'2027-01-01T00:00:00Z'}):
            with self.assertRaises(PermissionDeniedError):self.client.ingest(self.user,private.kb_id,'content',**kw)
    def test_controlled_uploads_start_draft_ordinary_editor_cannot_publish(self):
        kb=self.client.create_kb(self.admin,'regulated',visibility='enterprise',governance_tier='l2_controlled')
        self.client.grant_kb_member(self.admin,kb.kb_id,self.user.user_id,'editor')
        version=self.client.ingest(self.user,kb.kb_id,'controlled')
        self.assertEqual(self.client.store.get_document(version.doc_id).lifecycle_state,'draft')
        with self.assertRaisesRegex(PermissionDeniedError,'lifecycle_not_published'):self.client.retrieve(Actor('peer','org'),version.doc_id)
        with self.assertRaises(PermissionDeniedError):self.client.ingest(self.user,kb.kb_id,'controlled',doc_id=version.doc_id,lifecycle_state='published')
        self.client.ingest(self.admin,kb.kb_id,'controlled',doc_id=version.doc_id,lifecycle_state='published')
        self.assertEqual(self.client.retrieve(Actor('peer','org'),version.doc_id).text,'controlled')
        self.client.ingest(self.user,kb.kb_id,'new controlled',doc_id=version.doc_id)
        self.assertEqual(self.client.store.get_document(version.doc_id).lifecycle_state,'draft')
    def test_document_scoped_write_deny_blocks_creation_and_version_updates(self):
        original=self.client.store.get_document(self.version.doc_id).current_version
        self.client.policy_engine=DefaultPolicyEngine([PolicyRule('no-write','org',DENY,scope_doc_id=self.version.doc_id,actions=(A.WRITE_DOCUMENT,))])
        with self.assertRaisesRegex(PermissionDeniedError,'explicit_policy_deny'):
            self.client.ingest(self.admin,self.kb.kb_id,'replacement',doc_id=self.version.doc_id)
        self.assertEqual(self.client.store.get_document(self.version.doc_id).current_version,original)
        self.client.policy_engine=DefaultPolicyEngine([PolicyRule('no-create','org',DENY,scope_doc_id='blocked-new',actions=(A.WRITE_DOCUMENT,))])
        with self.assertRaisesRegex(PermissionDeniedError,'explicit_policy_deny'):
            self.client.ingest(self.admin,self.kb.kb_id,'creation',doc_id='blocked-new')
        from knowledge_sdk import NotFoundError
        with self.assertRaises(NotFoundError):self.client.store.get_document('blocked-new')

    def test_upload_write_receipt_does_not_leak_missing_hook_body(self):
        v=self.client.ingest(self.admin,self.kb.kb_id,'hidden 123-45-6789',rights=ResourceRights(redaction_profile='missing'))
        self.assertEqual(v.text,'');self.assertEqual(v.raw_hash,'');self.assertIsNone(v.blob_key)
        self.assertEqual(self.client.search(self.user,'hidden').hits,[])
    def test_ask_default_purpose_inference_and_explicit_override(self):
        self.rights(allowed_purposes=(READ,))
        self.assertEqual(self.client.ask(self.user,'alpha').status,'answered')
        spy=GeneratorSpy();self.assertEqual(self.client.ask(self.user,'alpha',generator=spy).status,'refused');self.assertEqual(spy.calls,0)
        self.assertEqual(self.client.ask(self.user,'alpha',generator=spy,purpose=READ).status,'answered');self.assertEqual(spy.calls,1)
    def test_rights_change_between_search_and_generate_never_calls_generator(self):
        client=self.client;original=client.policy_engine;docid=self.version.doc_id
        class RevokeOnSearch:
            def evaluate(self,*args,**kwargs):
                decision=original.evaluate(*args,**kwargs)
                action=kwargs.get('action',args[6] if len(args)>6 else A.READ_CONTENT)
                if action==A.SEARCH_INDEX:
                    client.store.put_document(replace(client.store.get_document(docid),rights=ResourceRights(revoked=True)))
                return decision
        client.policy_engine=RevokeOnSearch()
        spy=GeneratorSpy();answer=client.ask(self.user,'alpha',generator=spy)
        self.assertEqual((answer.status,answer.model_called,spy.calls),('refused',False,0))
    def test_acl_change_between_search_and_generate_never_calls_generator(self):
        client=self.client;original=client.policy_engine;docid=self.version.doc_id
        class DenyOnSearch:
            def evaluate(self,*args,**kwargs):
                decision=original.evaluate(*args,**kwargs)
                action=kwargs.get('action',args[6] if len(args)>6 else A.READ_CONTENT)
                if action==A.SEARCH_INDEX:client.store.set_acl(docid,DocumentACL(deny_users=['user']))
                return decision
        client.policy_engine=DenyOnSearch();spy=GeneratorSpy();answer=client.ask(self.user,'alpha',generator=spy)
        self.assertEqual((answer.status,answer.model_called,spy.calls),('refused',False,0))
    def test_vector_and_hybrid_candidates_obey_current_rights_and_masks(self):
        from tests.helpers import MemoryIndex
        from knowledge_sdk.retrieval.adapters.hash_embedder import HashEmbedder
        c=LocalKnowledgeClient(vector_index=MemoryIndex(),embedder=HashEmbedder())
        self.addCleanup(c.store.close)
        kb=c.create_kb(self.admin,'vector',space_type='enterprise_public')
        v=c.ingest(self.admin,kb.kb_id,'alpha 123-45-6789')
        c.set_document_rights(self.admin,v.doc_id,ResourceRights(redaction_profile='pii'))
        for mode in ('vector','hybrid'):
            self.assertEqual(c.search(self.user,'alpha',mode=mode).hits,[])
        c.redaction_registry.register('pii',RegexRedactionHook([('123-45-6789','[MASK]')]))
        for mode in ('vector','hybrid'):
            hit=c.search(self.user,'alpha',mode=mode).hits[0]
            self.assertNotIn('123-45-6789',hit.excerpt)
            self.assertEqual(hit.excerpt_hash,sha256(hit.excerpt))
        c.set_document_rights(self.admin,v.doc_id,ResourceRights(revoked=True))
        for mode in ('keyword','vector','hybrid'):
            self.assertEqual(c.search(self.user,'alpha',mode=mode).hits,[])

    def test_historical_versions_and_multi_chunks_are_masked_and_consumable(self):
        text='# One\nalpha 123-45-6789\n\n# Two\nsecond 123-45-6789'
        v=self.client.ingest(self.admin,self.kb.kb_id,text,filename='source.md')
        self.client.ingest(self.admin,self.kb.kb_id,text+' changed',filename='source.md',doc_id=v.doc_id)
        self.client.set_document_rights(self.admin,v.doc_id,ResourceRights(redaction_profile='pii'));self.register()
        inspection=self.client.inspect_document(self.user,v.doc_id,1)
        self.assertNotIn('123-45-6789',json.dumps(encode(inspection)))
        ids=[c.chunk_id for c in inspection['chunks']]
        ref=self.client.reference(self.user,v.doc_id,1,ids)
        self.assertNotIn('123-45-6789',ref.excerpt)
        self.assertEqual(self.client.consume(self.user,ref).status,'partial')

    def test_policy_change_during_redaction_hooks_checked_before_generation(self):
        client=self.client;docid=self.version.doc_id
        class RevokeDuringHook:
            def redact(self,text,*args):
                client.store.put_document(replace(client.store.get_document(docid),rights=ResourceRights(revoked=True)))
                return text.replace('123-45-6789','[MASK]'),'redacted'
        self.rights(redaction_profile='revokes');client.redaction_registry.register('revokes',RevokeDuringHook())
        spy=GeneratorSpy();answer=client.ask(self.user,'alpha',generator=spy)
        self.assertEqual((answer.status,answer.model_called,spy.calls),('refused',False,0))

    def test_consumer_receipt_rechecks_with_binding_and_context(self):
        binding=ConsumerBinding('cycle','c',KnowledgeScope('documents',doc_ids=(self.version.doc_id,)))
        ref=self.client.reference(self.user,self.version.doc_id,excerpt='alpha')
        attached=self.client.attach(self.user,ref,binding)
        self.rights(revoked=True)
        self.assertFalse(self.client.verify_receipt(self.user,ref,attached.receipt,binding))

    def test_schema_one_and_old_sqlite_json_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'legacy.sqlite3';store=SQLiteStore(path)
            tables=[r[0] for r in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            kb={'__type__':'KnowledgeBase','kb_id':'old-k','org_id':'org','name':'legacy','owner_id':'admin','visibility':'enterprise'}
            d={'__type__':'Document','doc_id':'old-d','org_id':'org','kb_id':'old-k','owner_id':'admin','title':'legacy','visibility':'enterprise'}
            store.db.execute('INSERT INTO knowledge_bases VALUES (?,?,?)',('old-k','org',json.dumps(kb)))
            store.db.execute('INSERT INTO documents VALUES (?,?,?,?)',('old-d','org','old-k',json.dumps(d)))
            store.close();store=SQLiteStore(path)
            try:
                self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0],1)
                self.assertEqual([r[0] for r in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")],tables)
                self.assertEqual(store.get_document('old-d').lifecycle_state,'published')
                self.assertEqual(store.get_kb('old-k').governance_tier,'l1_agile')
            finally:store.close()


class GeneratorSpy:
    def __init__(self):self.calls=0;self.text=''
    def generate(self,question,evidence_hits,scope,actor):
        self.calls+=1;self.text=' '.join(h.excerpt for h in evidence_hits)
        return GeneratedAnswer(self.text,True)  # deterministic local stub, no external model
