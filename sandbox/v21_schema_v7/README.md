# sandbox/v21_schema_v7

Isolated Wave-V21-6 Schema v7 sandbox. Pure Python standard library
(`sqlite3` allowed). No third-party dependencies, no `psycopg`, and no
live production or shared PostgreSQL connection.

This package is authorized only on the isolated branch
`feat/v21-wave6-schema-v7-sandbox-and-t01-t27` under AUTH-V21-06-SANDBOX.
It must never upgrade an existing Schema v6 store and must never edit
`src/knowledge_sdk/storage/`.

- SQLite: executable migration and idempotent rollback on a newly created
  in-memory or throwaway temporary database only.
- PostgreSQL: DDL / FORCE RLS *semantic* validation of candidate statements.
  A live PostgreSQL connection is not required and is not used.
- Scope label: `SANDBOX_DUAL_ENGINE_CANDIDATE`.
- `formal_t01_t27_accepted` is always `false`. Passing these tests is not
  formal T-01–T-27 acceptance.

Run:

```
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s sandbox/v21_schema_v7 -p '*cases.py'
```
