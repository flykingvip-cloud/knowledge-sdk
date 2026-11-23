from __future__ import annotations
"""Deterministic local fixtures; no remote services, embeddings, or model calls."""
from ..contracts.models import Actor, DocumentACL, ConsumerBinding, KnowledgeScope


def seed_demo(client):
    admin = Actor("admin", "demo-org", org_roles=("admin", "analyst"),
                  department_ids=("engineering",), managed_department_ids=("engineering",),
                  clearance_level="restricted")
    if client.list_kbs(admin):
        return  # Never modify a non-empty demo database.
    public = client.create_kb(admin, "Company handbook · 企业公共库", space_type="enterprise_public")
    department = client.create_kb(admin, "Engineering · 研发知识库", space_type="department", owner_department_id="engineering")
    personal = client.create_kb(admin, "My notebook · 个人库", space_type="personal")
    fixtures = [
        (public, "Welcome handbook", "# Welcome\nThe company handbook explains onboarding and shared knowledge.\n公共知识：新员工入职指南。", DocumentACL(access_level="org_public")),
        (public, "Engineering launch plan", "# Launch\nProject aurora engineering launch uses staged rollout and rollback.\n研发发布计划：灰度上线与回滚。", DocumentACL(access_level="department", allowed_department_ids=["engineering"], include_sub_departments=True)),
        (public, "Confidential budget", "# Budget\nConfidential finance budget reserve is 12 percent.\n预算密级：confidential。", DocumentACL(access_level="role_clearance", allowed_org_roles=["analyst"], required_clearance="confidential")),
        (public, "Personal research", "# Research\nPrivate nebula research belongs to the author only.", DocumentACL(access_level="personal_only")),
        (department, "Engineering runbook", "# Runbook\nEngineering incident response: inspect, mitigate, then review.", DocumentACL(access_level="org_public")),
        (personal, "My notes", "# Notes\nPersonal knowledge notebook.", DocumentACL(access_level="personal_only")),
    ]
    for kb, title, text, acl in fixtures:
        version = client.ingest(admin, kb.kb_id, text, filename="handbook.md", title=title)
        client.set_document_acl(admin, version.doc_id, acl)
    client.bind_consumer(admin, ConsumerBinding("agent", "demo-assistant", KnowledgeScope("spaces", kb_ids=(public.kb_id,)), "research"))
