"""Legacy lineage fixture setup: task labels now resolve to registered contexts.
No production API accepts caller-chosen task IDs; this is trusted test setup only.
"""
from __future__ import annotations
from dataclasses import replace
from knowledge_sdk import Purpose,NotFoundError


def provision_task(client,admin,actor,agent_id,task_id,purpose=Purpose.GROUND_INTERNAL_LLM):
    try:client.store.get_task_context(actor.org_id,task_id);return
    except NotFoundError:pass
    try:client.get_agent_profile(admin,agent_id)
    except NotFoundError:client.register_agent_profile(admin,agent_id)
    task=client.create_task_context(actor,agent_id,purpose=purpose)
    client.store.put_task_context(replace(task,task_id=task_id))
