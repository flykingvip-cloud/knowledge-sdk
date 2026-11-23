from __future__ import annotations
import os
import re
import tempfile
from pathlib import Path
from ..exceptions import ValidationError
class LocalBlobStore:
    def __init__(self,root): self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
    def _path(self,key):
        p=(self.root/key).resolve()
        if self.root not in p.parents: raise ValidationError("Invalid blob path")
        return p
    def put(self,org_id,doc_id,raw_hash,data):
        if any(not re.fullmatch(r"[A-Za-z0-9_-]+",s) for s in (org_id,doc_id,raw_hash)):
            raise ValidationError("Unsafe blob path component")
        key="/".join((org_id,doc_id,raw_hash)); p=self._path(key); p.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=p.parent,delete=False) as f:
            try:
                f.write(data); f.flush(); os.fsync(f.fileno()); temp=f.name
            except BaseException:
                Path(f.name).unlink(missing_ok=True); raise
        os.replace(temp,p); return key
    def get(self,key): return self._path(key).read_bytes()
