"""Explicit v6 upgrade of a RECOGNIZED owned test sandbox only; no repair path.

Original seed receipt is retained byte-for-byte. v6 has a separately sealed schema
receipt. A v6-marked database without that receipt is refused, never auto-repaired.
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from seed_openbot_sandbox import marker,read_receipt,connect,pg_target,schema_hash,fingerprint,SandboxClient,seed
from knowledge_sdk.storage.migration_v6 import upgrade_v6,require_v6


def connect_wave2(root,mode,dsn=None):
    root=marker(root);read_receipt(root,mode)
    receipt=json.loads((root/'wave2-receipt.json').read_text())
    if set(receipt)!={'schema_version','mode','seed_receipt_sha256','physical_schema_sha256'} or receipt['schema_version']!=6 or receipt['mode']!=mode or receipt['seed_receipt_sha256']!=hashlib.sha256((root/'seed-receipt.json').read_bytes()).hexdigest():
        raise ValueError('Unrecognized Wave2 fixture')
    if mode=='sqlite':
        path=root/'knowledge.sqlite'
        with closing(sqlite3.connect(path.absolute().as_uri()+'?mode=ro',uri=True)) as raw:
            if raw.execute('PRAGMA user_version').fetchone()[0]!=6 or schema_hash(raw)!=receipt['physical_schema_sha256']:raise ValueError('Unrecognized Wave2 schema')
        from knowledge_sdk.storage.sqlite_store import SQLiteStore
        store=SQLiteStore(path)
    elif mode=='postgres':
        conn,_=pg_target(dsn)
        try:
            if conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]!=6 or schema_hash(conn,True)!=receipt['physical_schema_sha256']:raise ValueError('Unrecognized Wave2 schema')
        finally:conn.close()
        from knowledge_sdk.storage.postgres_store import PostgresStore
        store=PostgresStore(dsn,migrate=False)
    else:raise ValueError('Invalid mode')
    try:require_v6(store);return SandboxClient(store,require_principal=True)
    except BaseException:store.close();raise


def upgrade(root,mode='sqlite',dsn=None):
    root=marker(root)
    if (root/'wave2-receipt.json').exists():
        c=connect_wave2(root,mode,dsn)
        try:return {'status':'WAVE2_IDEMPOTENT_NO_DDL','schema_version':6}
        finally:c.store.close()
    if not (root/'seed-receipt.json').exists():seed(root,mode,dsn)
    c=connect(root,mode,dsn)
    try:
        expected=read_receipt(root,mode)
        if fingerprint(c)!=expected['business_sha256']:raise ValueError('Diverged fixture refused')
        with c.store.transaction():
            upgrade_v6(c.store,owned_nonproduction=True)
            if fingerprint(c)!=expected['business_sha256']:raise ValueError('Lossless upgrade check failed')
        receipt=dict(schema_version=6,mode=mode,seed_receipt_sha256=hashlib.sha256((root/'seed-receipt.json').read_bytes()).hexdigest(),physical_schema_sha256=schema_hash(c.store.db,mode=='postgres'))
        temporary=root/'wave2-receipt.tmp';temporary.write_text(json.dumps(receipt,sort_keys=True)+'\n');temporary.chmod(0o600);temporary.replace(root/'wave2-receipt.json')
        return {'status':'OWNED_FIXTURE_UPGRADED_V6','schema_version':6,'business_rows_unchanged':True,'original_seed_receipt_unchanged':True}
    finally:c.store.close()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--state-dir',default='/data');a=p.parse_args()
    try:print(json.dumps(upgrade(a.state_dir,os.environ.get('SANDBOX_MODE','sqlite'),os.environ.get('KNOWLEDGE_SDK_DSN'))))
    except Exception:raise SystemExit('Wave2 owned fixture upgrade refused; no repair attempted') from None
