from __future__ import annotations
import re
from .fixed import FixedChunker
class HierarchicalChunker(FixedChunker):
    def split(self,text,doc_id,version):
        headings=list(re.finditer(r"(?m)^(#{1,6})[ \t]+(.+)$",text))
        boundaries=sorted(set([0]+[m.start() for m in headings]+[len(text)])); stack=[]; result=[]
        by_start={m.start():m for m in headings}
        for start,end in zip(boundaries,boundaries[1:]):
            m=by_start.get(start)
            if m:
                level=len(m[1]); stack=stack[:level-1]; stack.append(m[2].strip())
            for chunk in super().split(text[start:end],doc_id,version):
                chunk.start_offset+=start; chunk.end_offset+=start
                # Include absolute position, stable across re-parsing identical source.
                from ..fingerprint import sha256
                chunk.chunk_id=sha256(doc_id+":"+str(chunk.start_offset)+":"+chunk.chunk_hash)[:32]
                chunk.heading=stack[-1] if stack else ""; chunk.section_path=list(stack); result.append(chunk)
        return result
