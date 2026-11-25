"""Tenant-bound RFC 7644 core users/groups; directory, audit and outbox commit together."""
from __future__ import annotations
from dataclasses import asdict,replace
import uuid
import re
from ..contracts.identity import IdentityPrincipal
from ..contracts.events import OutboxEvent
from ..contracts.policy import DecisionEffect
from ..audit.ledger import append
from ..governance.workflow import now
from ..exceptions import ValidationError,PermissionDeniedError,NotFoundError,ConflictError

USER_SCHEMA='urn:ietf:params:scim:schemas:core:2.0:User'
GROUP_SCHEMA='urn:ietf:params:scim:schemas:core:2.0:Group'
LIST_SCHEMA='urn:ietf:params:scim:api:messages:2.0:ListResponse'


def user_resource(p):
    return {'schemas':[USER_SCHEMA],'id':p.user_id,'externalId':p.external_id,'userName':p.username,'active':p.active,'roles':list(p.roles),'department_ids':list(p.department_ids),'org_roles':list(p.org_roles),'clearance_level':p.clearance_level,'clearance_tags':list(p.clearance_tags),'policy_generation':p.policy_generation,'meta':{'resourceType':'User'}}


class SCIMService:
    def __init__(self,client):self.client=client;self.store=client.store
    def _admin(self,actor):
        try:
            self.client._check_principal(actor)
            if not set(actor.org_roles)&{'admin','manage_org','scim_admin'}:raise PermissionDeniedError('scim_admin_required')
        except PermissionDeniedError:
            self.client._audit_operation(actor,'scim',{},None,denied=True);raise
    def _event(self,actor,p,created=False):
        append(self.store,actor,'scim.principal_updated',reason='principal_created' if created else 'principal.policy_bumped')
        t=now()
        event=OutboxEvent(str(uuid.uuid4()),actor.org_id,'principal',p.user_id,'principal.policy_bumped',{'user_id':p.user_id,'policy_generation':p.policy_generation},available_at=t,created_at=t)
        self.store.enqueue_outbox(event);self.client._runtime_event(event)
    def users(self,actor):
        self._admin(actor);return [user_resource(p) for p in self.store.list_principals(actor.org_id)]
    def get(self,actor,user_id):
        self._admin(actor);p=self.store.get_principal(actor.org_id,user_id)
        if p is None:raise NotFoundError('Principal not found')
        return user_resource(p)
    def write(self,actor,data,user_id=None,*,replace_all=False,delete=False):
        self._admin(actor)
        if not isinstance(data,dict):raise ValidationError('Expected SCIM object')
        if 'org_id' in data and data['org_id']!=actor.org_id:raise PermissionDeniedError('tenant_mismatch')
        if 'policy_generation' in data:raise ValidationError('Generation is server controlled')
        user_id=user_id or data.get('id') or str(uuid.uuid4())
        if not isinstance(user_id,str) or not user_id:raise ValidationError('Invalid user id')
        with self.client._lock,self.store.runtime_transaction():
            self._admin(actor)
            self.store.lock_identity(actor.org_id,user_id)
            old=self.store.get_principal(actor.org_id,user_id)
            if old is None and (delete or replace_all):raise NotFoundError('Principal not found')
            if old is not None and data.get('_create'):raise ConflictError('Principal exists')
            p=IdentityPrincipal(actor.org_id,user_id) if old is None or replace_all else old
            keys={'externalId':'external_id','userName':'username','active':'active','roles':'roles','department_ids':'department_ids','org_roles':'org_roles','clearance_level':'clearance_level','clearance_tags':'clearance_tags'}
            values={}
            for k,n in keys.items():
                if k in data:
                    v=data[k]
                    if k=='roles' and isinstance(v,list):v=[x.get('value') if isinstance(x,dict) else x for x in v]
                    values[n]=v
            if delete:values['active']=False
            p=replace(p,**values)
            if old is not None:
                changed=any(getattr(p,n)!=getattr(old,n) for n in ('active','roles','department_ids','org_roles','clearance_level','clearance_tags'))
                p=replace(p,policy_generation=old.policy_generation+int(changed))
            p=replace(p,updated_at=now())
            self.store.upsert_principal(p)
            # Even a no-op is audited; an identical replay never increments generation.
            if old is None or p.policy_generation!=old.policy_generation:self._event(actor,p,old is None)
            else:append(self.store,actor,'scim.principal_noop')
            return user_resource(p)
    def patch(self,actor,user_id,data):
        self._admin(actor)
        if self.store.get_principal(actor.org_id,user_id) is None:raise NotFoundError('Principal not found')
        values={}
        ops=data.get('Operations') if isinstance(data,dict) else None
        if not isinstance(ops,list) or not ops:raise ValidationError('Invalid SCIM patch')
        for op in ops:
            if not isinstance(op,dict) or str(op.get('op','')).lower() not in ('add','replace','remove'):raise ValidationError('Invalid SCIM operation')
            path=op.get('path');v=op.get('value')
            if path is None and isinstance(v,dict):values.update(v);continue
            if path not in ('userName','externalId','active','roles','department_ids','org_roles','clearance_level','clearance_tags'):raise ValidationError('Unsupported SCIM path')
            if str(op['op']).lower()=='remove':v=[] if path in ('roles','department_ids','org_roles','clearance_tags') else False if path=='active' else ''
            values[path]=v
        return self.write(actor,values,user_id)
    def groups(self,actor):
        self._admin(actor);return [self._group_resource(g) for g in self.store.list_scim_groups(actor.org_id)]
    @staticmethod
    def _group_resource(g):return dict(g,schemas=[GROUP_SCHEMA],members=[{'value':u} for u in g['members']])
    def group_write(self,actor,data,group_id=None):
        self._admin(actor)
        if not isinstance(data,dict):raise ValidationError('Invalid group')
        if 'org_id' in data and data['org_id']!=actor.org_id:raise PermissionDeniedError('tenant_mismatch')
        with self.client._lock,self.store.runtime_transaction():
            self._admin(actor)
            # Tenant-wide group lock prevents concurrent membership lost updates.
            self.store.lock_identity(actor.org_id,'__scim_groups__')
            if group_id is None:
                group_id=data.get('id') or str(uuid.uuid4())
                try:self.store.get_scim_group(actor.org_id,group_id)
                except NotFoundError:pass
                else:raise ConflictError('Group exists')
                old={'id':group_id,'displayName':data.get('displayName',group_id),'members':[],'kind':data.get('kind','department')}
                new=dict(old);new['members']=self._members(data.get('members',[]))
            else:
                old=self.store.get_scim_group(actor.org_id,group_id);new=dict(old);new['members']=list(old['members'])
                ops=data.get('Operations')
                if not isinstance(ops,list) or not ops:raise ValidationError('Invalid SCIM patch')
                for op in ops:
                    if not isinstance(op,dict):raise ValidationError('Invalid SCIM operation')
                    kind=str(op.get('op','')).lower();path=op.get('path');v=op.get('value')
                    if kind not in ('add','replace','remove'):raise ValidationError('Invalid SCIM operation')
                    match=re.fullmatch(r'members\[value eq "([^"\x00-\x1f]+)"\]',path or '')
                    if match and kind=='remove':
                        new['members']=[u for u in new['members'] if u!=match[1]]
                    elif path=='members':
                        members=self._members(v or [])
                        if kind=='replace':new['members']=members
                        elif kind=='add':new['members']=list(dict.fromkeys(new['members']+members))
                        elif not v:new['members']=[]
                        else:new['members']=[x for x in new['members'] if x not in members]
                    elif path=='displayName' and kind=='replace' and isinstance(v,str):new['displayName']=v
                    else:raise ValidationError('Unsupported group patch path')
            if new['kind'] not in ('department','role','org_role'):raise ValidationError('Invalid group kind')
            field={'department':'department_ids','role':'roles','org_role':'org_roles'}[new['kind']]
            for uid in sorted(set(old['members'])|set(new['members'])):
                self.store.lock_identity(actor.org_id,uid)
                p=self.store.get_principal(actor.org_id,uid)
                if p is None:raise NotFoundError('Group principal not found')
                current=list(getattr(p,field));updated=[v for v in current if v!=old['displayName']]
                if uid in new['members']:updated=list(dict.fromkeys(updated+[new['displayName']]))
                if current!=updated:
                    p=replace(p,**{field:tuple(updated)},policy_generation=p.policy_generation+1,updated_at=now())
                    self.store.upsert_principal(p);self._event(actor,p)
            self.store.put_scim_group(actor.org_id,group_id,new)
            append(self.store,actor,'scim.group_updated')
            return self._group_resource(new)
    @staticmethod
    def _members(value):
        if not isinstance(value,list):raise ValidationError('Invalid group members')
        result=[v.get('value') if isinstance(v,dict) else v for v in value]
        if any(not isinstance(v,str) or not v for v in result):raise ValidationError('Invalid group member')
        return list(dict.fromkeys(result))


