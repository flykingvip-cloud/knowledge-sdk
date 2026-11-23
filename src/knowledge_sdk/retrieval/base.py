from __future__ import annotations
from typing import Protocol, List
from dataclasses import dataclass
@dataclass
class VectorHit:
    doc_id: str
    version: int
    chunk_id: str
    score: float
class Embedder(Protocol):
    def embed(self, texts: List[str]) -> List[List[float]]: ...
class VectorIndex(Protocol):
    def upsert(self, entries: list) -> None: ...
    def search(self, vector: List[float], limit: int = 100) -> List[VectorHit]: ...
    def delete_document(self, doc_id: str) -> None: ...
class Reranker(Protocol):
    def rerank(self, query: str, hits: list) -> list: ...
