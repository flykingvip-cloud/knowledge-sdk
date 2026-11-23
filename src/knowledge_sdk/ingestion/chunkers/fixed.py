from __future__ import annotations
from ...contracts.models import Chunk
from ...exceptions import ValidationError
from ..fingerprint import sha256
class FixedChunker:
    def __init__(self,size=1200,overlap=120):
        if size<1 or overlap<0 or overlap>=size: raise ValidationError("Require 0 <= overlap < size")
        self.size=size; self.overlap=overlap
    def split(self,text,doc_id,version):
        chunks=[]
        for start in range(0,len(text),self.size-self.overlap):
            end=min(start+self.size,len(text)); content=text[start:end]; digest=sha256(content)
            cid=sha256(doc_id+":"+str(start)+":"+digest)[:32]
            chunks.append(Chunk(cid,doc_id,version,content,start,end,digest))
            if end==len(text): break
        return chunks
