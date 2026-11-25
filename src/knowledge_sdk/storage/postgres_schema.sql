
        CREATE TABLE IF NOT EXISTS knowledge_bases(kb_id TEXT PRIMARY KEY,org_id TEXT NOT NULL,data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS kb_members(org_id TEXT NOT NULL,kb_id TEXT NOT NULL REFERENCES knowledge_bases(kb_id),user_id TEXT NOT NULL,role TEXT NOT NULL,PRIMARY KEY(kb_id,user_id));
        CREATE TABLE IF NOT EXISTS documents(doc_id TEXT PRIMARY KEY,org_id TEXT NOT NULL,kb_id TEXT NOT NULL REFERENCES knowledge_bases(kb_id),data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS documents_org ON documents(org_id,kb_id);
        CREATE TABLE IF NOT EXISTS document_versions(org_id TEXT NOT NULL,doc_id TEXT NOT NULL REFERENCES documents(doc_id),version INTEGER NOT NULL,data TEXT NOT NULL,PRIMARY KEY(doc_id,version));
        CREATE TABLE IF NOT EXISTS document_acls(org_id TEXT NOT NULL,doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id),data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chunks(org_id TEXT NOT NULL,doc_id TEXT NOT NULL,version INTEGER NOT NULL,chunk_id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(doc_id,version,chunk_id),FOREIGN KEY(doc_id,version) REFERENCES document_versions(doc_id,version));
        CREATE TABLE IF NOT EXISTS pending_indexes(org_id TEXT NOT NULL,doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id));
        CREATE TABLE IF NOT EXISTS consumer_bindings(org_id TEXT NOT NULL,user_id TEXT NOT NULL,consumer_type TEXT NOT NULL,consumer_id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(org_id,user_id,consumer_type,consumer_id));

        ;ALTER TABLE documents ADD COLUMN IF NOT EXISTS space_type TEXT NOT NULL DEFAULT '';ALTER TABLE documents ADD COLUMN IF NOT EXISTS governance_tier TEXT NOT NULL DEFAULT 'l1_agile';ALTER TABLE documents ADD COLUMN IF NOT EXISTS access_level TEXT NOT NULL DEFAULT '';ALTER TABLE documents ADD COLUMN IF NOT EXISTS lifecycle_state TEXT NOT NULL DEFAULT 'published';ALTER TABLE documents ADD COLUMN IF NOT EXISTS archived INTEGER NOT NULL DEFAULT 0;ALTER TABLE documents ADD COLUMN IF NOT EXISTS revoked INTEGER NOT NULL DEFAULT 0;ALTER TABLE documents ADD COLUMN IF NOT EXISTS valid_from TEXT;ALTER TABLE documents ADD COLUMN IF NOT EXISTS valid_to TEXT;
        CREATE INDEX IF NOT EXISTS idx_docs_pushdown ON documents(org_id,kb_id,archived,revoked,lifecycle_state,access_level);
        CREATE TABLE IF NOT EXISTS evidence_anchors(anchor_id TEXT NOT NULL,org_id TEXT NOT NULL,doc_id TEXT NOT NULL,version INTEGER NOT NULL,selector_kind TEXT NOT NULL,reanchor_status TEXT NOT NULL DEFAULT 'anchored',data TEXT NOT NULL,PRIMARY KEY(org_id,doc_id,version,anchor_id),FOREIGN KEY(doc_id,version) REFERENCES document_versions(doc_id,version));
        CREATE INDEX IF NOT EXISTS idx_anchors_lookup ON evidence_anchors(org_id,anchor_id);
        CREATE TABLE IF NOT EXISTS policy_rules(rule_id TEXT PRIMARY KEY,org_id TEXT NOT NULL,scope_kb_id TEXT NOT NULL DEFAULT '',scope_doc_id TEXT NOT NULL DEFAULT '',priority INTEGER NOT NULL DEFAULT 100,effect TEXT NOT NULL,data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_policy_org_scope ON policy_rules(org_id,scope_kb_id,scope_doc_id,priority);
        CREATE TABLE IF NOT EXISTS evidence_issues(issue_id TEXT PRIMARY KEY,org_id TEXT NOT NULL,doc_id TEXT NOT NULL,version INTEGER NOT NULL,anchor_id TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL,data TEXT NOT NULL);
    ;
CREATE TABLE IF NOT EXISTS outbox_events (
  event_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  available_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  dispatched_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending
  ON outbox_events(status, available_at, created_at);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  seq_no INTEGER NOT NULL,
  prev_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  agent_id TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL,
  purpose TEXT NOT NULL,
  resource_uri TEXT NOT NULL DEFAULT '',
  doc_id TEXT NOT NULL DEFAULT '',
  decision_effect TEXT NOT NULL,
  reason_code TEXT NOT NULL,
  policy_generation TEXT NOT NULL DEFAULT '0',
  redaction_profile TEXT NOT NULL DEFAULT '',
  data TEXT NOT NULL,
  UNIQUE(org_id, seq_no)
);
CREATE INDEX IF NOT EXISTS idx_audit_org_time
  ON audit_events(org_id, occurred_at, seq_no);
CREATE TABLE IF NOT EXISTS usage_events (
  usage_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  anchor_id TEXT NOT NULL DEFAULT '',
  consumer_type TEXT NOT NULL,
  consumer_id TEXT NOT NULL,
  task_id TEXT NOT NULL DEFAULT '',
  actor_id TEXT NOT NULL,
  agent_id TEXT NOT NULL DEFAULT '',
  purpose TEXT NOT NULL,
  receipt_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_doc
  ON usage_events(org_id, doc_id, version, anchor_id);
CREATE TABLE IF NOT EXISTS impact_alerts (
  alert_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  source_event_id TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  source_version INTEGER NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  impact_reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  data TEXT NOT NULL,
  UNIQUE(org_id, source_event_id, target_type, target_id)
);
CREATE INDEX IF NOT EXISTS idx_impact_org_status
  ON impact_alerts(org_id, status, created_at);
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
  subscription_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  event_types TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS webhook_deliveries (
  delivery_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  subscription_id TEXT NOT NULL,
  outbox_event_id TEXT NOT NULL,
  status TEXT NOT NULL,
  http_status INTEGER NOT NULL DEFAULT 0,
  attempted_at TEXT NOT NULL,
  data TEXT NOT NULL,
  UNIQUE(subscription_id, outbox_event_id)
);
CREATE TABLE IF NOT EXISTS review_decisions (
  decision_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  stage TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_packs (
  pack_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'sealed',
  pack_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connector_sync_state (
  connector_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  cursor TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  data TEXT NOT NULL,
  PRIMARY KEY(org_id, connector_id)
);
    ;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS search_vector TSVECTOR;
CREATE INDEX IF NOT EXISTS idx_chunks_search ON chunks USING GIN(search_vector);
CREATE TABLE IF NOT EXISTS resource_directory(kind TEXT NOT NULL,id TEXT NOT NULL,tenant TEXT NOT NULL,PRIMARY KEY(kind,id));
CREATE TABLE IF NOT EXISTS replay_nonces(org_id TEXT NOT NULL,nonce TEXT NOT NULL,expires_at DOUBLE PRECISION NOT NULL,PRIMARY KEY(org_id,nonce));
CREATE INDEX IF NOT EXISTS idx_replay_expiry ON replay_nonces(expires_at);

CREATE TABLE IF NOT EXISTS identity_principals (
 org_id TEXT NOT NULL,user_id TEXT NOT NULL,external_id TEXT NOT NULL DEFAULT '',username TEXT NOT NULL DEFAULT '',
 active INTEGER NOT NULL DEFAULT 1,policy_generation INTEGER NOT NULL DEFAULT 1,
 roles_json TEXT NOT NULL DEFAULT '[]',department_ids_json TEXT NOT NULL DEFAULT '[]',org_roles_json TEXT NOT NULL DEFAULT '[]',
 clearance_level TEXT NOT NULL DEFAULT '',clearance_tags_json TEXT NOT NULL DEFAULT '[]',updated_at TEXT NOT NULL,data TEXT NOT NULL,
 PRIMARY KEY(org_id,user_id));
CREATE INDEX IF NOT EXISTS idx_principals_org_ext ON identity_principals(org_id,external_id);
CREATE TABLE IF NOT EXISTS scim_groups(org_id TEXT NOT NULL,group_id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(org_id,group_id));
CREATE TABLE IF NOT EXISTS scim_group_members(org_id TEXT NOT NULL,group_id TEXT NOT NULL,user_id TEXT NOT NULL,PRIMARY KEY(org_id,group_id,user_id));
