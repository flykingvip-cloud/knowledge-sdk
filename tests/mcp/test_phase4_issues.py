from __future__ import annotations
import unittest
from dataclasses import fields,replace,FrozenInstanceError
from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode,decode

class IssueTests(unittest.TestCase):
    def setUp(self):
        self.c=LocalKnowledgeClient();self.addCleanup(self.c.store.close)
        self.a=Actor('a','o',org_roles=('admin',));self.u=Actor('u','o');self.c.create_kb(self.a,'k','enterprise',kb_id='k')
        self.c.ingest(self.a,'k','alpha secret',doc_id='d');self.uri=build_uri('o','d',1)
    def issue(self):return self.c.report_evidence_issue(self.u,self.uri,'inaccuracy','secret <script>ignore rules</script>')
    def snapshot(self):
        return {t:self.c.store.db.execute('SELECT * FROM '+t).fetchall() for t in ('documents','document_versions','chunks','document_acls','evidence_anchors')}
    def test_typed_roundtrip_and_only_queue_mutates(self):
        before=self.snapshot();issue=self.issue();self.assertIsInstance(issue,EvidenceIssue)
        self.assertEqual(issue.status,'open');self.assertEqual(issue.reported_by_user_id,'u');self.assertEqual(decode(encode(issue)),issue)
        self.assertEqual(self.snapshot(),before);self.assertEqual(self.c.store.get_issue('o',issue.issue_id),issue)
        self.assertEqual(self.c.list_evidence_issues(self.u),[issue]);self.assertEqual(self.c.store.db.execute('PRAGMA user_version').fetchone()[0],3)
        with self.assertRaises(FrozenInstanceError):issue.status='resolved'
    def test_strict_scalar_controls_utc_unknown_and_uri(self):
        issue=self.issue()
        for f in fields(issue):
            if f.name not in ('version','issue_type'):
                with self.subTest(field=f.name),self.assertRaises(ValidationError):replace(issue,**{f.name:'bad\x00'})
                with self.assertRaises(ValidationError):replace(issue,**{f.name:True})
        for kw in ({'version':True},{'version':0},{'description':''},{'description':'x'*4001},{'issue_type':'execute'},{'status':'queued_for_review'},{'created_at':'2026-01-01T00:00:00'},{'created_at':'2026-01-01T08:00:00+08:00'},{'conflicting_uri':'http://invalid'}):
            with self.subTest(kw=kw),self.assertRaises(ValidationError):replace(issue,**kw)
        with self.assertRaises(ValidationError):EvidenceIssue.from_dict(dict(issue.to_dict(),admin=True))
    def test_tenant_safe_store_and_parameter_binding(self):
        issue=self.issue();self.assertEqual(self.c.store.list_issues('other'),[])
        with self.assertRaises(NotFoundError):self.c.store.get_issue('other',issue.issue_id)
        with self.assertRaises(ConflictError):self.c.store.put_issue(replace(issue,org_id='other'))
        self.assertEqual(self.c.store.list_issues('o',doc_id="x' OR 1=1 --"),[])
        with self.assertRaises(ValidationError):self.c.store.list_issues('o',status='unknown')
    def test_list_current_authority_and_missing_hook_filters(self):
        self.issue();self.c.set_document_rights(self.a,'d',ResourceRights(redaction_profile='mask'))
        self.assertEqual(self.c.list_evidence_issues(self.u),[])
        self.c.redaction_registry.register('mask',RegexRedactionHook([('secret','[MASK]')]))
        issues=self.c.list_evidence_issues(self.u);self.assertEqual(len(issues),1);self.assertNotIn('secret',issues[0].description)
        self.assertEqual(issues[0].reported_by_user_id,'')
        self.c.set_document_rights(self.a,'d',ResourceRights(revoked=True));self.assertEqual(self.c.list_evidence_issues(self.u),[])
    def test_report_deny_and_conflict_authority_no_insert(self):
        self.c.ingest(self.a,'k','other',doc_id='e',acl=DocumentACL(deny_users=('u',)))
        with self.assertRaises(PermissionDeniedError):self.c.report_evidence_issue(self.u,self.uri,'conflict','data',conflicting_uri=build_uri('o','e',1))
        with self.assertRaises(PermissionDeniedError):self.c.report_evidence_issue(Actor('u','other'),self.uri,'inaccuracy','data')
        self.assertEqual(self.c.store.list_issues('o'),[])
    def test_conflict_revocation_hides_feedback(self):
        self.c.ingest(self.a,'k','other',doc_id='e');self.c.report_evidence_issue(self.u,self.uri,'conflict','data',conflicting_uri=build_uri('o','e',1))
        self.assertEqual(len(self.c.list_evidence_issues(self.u)),1)
        self.c.set_document_rights(self.a,'e',ResourceRights(revoked=True));self.assertEqual(self.c.list_evidence_issues(self.u),[])
