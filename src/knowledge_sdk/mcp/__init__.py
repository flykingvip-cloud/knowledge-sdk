"""Python3.9+ stdlib MCP kernel; optional HTTP imports only on explicit startup."""
from __future__ import annotations
from .tools import EvidenceTools,tool_definitions
from .protocol import MCPProtocol
from .gateway import GatewayContext,GatewayAuthenticator

def create_app(*args,**kwargs):
    from .server import create_app as factory
    return factory(*args,**kwargs)
