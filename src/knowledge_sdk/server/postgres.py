"""Explicit optional service wiring; deterministic hashing is not semantic AI."""
from ..client.local import LocalKnowledgeClient
from ..storage.postgres_store import PostgresStore
from .replay_pg import PostgresReplayStore


def postgres_client(dsn,*,enable_rls=True,pgvector_dims=None):
    store=PostgresStore(dsn,enable_rls=enable_rls)
    try:
        kwargs={}
        if pgvector_dims is not None:
            from ..retrieval.adapters.pgvector_index import PgVectorIndex
            from ..retrieval.adapters.hash_embedder import HashEmbedder
            embedder=HashEmbedder();embedder.dimensions=pgvector_dims
            kwargs={'vector_index':PgVectorIndex(store=store,dimensions=pgvector_dims,enable_rls=enable_rls),'embedder':embedder}
        return LocalKnowledgeClient(store,**kwargs)
    except BaseException:store.close();raise
