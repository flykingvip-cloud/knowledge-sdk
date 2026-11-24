"""Explicit redaction hooks. No missing/failed hook may fall back to plaintext."""
from __future__ import annotations
from copy import deepcopy
import re
from typing import Any, Dict, Protocol, Tuple
from ..contracts.policy import Purpose, enum_value
from ..exceptions import PermissionDeniedError, ValidationError


class RedactionHook(Protocol):
    def redact(self, text: str, profile: str, purpose: Purpose, metadata: Dict[str, Any]) -> Tuple[str, str]:
        ...


class RedactionRegistry:
    def __init__(self): self._hooks = {}

    def register(self, profile, hook):
        if (not isinstance(profile, str) or not profile or profile != profile.strip() or ',' in profile
            or not callable(getattr(hook, 'redact', None))):
            raise ValidationError('Invalid redaction registration')
        self._hooks[profile] = hook

    def has_profile(self, profile):
        return isinstance(profile, str) and profile in self._hooks

    def apply(self, text, profiles, purpose, metadata=None):
        if not isinstance(profiles, str) or not isinstance(text, str):
            raise PermissionDeniedError('redaction_failed')
        names = profiles.split(',') if profiles else []
        if any(not self.has_profile(p) for p in names):
            raise PermissionDeniedError('redaction_hook_missing')
        summaries = []
        try:
            purpose = enum_value(Purpose, purpose)
            if metadata is not None and not isinstance(metadata, dict): raise ValueError()
            for name in names:
                result = self._hooks[name].redact(text, name, purpose, deepcopy(metadata or {}))
                if type(result) is not tuple or len(result) != 2 or not all(isinstance(v, str) for v in result):
                    raise ValueError()
                text, summary = result
                summaries.append(name + ':' + summary)
        except Exception:
            # Do not chain a hook's potentially plaintext-bearing exception.
            raise PermissionDeniedError('redaction_failed') from None
        return text, '; '.join(summaries)


class RegexRedactionHook:
    """Operator-supplied regex rules; deliberately no defaults or auto-register.

    rules is a sequence of (pattern, replacement) strings. Summaries contain only
    substitution counts. Patterns/replacements must be reviewed by the host.
    """
    def __init__(self, rules):
        if not isinstance(rules, (list, tuple)):
            raise ValidationError('Invalid regex rules')
        compiled = []
        try:
            for item in rules:
                if not isinstance(item, (tuple,list)) or len(item) != 2 or not all(isinstance(x,str) for x in item):
                    raise ValueError()
                compiled.append((re.compile(item[0]), item[1]))
        except (ValueError, TypeError, re.error):
            raise ValidationError('Invalid regex rules') from None
        self.rules = tuple(compiled)

    def redact(self, text, profile, purpose, metadata):
        count = 0
        for pattern, replacement in self.rules:
            text, n = pattern.subn(replacement, text); count += n
        return text, 'replacements=' + str(count)
