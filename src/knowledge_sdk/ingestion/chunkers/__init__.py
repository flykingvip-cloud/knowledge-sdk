from __future__ import annotations
from typing import Protocol, List
from ...contracts.models import Chunk
class Chunker(Protocol):
    def split(self, text: str, doc_id: str, version: int) -> List[Chunk]: ...
from .fixed import FixedChunker
from .hierarchical import HierarchicalChunker
