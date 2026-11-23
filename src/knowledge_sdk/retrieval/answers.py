"""Generators receive authorized evidence only. No SDK-owned network calls."""
from __future__ import annotations
from typing import List, Protocol
from ..contracts.models import Actor, SearchHit, KnowledgeScope, GeneratedAnswer


class AnswerGenerator(Protocol):
    def generate(self, question: str, evidence_hits: List[SearchHit], scope: KnowledgeScope,
                 actor: Actor) -> GeneratedAnswer: ...


class ExtractiveAnswerGenerator:
    """Deterministic evidence-only baseline: does not claim generative inference."""
    def generate(self, question: str, evidence_hits: List[SearchHit], scope: KnowledgeScope,
                 actor: Actor) -> GeneratedAnswer:
        return GeneratedAnswer("\n\n".join(f"[{i}] {hit.excerpt}" for i, hit in enumerate(evidence_hits, 1)), False)