def mount_scim(app,client):
    from fastapi import Request
    # FastAPI resolves annotations against module globals.
    globals()['Request']=Request
    from fastapi.responses import JSONResponse,Response
    service=SCIMService(client)
    async def body(request):
        try:value=await request.json()
        except (ValueError,UnicodeError):raise ValidationError('Invalid SCIM JSON') from None
        if not isinstance(value,dict):raise ValidationError('Expected SCIM object')
        return value
    def listing(values,request):
        filter_value=request.query_params.get('filter')
        if filter_value is not None:
            match=re.fullmatch(r'(id|userName|externalId|active|displayName) eq (?:(true|false)|"([^"\x00-\x1f]*)")',filter_value)
            if not match:raise ValidationError('Unsupported SCIM filter')
            expected=(match[2]=='true') if match[2] else match[3]
            values=[v for v in values if v.get(match[1])==expected]
        try:start=max(1,int(request.query_params.get('startIndex','1')));count=min(1000,max(0,int(request.query_params.get('count','100'))))
        except ValueError:raise ValidationError('Invalid pagination')
        return {'schemas':[LIST_SCHEMA],'totalResults':len(values),'startIndex':start,'itemsPerPage':len(values[start-1:start-1+count]),'Resources':values[start-1:start-1+count]}
    @app.post('/scim/v2/Users',status_code=201)
    async def create_user(request:Request):
        data=await body(request);data['_create']=True
        return service.write(request.state.actor,data)
    @app.get('/scim/v2/Users')
    async def users(request:Request):return listing(service.users(request.state.actor),request)
    @app.get('/scim/v2/Users/{user_id}')
    async def user(user_id:str,request:Request):return service.get(request.state.actor,user_id)
    @app.patch('/scim/v2/Users/{user_id}')
    async def patch(user_id:str,request:Request):return service.patch(request.state.actor,user_id,await body(request))
    @app.put('/scim/v2/Users/{user_id}')
    async def put(user_id:str,request:Request):return service.write(request.state.actor,await body(request),user_id,replace_all=True)
    @app.delete('/scim/v2/Users/{user_id}',status_code=204)
    async def delete(user_id:str,request:Request):
        service.write(request.state.actor,{},user_id,delete=True);return Response(status_code=204)
    @app.post('/scim/v2/Groups',status_code=201)
    async def create_group(request:Request):return service.group_write(request.state.actor,await body(request))
    @app.get('/scim/v2/Groups')
    async def groups(request:Request):return listing(service.groups(request.state.actor),request)
    @app.patch('/scim/v2/Groups/{group_id}')
    async def patch_group(group_id:str,request:Request):return service.group_write(request.state.actor,await body(request),group_id)
