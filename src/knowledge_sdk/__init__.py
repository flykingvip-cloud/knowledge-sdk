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

from .contracts.policy import (Purpose, PolicyAction, DecisionEffect, GovernanceTier, AgentIdentity, ResourceRights, PolicyRule, PolicyContext, PolicyDecision)
from .permissions.engine import KnowledgePolicyEngine, DefaultPolicyEngine, intersect_decisions
from .permissions.redaction import RedactionHook, RedactionRegistry, RegexRedactionHook

from .contracts.anchors import (SelectorKind, ReanchorStatus, TextQuoteSelector, PdfBBoxSelector, TableCellSelector, SectionQuoteSelector, EvidenceAnchor)
from .contracts.uri import ParsedKBURI, parse_uri_v2

from .ingestion.parsers.layout import ParsedSpan, LayoutParseResult, LayoutParser
from .contracts.reanchor import build_anchors_from_layout, reanchor_to_version

from .contracts.issues import EvidenceIssue, IssueType

from .contracts.audit import AuditEvent, AuditChainReport

from .contracts.events import OutboxEvent, DispatchSummary
from .impact.webhook import verify_webhook_signature

from .contracts.impact import UsageEvent, ImpactAlert, ImpactReason

from .contracts.governance import ReviewDecision, ReleaseManifest, IssueResolution
from .contracts.packs import PackItem, EvidencePack, PackVerificationReport, ExportResult

from .contracts.identity import IdentityPrincipal, ConnectorSyncState
from .contracts.connectors import ConnectorDocument, ConnectorACLUpdate, TombstoneRecord, ConnectorSyncBatch, ConnectorSyncReport
from .connectors import BaseConnector, ConnectorSyncRunner, ControlledFilesystemConnector, WebhookSyncConnector

from .contracts.runtime import ContextBudget, AgentProfile, TaskContext, SnapshotItem, ContextSnapshot, MidTaskRevocation
