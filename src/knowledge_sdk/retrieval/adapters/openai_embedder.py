"""Dependency-free client for explicitly configured OpenAI-compatible embeddings."""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from typing import Optional

from ...exceptions import KnowledgeSDKError, ValidationError


class EmbeddingError(KnowledgeSDKError):
    """Embedding transport or response failure. Provider bodies are never exposed."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward credentials, custom headers or document text to a redirect.
        return None


class OpenAICompatibleEmbedder:
    """Use a /v1 base URL (or explicit /embeddings endpoint).

    dimensions is an optional provider request, not a local projection. Inferred
    dimensions remain fixed for this instance. batch_size bounds each HTTP call.
    No retries: the host owns rate limits and retry/billing policy.
    """

    non_semantic = False

    def __init__(self, base_url, model, api_key: Optional[str] = None,
                 timeout=30, dimensions=None, extra_headers=None, batch_size=64):
        try:
            url = urlsplit(base_url)
            valid = (url.scheme in ("http", "https") and url.hostname and
                     not url.username and not url.password and not url.query and not url.fragment)
            url.port
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ValidationError("Explicit HTTP(S) embedding URL without credentials/query required")
        if not isinstance(model, str) or not model.strip():
            raise ValidationError("Embedding model required")
        if (not isinstance(timeout, (float, int)) or isinstance(timeout, bool)
                or not math.isfinite(timeout) or timeout <= 0):
            raise ValidationError("Invalid embedding timeout")
        for value in (batch_size, dimensions):
            if value is not None and (type(value) is not int or value < 1):
                raise ValidationError("Invalid embedding batch size or dimensions")
        if batch_size is None:
            raise ValidationError("Embedding batch size required")
        if api_key is not None and (not isinstance(api_key, str) or not api_key or
                                    any(c in api_key for c in "\r\n")):
            raise ValidationError("Invalid embedding credential")
        headers = dict(extra_headers or {})
        for key, value in headers.items():
            if (not isinstance(key, str) or not isinstance(value, str) or not key
                    or any(c in key + value for c in "\r\n")
                    or key.lower() in ("authorization", "content-type", "host", "content-length")):
                raise ValidationError("Invalid or reserved embedding header")
        self.endpoint = base_url.rstrip("/")
        if not self.endpoint.endswith("/embeddings"):
            self.endpoint += "/embeddings"
        self.model = model
        self.timeout = timeout
        self.dimensions = dimensions
        self.batch_size = batch_size
        self._vector_size = dimensions
        self._headers = {"Content-Type": "application/json", **headers}
        if api_key is not None:
            self._headers["Authorization"] = "Bearer " + api_key
        self._opener = urllib.request.build_opener(_NoRedirect())

    def embed(self, texts):
        if not isinstance(texts, (list, tuple)) or not all(isinstance(t, str) for t in texts):
            raise ValidationError("Embedding input must be a text sequence")
        result = []
        expected_size = self._vector_size
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start:start + self.batch_size])
            body = {"model": self.model, "input": batch, "encoding_format": "float"}
            if self.dimensions is not None:
                body["dimensions"] = self.dimensions
            try:
                request = urllib.request.Request(self.endpoint,
                    data=json.dumps(body).encode("utf-8"), headers=self._headers, method="POST")
                with self._opener.open(request, timeout=self.timeout) as response:
                    data = json.load(response)
            except urllib.error.HTTPError as exc:
                status = exc.code
                exc.close()
                raise EmbeddingError("Embedding HTTP request failed (status {})".format(status)) from None
            except Exception:
                # Do not propagate URLs, provider bodies, headers or original errors.
                raise EmbeddingError("Embedding transport or JSON response failed") from None
            try:
                rows = data["data"]
                if not isinstance(rows, list) or len(rows) != len(batch):
                    raise ValueError()
                by_index = {}
                for row in rows:
                    idx = row["index"]
                    vector = row["embedding"]
                    if (type(idx) is not int or not 0 <= idx < len(batch) or idx in by_index
                            or not isinstance(vector, list) or not vector):
                        raise ValueError()
                    if expected_size is None:
                        expected_size = len(vector)
                    if len(vector) != expected_size:
                        raise ValueError()
                    if any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
                        raise ValueError()
                    by_index[idx] = [float(v) for v in vector]
                result.extend(by_index[i] for i in range(len(batch)))
            except Exception:
                raise EmbeddingError("Invalid embedding response: count, indices or vector dimensions/values") from None
        self._vector_size = expected_size
        return result
