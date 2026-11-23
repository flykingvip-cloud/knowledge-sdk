from __future__ import annotations
import hashlib
import math
from ...storage.sqlite_store import tokens
class HashEmbedder:
    """Deterministic lexical hashing for tests/offline use, NOT semantic embeddings."""
    non_semantic=True
    dimensions=256
    def embed(self,texts):
        result=[]
        for text in texts:
            v=[0.0]*self.dimensions
            for word in tokens(text):
                digest=hashlib.sha256(word.encode()).digest(); index=int.from_bytes(digest[:4],"big")%self.dimensions
                v[index]+=1.0 if digest[4]%2 else -1.0
            norm=math.sqrt(sum(x*x for x in v)) or 1.0; result.append([x/norm for x in v])
        return result
