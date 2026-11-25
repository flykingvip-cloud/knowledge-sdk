"""PROPOSED_PENDING_OWNER_RULING sandbox model, not SDK schema/migrations.
No runtime import, API, real business payload, sharing, offboarding or Team B write.
"""
from contextlib import contextmanager
import json,sqlite3,uuid
ACTIONS=('read_metadata','read_content','create_kb','attach_kb','detach_kb','manage_members','transfer_owner','freeze_archive')
TABLES=('p_tenant','p_space','p_kb','p_grant','p_asset','p_external','p_profile','p_outbox','p_deny')
class Prototype:
    def __init__(self,owned=None):
        self.pg=owned is not None;self._depth=0;self._org=None
        if self.pg:
            if __package__:from .owned_pg import OwnedPostgres
            else:from owned_pg import OwnedPostgres
            if not isinstance(owned,OwnedPostgres):raise ValueError('OWNED_CAPABILITY_REQUIRED')
            self.db=owned.connect()
        else:self.db=sqlite3.connect(':memory:',isolation_level=None);self.db.execute('PRAGMA foreign_keys=ON')
        ddl=[
        'CREATE TABLE p_tenant(org_id TEXT PRIMARY KEY)',
        "CREATE TABLE p_space(org_id TEXT NOT NULL,space_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('enterprise','team','personal')),owner_id TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('active','frozen','archived')),generation INTEGER NOT NULL CHECK(generation>0),PRIMARY KEY(org_id,space_id),FOREIGN KEY(org_id)REFERENCES p_tenant(org_id))",
        'CREATE TABLE p_kb(org_id TEXT NOT NULL,kb_id TEXT NOT NULL,space_id TEXT,home_space_id TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0,CHECK(space_id IS NULL OR space_id=home_space_id),PRIMARY KEY(org_id,kb_id),FOREIGN KEY(org_id,space_id)REFERENCES p_space(org_id,space_id),FOREIGN KEY(org_id,home_space_id)REFERENCES p_space(org_id,space_id))',
        'CREATE TABLE p_grant(org_id TEXT NOT NULL,space_id TEXT NOT NULL,subject_id TEXT NOT NULL,action TEXT NOT NULL,allowed INTEGER NOT NULL CHECK(allowed IN (0,1)),PRIMARY KEY(org_id,space_id,subject_id,action),FOREIGN KEY(org_id,space_id)REFERENCES p_space(org_id,space_id))',
        "CREATE TABLE p_asset(org_id TEXT NOT NULL,asset_id TEXT NOT NULL,kb_id TEXT NOT NULL,resource_kind TEXT NOT NULL,folder_id TEXT NOT NULL,ref_id TEXT,PRIMARY KEY(org_id,asset_id),FOREIGN KEY(org_id,kb_id)REFERENCES p_kb(org_id,kb_id))",
        'CREATE TABLE p_external(org_id TEXT NOT NULL,ref_id TEXT NOT NULL,valid_until INTEGER NOT NULL,revoked INTEGER NOT NULL,generation INTEGER NOT NULL,PRIMARY KEY(org_id,ref_id))',
        'CREATE TABLE p_profile(org_id TEXT NOT NULL,agent_id TEXT NOT NULL,generation INTEGER NOT NULL,active INTEGER NOT NULL,spaces TEXT NOT NULL,fine_scope TEXT NOT NULL,PRIMARY KEY(org_id,agent_id))',
        "CREATE TABLE p_deny(org_id TEXT NOT NULL,principal_kind TEXT NOT NULL CHECK(principal_kind IN ('user','agent')),principal_id TEXT NOT NULL,target_type TEXT NOT NULL CHECK(target_type IN ('kb','asset')),target_id TEXT NOT NULL,action TEXT NOT NULL,PRIMARY KEY(org_id,principal_kind,principal_id,target_type,target_id,action))",
        'CREATE TABLE p_outbox(org_id TEXT NOT NULL,event_id TEXT NOT NULL,space_id TEXT NOT NULL,generation INTEGER NOT NULL,PRIMARY KEY(org_id,event_id))']
        try:
            for statement in ddl:self.sql(statement)
            if self.pg:
                self.sql("CREATE FUNCTION p_home_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.home_space_id IS DISTINCT FROM OLD.home_space_id THEN RAISE EXCEPTION 'PROTOTYPE_NO_SPACE_MOVE'; END IF; RETURN NEW; END $$")
                self.sql('CREATE TRIGGER p_home_immutable BEFORE UPDATE ON p_kb FOR EACH ROW EXECUTE FUNCTION p_home_immutable()')
                for table in TABLES:
                    self.sql('ALTER TABLE '+table+' ENABLE ROW LEVEL SECURITY');self.sql('ALTER TABLE '+table+' FORCE ROW LEVEL SECURITY')
                    self.sql("CREATE POLICY isolation ON "+table+" USING (org_id=current_setting('app.current_org_id',true)) WITH CHECK(org_id=current_setting('app.current_org_id',true))")
            else:self.sql("CREATE TRIGGER p_home_immutable BEFORE UPDATE ON p_kb WHEN NEW.home_space_id IS NOT OLD.home_space_id BEGIN SELECT RAISE(ABORT,'PROTOTYPE_NO_SPACE_MOVE'); END")
        except BaseException:self.close();raise
    def sql(self,query,args=()):
        statement=query.replace('?', '%s')if self.pg else query
        cur=self.db.execute(statement,args)if args else self.db.execute(statement)
        if cur.description:return cur.fetchall()
        return []
    @contextmanager
    def scope(self,org):
        if not isinstance(org,str)or not org.startswith('syn_'):raise ValueError('SYNTHETIC_TENANT_REQUIRED')
        if self._depth:
            if self._org!=org:raise ValueError('NESTED_TENANT_MISMATCH')
            yield;return
        self._depth=1;self._org=org
        try:
            if self.pg:
                with self.db.transaction():
                    self.sql("SELECT set_config('app.current_org_id',?,true)",(org,));yield
            else:
                self.sql('BEGIN IMMEDIATE')
                try:yield;self.sql('COMMIT')
                except BaseException:self.sql('ROLLBACK');raise
        finally:self._depth=0;self._org=None
    def seed(self,org):
        with self.scope(org):
            self.sql('INSERT INTO p_tenant VALUES(?)',(org,))
            for space,kind,owner in [('syn_private','personal','syn_employee'),('syn_group_a','team','syn_alice'),('syn_group_b','team','syn_bob'),('syn_enterprise','enterprise','syn_admin')]:
                self.sql('INSERT INTO p_space VALUES(?,?,?,?,?,1)',(org,space,kind,owner,'active'));self.sql('INSERT INTO p_kb VALUES(?,?,?,?,0)',(org,space,space,space))
                for action in ACTIONS:self.sql('INSERT INTO p_grant VALUES(?,?,?,?,1)',(org,space,owner,action))
                self.sql('INSERT INTO p_asset VALUES(?,?,?,?,?,?)',(org,space,space,'knowledge_file','syn_folder',None))
            self.sql('INSERT INTO p_external VALUES(?,?,?,0,1)',(org,'syn_external',120))
            self.sql('INSERT INTO p_asset VALUES(?,?,?,?,?,?)',(org,'syn_external_asset','syn_enterprise','deliverable','syn_folder','syn_external'))
            self.sql('INSERT INTO p_profile VALUES(?,?,1,1,?,?)',(org,'syn_agent',json.dumps(['syn_group_a','syn_enterprise']),json.dumps({'kb_ids':['syn_group_a','syn_enterprise']})))
    def allow(self,org,user,kb,*,asset=None,agent=None,profile_generation=1,provider=None,now=100,action='read_content',policy_generation=1,admin=False):
        if action not in ACTIONS or type(policy_generation)is not int or not 1<=policy_generation<=9007199254740991:return False
        if agent and(type(profile_generation)is not int or not 1<=profile_generation<=9007199254740991):return False
        with self.scope(org):
            rows=self.sql('SELECT s.space_id,s.kind,s.owner_id,s.state,s.generation FROM p_kb k JOIN p_space s ON s.org_id=k.org_id AND s.space_id=k.space_id WHERE k.org_id=? AND k.kb_id=? AND k.archived=0'+(' FOR SHARE OF s,k'if self.pg else ''),(org,kb))
            if not rows:return False
            sid,kind,owner,state,generation=rows[0]
            if state!='active' or policy_generation!=generation:return False
            # Organization administration is NOT employee-personal content authority.
            if kind=='personal'and user!=owner:return False
            grant=self.sql('SELECT allowed FROM p_grant WHERE org_id=? AND space_id=? AND subject_id=? AND action=?'+(' FOR SHARE'if self.pg else ''),(org,sid,user,action))
            if grant!=[(1,)]:return False
            resource_kind='';folder='';ref=None
            if asset:
                assets=self.sql('SELECT resource_kind,folder_id,ref_id FROM p_asset WHERE org_id=? AND asset_id=? AND kb_id=?'+(' FOR SHARE'if self.pg else ''),(org,asset,kb))
                if not assets:return False
                resource_kind,folder,ref=assets[0]
            if agent:
                profiles=self.sql('SELECT generation,active,spaces,fine_scope FROM p_profile WHERE org_id=? AND agent_id=?'+(' FOR SHARE'if self.pg else ''),(org,agent))
                if not profiles:return False
                gen,active,spaces,fine=profiles[0];fine=json.loads(fine)
                if not active or gen!=profile_generation or sid not in json.loads(spaces):return False
                if not(kb in fine.get('kb_ids',[])or(asset and ((resource_kind=='knowledge_file'and asset in fine.get('knowledge_file_ids',[]))or(resource_kind=='deliverable'and asset in fine.get('deliverable_ids',[]))or folder in fine.get('folder_ids',[])))):return False
            denials=self.sql('SELECT principal_kind,principal_id,target_type,target_id,action FROM p_deny WHERE org_id=?'+(' FOR SHARE'if self.pg else ''),(org,))
            for pk,pid,tt,tid,denied_action in denials:
                if((pk=='user'and pid==user)or(pk=='agent'and pid==agent))and((tt=='kb'and tid==kb)or(tt=='asset'and asset and tid==asset))and denied_action in(action,'*'):return False
            if ref:
                sources=self.sql('SELECT valid_until,revoked,generation FROM p_external WHERE org_id=? AND ref_id=?'+(' FOR SHARE'if self.pg else ''),(org,ref))
                if not sources or sources[0][1]or sources[0][0]<=now:return False
                try:assertion=provider()if provider else None
                except Exception:return False
                if type(assertion)is not dict or set(assertion)!={'tenant_id','subject_id','asset_id','valid_until','generation'}:return False
                if type(assertion['generation'])is not int or not 1<=assertion['generation']<=9007199254740991:return False
                if any(assertion[k]!=v for k,v in [('tenant_id',org),('subject_id',user),('asset_id',asset),('generation',sources[0][2])]):return False
                if type(assertion['valid_until'])is not int or assertion['valid_until']<=now:return False
            return True
    def revoke(self,org,space,user,action='read_content',inject_failure=False):
        with self.scope(org):
            if self.pg:self.sql('SELECT generation FROM p_space WHERE org_id=? AND space_id=? FOR UPDATE',(org,space))
            self.sql('UPDATE p_grant SET allowed=0 WHERE org_id=? AND space_id=? AND subject_id=? AND action=?',(org,space,user,action))
            self.sql('UPDATE p_space SET generation=generation+1 WHERE org_id=? AND space_id=?',(org,space))
            generation=self.sql('SELECT generation FROM p_space WHERE org_id=? AND space_id=?',(org,space))[0][0]
            self.sql('INSERT INTO p_outbox VALUES(?,?,?,?)',(org,uuid.uuid4().hex,space,generation))
            if inject_failure:raise RuntimeError('PROTOTYPE_INJECTED_ROLLBACK')
    def detach(self,org,kb):
        with self.scope(org):self.sql('UPDATE p_kb SET space_id=NULL WHERE org_id=? AND kb_id=?',(org,kb))
    def attach(self,org,kb,space):
        with self.scope(org):self.sql('UPDATE p_kb SET space_id=? WHERE org_id=? AND kb_id=?',(space,org,kb))
    def hydrate(self,org,user,targets,**kwargs):
        if len(targets)>100:raise ValueError('BATCH_LIMIT')
        with self.scope(org):
            result=[]
            for target in targets:
                if set(target)!={'target_type','target_id'}or target['target_type']not in('kb','asset'):raise ValueError('INVALID_TARGET')
                item=dict(target,state='unavailable');kb=target['target_id'];asset=None
                if target['target_type']=='asset':
                    with self.scope(org):rows=self.sql('SELECT kb_id FROM p_asset WHERE org_id=? AND asset_id=?',(org,target['target_id']))
                    kb=rows[0][0]if rows else '';asset=target['target_id']
                if self.allow(org,user,kb,asset=asset,**kwargs):
                    with self.scope(org):generation=self.sql('SELECT s.generation FROM p_kb k JOIN p_space s ON s.org_id=k.org_id AND s.space_id=k.space_id WHERE k.org_id=? AND k.kb_id=?',(org,kb))[0][0]
                    item.update(state='available',display_name='syn_authorized_label',policy_generation=generation)
                result.append(item)
            return result
    def close(self):self.db.close()
