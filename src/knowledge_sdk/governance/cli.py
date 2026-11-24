"""Trusted local operation CLI. Identity comes from host environment, not params."""
from __future__ import annotations
import argparse
import json
import os
import sys
from ..contracts.models import Actor, encode, decode
from ..client.local import LocalKnowledgeClient
from ..storage.sqlite_store import SQLiteStore
from ..exceptions import KnowledgeSDKError

OPERATIONS=('submit_for_review','approve_release','reject_release','publish_release','record_dissent','get_release_manifest','resolve_evidence_issue','create_evidence_pack','get_evidence_pack','list_evidence_packs','verify_evidence_pack','export_evidence_pack')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=OPERATIONS)
    parser.add_argument('--db',default=':memory:')
    parser.add_argument('--dsn',default=os.environ.get('KNOWLEDGE_SDK_DSN'))
    parser.add_argument('--params',default='{}',help='JSON method arguments, never identity')
    args=parser.parse_args(argv)
    client=None
    try:
        actor=Actor(**json.loads(os.environ.get('KNOWLEDGE_SDK_ACTOR_JSON','{}')))
        params=decode(json.loads(args.params))
        if not isinstance(params,dict) or set(params)&{'actor','self','agent','policy_context'}:raise ValueError()
        if args.dsn:
            from ..server.postgres import postgres_client
            client=postgres_client(args.dsn)
        else:client=LocalKnowledgeClient(SQLiteStore(args.db))
        print(json.dumps(encode(getattr(client,args.operation)(actor,**params)),sort_keys=True))
        return 0
    except (KnowledgeSDKError,ValueError,TypeError,KeyError):
        print('Operation rejected (details withheld)',file=sys.stderr)
        return 2
    finally:
        if client is not None:client.store.close()

if __name__=='__main__':raise SystemExit(main())
