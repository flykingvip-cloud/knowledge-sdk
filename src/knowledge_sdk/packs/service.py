"""Policy intersection at creation AND every read. No partial pack delivery."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import uuid
from ..contracts.packs import EvidencePack, PackItem, PackVerificationReport, ExportResult, digest, canonical, plain
from ..contracts.policy import Purpose, PolicyAction, DecisionEffect, enum_value
from ..contracts.impact import UsageEvent
from ..contracts.uri import build_uri
from ..exceptions import PermissionDeniedError, NotFoundError, ConflictError, ValidationError
from ..governance.workflow import operation, now

class PackMixin:
    def _pack_source(self,actor,entry,purpose,*,agent=None,policy_context=None):
        doc_id=entry['doc_id'];version=entry['version']
        if type(version) is not int or version<1:raise ValidationError('Invalid pack version')
        decision=self.evaluate_policy(actor,doc_id,action=PolicyAction.EXPORT_PACK,purpose=purpose,agent=agent,policy_context=policy_context)
        if not decision.allowed:raise PermissionDeniedError('pack_access_denied')
        d=self.store.get_document(doc_id);v=self.store.get_version(doc_id,version)
        if d.org_id!=actor.org_id or d.archived or d.lifecycle_state!='published' or v.lifecycle_state!='published':raise PermissionDeniedError('pack_source_not_published')
        excerpt=v.text
        if entry.get('anchor_id'):
            anchor=self.store.get_anchor(actor.org_id,doc_id,version,entry['anchor_id'])
            if anchor.reanchor_status.value not in ('anchored','exact','relocated'):raise PermissionDeniedError('pack_anchor_unhealthy')
            from ..client.anchors import validate_source, validate_identity
            validate_identity(anchor,actor.org_id,doc_id,version,entry['anchor_id']);validate_source(anchor,v)
            excerpt=anchor.quote.exact
        excerpt,summary=self.redaction_registry.apply(excerpt,decision.redaction_profile,purpose,{'doc_id':doc_id,'version':version})
        return excerpt,summary,decision

    def _pack_lock(self,actor,entries):
        for doc_id in sorted({e['doc_id'] for e in entries}):
            self.store.lock_document(doc_id)
            if self.store.get_document(doc_id).org_id!=actor.org_id:raise PermissionDeniedError('pack_access_denied')

    def _pack_check(self,actor,pack,purpose,*,agent=None,policy_context=None,check_digest=True):
        if pack.org_id!=actor.org_id:raise NotFoundError('Pack not found')
        entries=[plain(i) for i in pack.items]
        self._pack_lock(actor,entries)
        decisions=[]
        try:
            for item in pack.items:
                excerpt,summary,decision=self._pack_source(actor,plain(item),purpose,agent=agent,policy_context=policy_context)
                if hashlib.sha256(excerpt.encode()).hexdigest()!=item.excerpt_hash or excerpt!=item.excerpt:raise PermissionDeniedError('pack_redaction_changed')
                decisions.append(decision)
            profiles=','.join(dict.fromkeys(p for decision in decisions for p in decision.redaction_profile.split(',') if p))
            def unchanged(value):
                if isinstance(value,str):
                    if self.redaction_registry.apply(value,profiles,purpose)[0]!=value:raise PermissionDeniedError('pack_redaction_changed')
                elif isinstance(value,dict):
                    for k,v in value.items():unchanged(k);unchanged(v)
                elif isinstance(value,(list,tuple)):
                    for v in value:unchanged(v)
            unchanged([pack.title,pack.topic,pack.dissent_notes,pack.effective_decision,[i.condition_note for i in pack.items]])
            # A hook can re-enter this client and revoke another item. Recheck
            # every policy AFTER all hooks before returning any sealed plaintext.
            for item,previous in zip(pack.items,decisions):
                current=self.evaluate_policy(actor,item.doc_id,action=PolicyAction.EXPORT_PACK,purpose=purpose,agent=agent,policy_context=policy_context)
                if current!=previous or not current.allowed:raise PermissionDeniedError('pack_access_changed')
                for profile in current.redaction_profile.split(','):
                    if profile and not self.redaction_registry.has_profile(profile):raise PermissionDeniedError('redaction_hook_missing')
                if self.store.get_version(item.doc_id,item.version).lifecycle_state!='published':raise PermissionDeniedError('pack_source_not_published')
            if check_digest and digest(pack)!=pack.pack_sha256:raise ConflictError('Pack digest mismatch')
            if check_digest:
                try:stored=self.store.get_evidence_pack(actor.org_id,pack.pack_id)
                except NotFoundError:stored=None  # construction has not persisted yet
                if stored is not None and (digest(stored)!=pack.pack_sha256 or stored.pack_sha256!=pack.pack_sha256):raise ConflictError('Pack digest mismatch')
        except NotFoundError:raise PermissionDeniedError('pack_access_denied') from None

    @operation
    def create_evidence_pack(self,actor,title,entries,*,topic='',effective_decision=None,dissent_notes=(),seal=True,purpose=Purpose.EXPORT,pack_id=None,agent=None,policy_context=None):
        purpose=enum_value(Purpose,purpose)
        if type(seal) is not bool or not isinstance(entries,(list,tuple)) or not entries or len(entries)>1000:raise ValidationError('Invalid pack entries')
        allowed={'doc_id','version','anchor_id','stance','condition_note'}
        if any(not isinstance(e,dict) or set(e)-allowed or not {'doc_id','version'}<=set(e) for e in entries):raise ValidationError('Invalid pack entry')
        for entry in entries:
            if not isinstance(entry['doc_id'],str) or not entry['doc_id'] or type(entry['version']) is not int or entry['version']<1:raise ValidationError('Invalid pack entry identity')
        self._pack_lock(actor,entries)
        items=[];notes=list(dissent_notes);profiles=[]
        for entry in entries:
            excerpt,summary,decision=self._pack_source(actor,entry,purpose,agent=agent,policy_context=policy_context)
            profiles.extend(decision.redaction_profile.split(',') if decision.redaction_profile else [])
            condition=self.redaction_registry.apply(entry.get('condition_note',''),decision.redaction_profile,purpose)[0]
            item=PackItem(build_uri(actor.org_id,entry['doc_id'],entry['version'],anchor_id=entry.get('anchor_id') or None),entry['doc_id'],entry['version'],entry.get('anchor_id',''),entry.get('stance','supporting'),condition,excerpt,hashlib.sha256(excerpt.encode()).hexdigest(),summary,str(uuid.uuid4()))
            items.append(item)
            notes.extend(r.dissent_note for r in self.store.list_review_decisions(actor.org_id,item.doc_id,item.version) if r.stage=='dissent_recorded')
        profiles=','.join(dict.fromkeys(profiles))
        def mask(v):
            if isinstance(v,str):return self.redaction_registry.apply(v,profiles,purpose)[0]
            if isinstance(v,dict):return {mask(k):mask(x) for k,x in v.items()}
            if isinstance(v,(list,tuple)):return [mask(x) for x in v]
            return v
        pack=EvidencePack(pack_id or str(uuid.uuid4()),actor.org_id,mask(title),mask(topic),actor.user_id,'sealed' if seal else 'draft',purpose,mask(effective_decision or {}),tuple(items),tuple(mask(notes)),created_at=now())
        pack=replace(pack,pack_sha256=digest(pack))
        self._pack_check(actor,pack,purpose,agent=agent,policy_context=policy_context)
        self.store.put_evidence_pack(pack)
        for item in pack.items:
            self.store.put_usage_event(UsageEvent(item.receipt_id,actor.org_id,item.doc_id,item.version,anchor_id=item.anchor_id,consumer_type='evidence_pack',consumer_id=pack.pack_id,actor_id=actor.user_id,agent_id=agent.agent_id if agent else '',purpose=purpose.value,receipt_hash=item.excerpt_hash,created_at=pack.created_at),actor=actor,agent=agent)
        return pack

    @operation
    def get_evidence_pack(self,actor,pack_id,*,purpose=Purpose.EXPORT,agent=None,policy_context=None):
        pack=self.store.get_evidence_pack(actor.org_id,pack_id)
        self._pack_check(actor,pack,purpose,agent=agent,policy_context=policy_context)
        return pack

    @operation
    def list_evidence_packs(self,actor,*,purpose=Purpose.EXPORT,agent=None,policy_context=None):
        result=[]
        for pack in self.store.list_evidence_packs(actor.org_id):
            try:self._pack_check(actor,pack,purpose,agent=agent,policy_context=policy_context)
            except (PermissionDeniedError,ConflictError,NotFoundError):continue
            result.append(pack)
        return result

    @operation
    def verify_evidence_pack(self,actor,pack_id,*,purpose=Purpose.EXPORT,agent=None,policy_context=None):
        pack=self.store.get_evidence_pack(actor.org_id,pack_id)
        self._pack_check(actor,pack,purpose,agent=agent,policy_context=policy_context,check_digest=False)
        alerts=tuple(a for a in self.store.list_impact_alerts(actor.org_id) if a.target_type=='evidence_pack' and a.target_id==pack_id)
        return PackVerificationReport(pack_id,digest(pack)==pack.pack_sha256,pack.status,alerts)

    @operation
    def export_evidence_pack(self,actor,pack_id,*,format='json',output_path=None,purpose=Purpose.EXPORT,agent=None,policy_context=None):
        import base64
        from pathlib import Path
        from .export import render
        if format not in ('json','ro_crate'):raise ValidationError('Invalid pack format')
        pack=self.store.get_evidence_pack(actor.org_id,pack_id)
        self._pack_check(actor,pack,purpose,agent=agent,policy_context=policy_context)
        data=render(pack,format)
        # Final whole-pack recheck precedes BOTH file creation and return.
        self._pack_check(actor,pack,purpose,agent=agent,policy_context=policy_context)
        if output_path is not None:Path(output_path).write_bytes(data)
        return ExportResult(pack_id,format,data.decode('utf-8') if format=='json' else base64.b64encode(data).decode('ascii'),'application/json' if format=='json' else 'application/zip','utf-8' if format=='json' else 'base64',str(output_path or ''),hashlib.sha256(data).hexdigest())
