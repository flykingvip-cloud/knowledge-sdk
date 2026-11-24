from contextlib import closing
from dataclasses import replace
import json
import tempfile
import threading
import unittest
from pathlib import Path
from knowledge_sdk import *
from knowledge_sdk.audit.ledger import append, verify_audit_chain, COLUMNS
from knowledge_sdk.contracts.models import encode, decode


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.c=LocalKnowledgeClient();self.addCleanup(self.c.store.close)
        self.a=Actor('owner','org',org_roles=('admin',));self.reader=Actor('reader','org')
        self.k=self.c.create_kb(self.a,'k','enterprise')
        self.v=self.c.ingest(self.a,self.k.kb_id,'Secret original body',doc_id='d')

    def test_roundtrip_hash_query_no_source_text_and_immutability(self):
        self.c.retrieve(self.reader,'d')
        events=self.c.query_audit_events(self.reader)
        self.assertTrue(events);self.assertTrue(all(e.actor_id=='reader' for e in events))
        self.assertNotIn('Secret original body',json.dumps(encode(events)))
        for event in events:self.assertEqual(decode(encode(event)),event)
        self.assertTrue(self.c.verify_audit_chain(self.a).valid)
        with self.assertRaises(TypeError):events[0].details['body']='sensitive'
        with self.assertRaises(ValidationError):replace(events[0],details={'excerpt':'source text'})

    def test_success_and_denial_automatically_recorded(self):
        ref=self.c.reference(self.reader,'d',excerpt='Secret')
        self.c.consume(self.reader,ref);self.c.attach(self.reader,ref)
        self.c.search(self.reader,'Secret');self.c.archive(self.a,'d');self.c.restore(self.a,'d')
        self.c.set_document_acl(self.a,'d',DocumentACL(deny_users=['reader']))
        with self.assertRaises(PermissionDeniedError):self.c.retrieve(self.reader,'d')
        events=self.c.store.list_audit_events('org',limit=1000)
        actions={e.action for e in events}
        self.assertTrue({'ingest','retrieve','consume','attach','search','archive','restore','set_document_acl'}<=actions)
        self.assertTrue(any(e.actor_id=='reader' and e.decision_effect==DecisionEffect.DENY for e in events))
        self.assertTrue(self.c.verify_audit_chain(self.a).valid)

    def test_agent_purpose_generation(self):
        actor=replace(self.reader,policy_generation='42')
        agent=AgentIdentity('agent','org')
        self.c.retrieve(actor,'d',agent=agent,purpose=Purpose.GROUND_INTERNAL_LLM)
        event=self.c.store.list_audit_events('org',action='retrieve')[0]
        self.assertEqual((event.agent_id,event.purpose,event.policy_generation),('agent',Purpose.GROUND_INTERNAL_LLM,'42'))

    def test_tenant_and_self_scope(self):
        self.assertEqual(self.c.query_audit_events(Actor('owner','other',org_roles=('admin',))),[])
        with self.assertRaises(PermissionDeniedError):self.c.query_audit_events(self.reader,actor_id='owner')
        with self.assertRaises(PermissionDeniedError):self.c.verify_audit_chain(self.reader)

    def test_every_physical_column_tamper_detected(self):
        # New ledger per corruption; indexed fields AND encoded data verified.
        for column in COLUMNS+('data',):
            with self.subTest(column=column),closing(SQLiteStore()) as store:
                append(store,self.a,'one');append(store,self.a,'two');append(store,self.a,'three')
                if column=='seq_no':value=20
                elif column=='data':value='{}'
                else:value='tampered'
                store._execute('UPDATE audit_events SET '+column+'=? WHERE seq_no=2',(value,))
                report=verify_audit_chain(store,'org')
                self.assertFalse(report.valid);self.assertEqual(report.first_invalid_seq,2)

    def test_json_body_and_gap_detection_and_subrange(self):
        store=self.c.store;row=store._execute('SELECT seq_no,data FROM audit_events ORDER BY seq_no')[1]
        value=json.loads(row[1]);value['action']='forged'
        store._execute('UPDATE audit_events SET data=? WHERE seq_no=?',(json.dumps(value),row[0]))
        report=self.c.verify_audit_chain(self.a)
        self.assertFalse(report.valid);self.assertEqual(report.first_invalid_seq,row[0])
        store._execute('DELETE FROM audit_events WHERE seq_no=?',(row[0],))
        report=self.c.verify_audit_chain(self.a,from_seq=row[0]+1)
        self.assertFalse(report.valid);self.assertEqual(report.first_invalid_seq,row[0])

    def test_multi_connection_monotonic_and_atomic_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.db'
            with closing(SQLiteStore(path)) as one,closing(SQLiteStore(path)) as two:
                errors=[]
                def worker(store):
                    try:
                        for i in range(25):append(store,self.a,'worker')
                    except Exception as exc:errors.append(exc)
                threads=[threading.Thread(target=worker,args=(s,)) for s in (one,two)]
                for t in threads:t.start()
                for t in threads:t.join()
                self.assertEqual(errors,[])
                self.assertEqual([e.seq_no for e in one.list_audit_events('org')],list(range(1,51)))
                self.assertTrue(verify_audit_chain(one,'org').valid)
                with self.assertRaises(RuntimeError),one.transaction():
                    append(one,self.a,'rollback');raise RuntimeError('abort')
                self.assertEqual(len(one.list_audit_events('org')),50)

    def test_write_audit_uses_actual_context_generation_request_task(self):
        context=PolicyContext(policy_generation='current-9',request_id='request',task_id='task')
        self.c.archive(self.a,'d',policy_context=context)
        event=self.c.store.list_audit_events('org',action='archive')[0]
        self.assertEqual((event.policy_generation,event.request_id,event.task_id),('current-9','request','task'))
        self.assertEqual(self.c.policy_engine.rules,())
