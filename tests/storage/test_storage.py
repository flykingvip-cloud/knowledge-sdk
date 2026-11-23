from __future__ import annotations
import tempfile
from pathlib import Path
import unittest
from knowledge_sdk import *
class StorageTests(unittest.TestCase):
    def test_persistence_and_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=SQLiteStore(Path(tmp)/"kb.db"); blobs=LocalBlobStore(Path(tmp)/"blobs")
            c=LocalKnowledgeClient(store,blobs); a=Actor("u","o"); kb=c.create_kb(a,"K"); v=c.ingest(a,kb.kb_id,b"persisted")
            self.assertEqual(blobs.get(v.blob_key),b"persisted"); store.close()
            store=SQLiteStore(Path(tmp)/"kb.db"); c=LocalKnowledgeClient(store)
            self.assertEqual(c.retrieve(a,v.doc_id).text,"persisted"); self.assertTrue(c.search(a,"persisted").hits); store.close()
    def test_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=LocalBlobStore(tmp)
            for org in ["../x","/tmp","a/b","..",""]:
                with self.assertRaises(ValidationError): b.put(org,"doc","abc",b"x")
            with self.assertRaises(ValidationError): b.get("../outside")
    def test_transaction_rolls_back(self):
        c=LocalKnowledgeClient(); a=Actor("u","o"); k=c.create_kb(a,"K")
        original=c.store.put_version
        def fail(*args): raise RuntimeError("storage fault")
        c.store.put_version=fail
        with self.assertRaises(RuntimeError): c.ingest(a,k.kb_id,"atomic")
        self.assertEqual(c.list_documents(a),[]); c.store.put_version=original; c.store.close()
