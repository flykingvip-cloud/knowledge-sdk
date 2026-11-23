from __future__ import annotations
import hashlib
import unicodedata

def normalize_text(text):
    return " ".join(unicodedata.normalize("NFC", text).split())
def sha256(value):
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()
def fingerprints(raw, text): return sha256(raw), sha256(normalize_text(text))
def classify(previous, raw_hash, semantic_hash):
    if previous and previous.raw_hash == raw_hash: return "unchanged"
    if previous and previous.semantic_hash == semantic_hash: return "raw_only"
    return "new_semantic_version"
