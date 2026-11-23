from __future__ import annotations
class KnowledgeSDKError(Exception):
    """Base SDK exception."""
class PermissionDeniedError(KnowledgeSDKError): pass
class NotFoundError(KnowledgeSDKError): pass
class ValidationError(KnowledgeSDKError): pass
class TamperedExcerptError(ValidationError): pass
class ConflictError(KnowledgeSDKError): pass
