"""Explicit local-only injection boundary; SDK never loads a model or URL."""
from __future__ import annotations
from dataclasses import dataclass
from ..rerank import identifier
from ...exceptions import ValidationError

@dataclass(frozen=True)
class CallableRerankerAdapter:
    reranker_id: str
    scorer: object
    def __post_init__(self):
        identifier(self.reranker_id)
        if not callable(self.scorer):raise ValidationError('Local scorer callable required')
    def score(self,query,candidates):
        # Callable receives only the exact frozen controlled candidate contract.
        return self.scorer(query,candidates)
