from __future__ import annotations
from .contracts.models import (Actor, KnowledgeBase, Document, DocumentVersion, Chunk, DocumentACL, KnowledgeRef, MaterialReceipt, ExcerptPolicy, SearchHit, SearchResponse, RetrieveResponse)
from .contracts.uri import build_uri, parse_uri
from .exceptions import (KnowledgeSDKError, PermissionDeniedError, NotFoundError, ValidationError, TamperedExcerptError, ConflictError)
from .client.local import LocalKnowledgeClient
from .client.http_client import HttpKnowledgeClient
from .client.base import KnowledgeClient
from .storage.sqlite_store import SQLiteStore
from .storage.local_blob import LocalBlobStore
__version__ = "1.2.0"
from .retrieval.adapters.openai_embedder import OpenAICompatibleEmbedder, EmbeddingError

from .contracts.models import (SpaceType, KnowledgeScope, ConsumerBinding, GeneratedAnswer, KnowledgeAnswer, Attachment)
from .retrieval.answers import AnswerGenerator, ExtractiveAnswerGenerator
from .permissions import can_manage_kb, can_upload_to_kb, expand_department_ancestors
