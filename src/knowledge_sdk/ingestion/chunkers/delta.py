from __future__ import annotations
def chunk_delta(previous,current):
    old={c.chunk_hash for c in previous}; new={c.chunk_hash for c in current}
    return {"added":[c for c in current if c.chunk_hash not in old],
            "unchanged":[c for c in current if c.chunk_hash in old],
            "removed":[c for c in previous if c.chunk_hash not in new]}
