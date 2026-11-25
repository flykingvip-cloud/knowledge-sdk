# Bounded HTTP/MCP container (not a deployment)

The image disables UI/demo/insecure authentication and access-log query strings.
Runtime UID/GID is 65532; mount a writable `/data` owned by that UID and a read-only
secret at `/run/secrets/knowledge_auth_secret` (at least 32 characters). Do not
put credentials in build arguments, images, command arguments, or source control.
HTTP and the four MCP tools share port 8088. Set KNOWLEDGE_SDK_DSN using a runtime
secret-aware orchestrator for PostgreSQL; otherwise SQLite data/replay DBs use the
volume. This does not connect any enterprise system or authorize a deployment.

`docker build --tag knowledge-sdk:align-wave1 .` builds bounded, optional HTTP/MCP
and PostgreSQL dependencies only. Versions are pinned in container-requirements.txt;
provide a verified image digest via PYTHON_IMAGE for reproducible release builds.
This source artifact has NOT been built/run if the acceptance receipt says
BUILD_NOT_RUN (no Docker/Podman/BuildKit/daemon available); source checks are not
Docker engine validation. No publication or production command is provided.

`/v1/health` retains its old contract. `/v1/ready` is deliberately public, minimal
status-only, and runs SELECT 1 plus an exact schema-v5 check; failures are 503 with
no exception/DSN text. `/v1/metrics` requires signed current identity with the
operator-only `metrics_admin` org role and non-broadened agent context. It returns
five fixed process-wide request/status counters only, no dynamic labels or data.
It does not expose per-tenant rates. All new operational routes are no-store;
apply gateway rate limiting as appropriate. Never grant metrics_admin from a
client-controlled header. Kubernetes/Helm/console/production rollout are out of scope.
