"""Reference 1: controlled-root snapshots, stable cursor and ACL sidecars.

All relative opens traverse directory FDs with O_NOFOLLOW (not just a racy
resolve-before-open check). Symlinks are rejected, including internal symlinks.
"""
from __future__ import annotations
from pathlib import Path
import os,json,hashlib,uuid
from ..contracts.connectors import ConnectorDocument,ConnectorSyncBatch,TombstoneRecord
from ..exceptions import ValidationError,PermissionDeniedError
from .base import BaseConnector

class ControlledFilesystemConnector(BaseConnector):
    def __init__(self,connector_id,root,*,org_id,missing_action='revoke',max_bytes=16*1024*1024):
        root=Path(root)
        if root.is_symlink() or not root.is_dir() or missing_action not in ('revoke','archive'):raise ValidationError('Invalid controlled root')
        self.connector_id=connector_id;self.org_id=org_id;self.root=root.resolve();self.missing_action=missing_action;self.max_bytes=max_bytes
    def _read(self,relative):
        parts=Path(relative).parts
        if Path(relative).is_absolute() or any(p in ('..','.','') for p in parts):raise ValidationError('Unsafe source path')
        fd=os.open(str(self.root),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                nextfd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nextfd
            filefd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
            try:
                import stat
                if not stat.S_ISREG(os.fstat(filefd).st_mode):raise ValidationError('Source is not regular')
                with os.fdopen(filefd,'rb',closefd=False) as f:data=f.read(self.max_bytes+1)
                if len(data)>self.max_bytes:raise ValidationError('Source too large')
                return data
            finally:os.close(filefd)
        except OSError:raise ValidationError('Unsafe or unavailable source') from None
        finally:os.close(fd)
    def sync_since(self,cursor,*,org_id,kb_id):
        if org_id!=self.org_id:raise PermissionDeniedError('connector_tenant_mismatch')
        try:previous=json.loads(cursor) if cursor else {}
        except ValueError:raise ValidationError('Invalid filesystem cursor')
        current={};upserts=[];tombstones=[]
        paths=[]
        def failure(error):raise ValidationError('Source enumeration failed')
        for directory,dirs,files in os.walk(self.root,followlinks=False,onerror=failure):
            if any((Path(directory)/d).is_symlink() for d in dirs):raise ValidationError('Source symlink forbidden')
            for name in files:
                if not name.endswith('.acl.json'):paths.append((Path(directory)/name).relative_to(self.root).as_posix())
        for relative in sorted(paths):
            raw=self._read(relative);sha=hashlib.sha256(raw).hexdigest();side={}
            sidepath=self.root/(relative+'.acl.json')
            if sidepath.exists() or sidepath.is_symlink():
                try:side=json.loads(self._read(relative+'.acl.json'))
                except (ValueError,UnicodeError):raise ValidationError('Invalid source ACL sidecar')
                if not isinstance(side,dict):raise ValidationError('Invalid source ACL sidecar')
            doc_id=str(uuid.uuid5(uuid.NAMESPACE_URL,org_id+':'+self.connector_id+':'+relative))
            current[relative]={'sha':sha,'side':side,'doc_id':doc_id}
            if current[relative]==previous.get(relative):continue
            if side.get('deleted') or side.get('revoked'):
                if relative in previous:tombstones.append(TombstoneRecord(relative,doc_id,self.missing_action))
                else:current.pop(relative,None)  # Never track an unsynchronized deleted source.
                continue
            upserts.append(ConnectorDocument(relative,doc_id,kb_id,raw,filename=relative,title=relative,acl=side.get('acl'),rights=side.get('rights'),source_sha256=sha,governance_tier=side.get('governance_tier','l1_agile')))
        for relative,state in sorted(previous.items()):
            if relative not in current:tombstones.append(TombstoneRecord(relative,state['doc_id'],self.missing_action))
        return ConnectorSyncBatch(tuple(upserts),(),tuple(tombstones),json.dumps(current,sort_keys=True,separators=(',',':')))
