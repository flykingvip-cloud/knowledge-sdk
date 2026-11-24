"""Optional MCP surface. Handler/contracts stay stdlib-only; wire is lazy."""
from __future__ import annotations
from .gateway import GatewayContext, GatewayAuthenticator
from .handlers import EvidenceTools, tool_definitions


def create_app(*args,**kwargs):
    # Import the official optional transport only on explicit application creation.
    from .transport import create_app as factory
    return factory(*args,**kwargs)
