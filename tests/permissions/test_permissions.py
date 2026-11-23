from __future__ import annotations
from knowledge_sdk import *
from tests.helpers import ClientCase
class PermissionTests(ClientCase):
    def grant(self,role="viewer"): self.c.grant_kb_member(self.a,self.k.kb_id,"viewer",role)
    def test_cross_org_cannot_read(self):
        with self.assertRaises(PermissionDeniedError): self.c.get_document(self.other,self.v.doc_id)
        self.assertEqual(self.c.list_kbs(self.other),[])
        self.assertEqual(self.c.search(self.other,"Knowledge").hits,[])
    def test_team_membership(self):
        self.assertEqual(self.c.list_documents(self.viewer),[]); self.grant()
        self.assertEqual(len(self.c.list_documents(self.viewer)),1)
    def test_private_document(self):
        self.grant(); v=self.c.ingest(self.a,self.k.kb_id,"secret",visibility="private")
        with self.assertRaises(PermissionDeniedError): self.c.retrieve(self.viewer,v.doc_id)
    def test_enterprise_not_cross_org(self):
        k=self.c.create_kb(self.a,"Enterprise","enterprise"); v=self.c.ingest(self.a,k.kb_id,"common")
        self.assertEqual(self.c.retrieve(self.viewer,v.doc_id).text,"common")
        with self.assertRaises(PermissionDeniedError): self.c.retrieve(self.other,v.doc_id)
    def test_enterprise_doc_cannot_bypass_private_kb(self):
        k=self.c.create_kb(self.a,"Private"); v=self.c.ingest(self.a,k.kb_id,"common",visibility="enterprise")
        with self.assertRaises(PermissionDeniedError): self.c.retrieve(self.viewer,v.doc_id)
    def test_viewer_cannot_write(self):
        self.grant()
        with self.assertRaises(PermissionDeniedError): self.c.ingest(self.viewer,self.k.kb_id,"bad")
        with self.assertRaises(PermissionDeniedError): self.c.archive(self.viewer,self.v.doc_id)
    def test_editor_can_write_not_grant(self):
        self.grant("editor"); self.c.ingest(self.viewer,self.k.kb_id,"new")
        with self.assertRaises(PermissionDeniedError): self.c.grant_kb_member(self.viewer,self.k.kb_id,"x","admin")
        with self.assertRaises(PermissionDeniedError): self.c.set_document_acl(self.viewer,self.v.doc_id,DocumentACL())
    def test_admin_can_manage(self):
        self.grant("admin"); self.c.grant_kb_member(self.viewer,self.k.kb_id,"x","viewer")
        self.assertEqual(self.c.store.member_role(self.k.kb_id,"x"),"viewer")
    def test_deny_overrides_owner(self):
        self.c.set_document_acl(self.a,self.v.doc_id,DocumentACL(deny_users=["owner"]))
        with self.assertRaises(PermissionDeniedError): self.c.retrieve(self.a,self.v.doc_id)
    def test_explicit_allow_and_deny(self):
        self.grant(); self.c.set_document_acl(self.a,self.v.doc_id,DocumentACL(allow_users=["viewer"],deny_users=["viewer"]))
        with self.assertRaises(PermissionDeniedError): self.c.retrieve(self.viewer,self.v.doc_id)
    def test_role_allowlist(self):
        self.grant(); self.c.set_document_acl(self.a,self.v.doc_id,DocumentACL(allow_roles=["finance"]))
        self.assertEqual(self.c.search(self.viewer,"Knowledge").hits,[])
        self.assertTrue(self.c.retrieve(Actor("viewer","org",("finance",)),self.v.doc_id).text)
    def test_department_acl(self):
        self.grant(); self.c.set_document_acl(self.a,self.v.doc_id,DocumentACL(allow_departments=["research"]))
        actor=Actor("viewer","org",department_ids=("research",))
        self.assertTrue(self.c.retrieve(actor,self.v.doc_id).text)
        self.c.set_document_acl(self.a,self.v.doc_id,DocumentACL(allow_departments=["research"],deny_departments=["research"]))
        with self.assertRaises(PermissionDeniedError): self.c.retrieve(actor,self.v.doc_id)
    def test_doc_id_collision_cannot_cross_tenant(self):
        k=self.c.create_kb(self.other,"Other")
        with self.assertRaises(PermissionDeniedError): self.c.ingest(self.other,k.kb_id,"attack",doc_id=self.v.doc_id)
    def test_kb_id_collision(self):
        with self.assertRaises(ConflictError): self.c.create_kb(self.other,"X",kb_id=self.k.kb_id)
    def test_invalid_visibility_and_role(self):
        with self.assertRaises(ValidationError): self.c.create_kb(self.a,"X","public")
        with self.assertRaises(ValidationError): self.c.grant_kb_member(self.a,self.k.kb_id,"x","root")

    def test_malformed_identity_and_acl_rejected(self):
        for kwargs in ({"allow_users":"viewer"},{"deny_roles":[1]},{"allow_departments":None}):
            with self.assertRaises(ValidationError): DocumentACL(**kwargs)
        with self.assertRaises(ValidationError): Actor("u","o",roles="admin")
        with self.assertRaises(ValidationError): Actor(1,"o")
