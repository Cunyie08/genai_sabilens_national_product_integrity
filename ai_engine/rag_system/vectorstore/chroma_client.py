"""
vectorstore/chroma_client.py
-----------------------------
Manages the ChromaDB persistent vector store.

SINGLE RESPONSIBILITY
  Read and write ProductChunk documents to ChromaDB.
  No business logic, no scoring, no text construction here.

WHY PERSISTENT CLIENT?
  PersistentClient writes the collection to disk at CHROMA_PERSIST_DIR.
  After ingestion runs once, the API server starts instantly without
  re-embedding.  Embedding 15 products takes seconds, but this design
  scales cleanly when the database grows to thousands of products.

WHY UPSERT INSTEAD OF ADD?
  NAFDAC updates its database periodically.  Re-running ingestion after
  an update should:
    • Update records whose details changed (new expiry date, name correction).
    • Insert genuinely new products.
    • Leave unchanged records untouched.
  Using add() would raise a DuplicateIDError on re-run.  upsert() is safe
  to call at any time with any number of products.

DISTANCE METRIC: cosine
  SentenceTransformer vectors are L2-normalised before storage (see embedder.py).
  With L2-normalised vectors, cosine distance = 2 × (1 − cosine_similarity).
  ChromaDB returns distance (lower = more similar); the retriever converts to
  a 0–1 similarity score for downstream scoring.
"""

import os
import sqlite3

import chromadb
from ai_engine.rag_system.config.settings import settings
from ai_engine.rag_system.ingestion.schema import ProductChunk


def _apply_schema_migration(persist_dir: str) -> None:
    """
    Add columns that ChromaDB 0.4.x expects but older database files lack.

    The `topic` column was introduced in ChromaDB 0.4.x for the SQLite-backed
    embeddings queue.  Databases created with ChromaDB <0.4.0 don't have it,
    so opening them with 0.4.24 raises "no such column: collections.topic".

    This runs before PersistentClient opens the file, so ChromaDB sees a
    compatible schema on its first read.  It is a no-op when the database is
    fresh or already migrated.
    """
    db_path = os.path.join(persist_dir, "chroma.sqlite3")
    if not os.path.exists(db_path):
        return  # New database — ChromaDB will create it with the correct schema.
    try:
        with sqlite3.connect(db_path) as conn:
            existing_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(collections)")
            }
            if "topic" not in existing_cols:
                conn.execute("ALTER TABLE collections ADD COLUMN topic TEXT")
                conn.commit()
                print(
                    "[ChromaStore] Schema migration applied: "
                    "added 'topic' column to collections table."
                )
    except Exception as exc:
        # Non-fatal: log and let PersistentClient raise the real error if needed.
        print(f"[ChromaStore] Schema migration warning (non-fatal): {exc}")


class ChromaStore:
    """
    Interface to the ChromaDB persistent collection of NAFDAC product records.

    Provides three operations:
      ingest()  — upsert chunks with their pre-computed embedding vectors
      query()   — vector similarity search with optional metadata filtering
      count()   — number of documents currently stored

    Usage:
        store = ChromaStore()
        store.ingest(chunks, embeddings)
        results = store.query(query_vec, n_results=5,
                              where={"nafdac_no_clean": "A8-4114"})
    """

    def __init__(self):
        # Fix any schema mismatch before PersistentClient opens the SQLite file.
        _apply_schema_migration(settings.CHROMA_PERSIST_DIR)

        # PersistentClient persists all data to disk.
        # Safe to instantiate multiple times — returns the same client for the
        # same path (ChromaDB manages the singleton internally).
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

        # get_or_create_collection is idempotent — safe on every startup.
        # hnsw:space=cosine configures the HNSW index for cosine distance.
        self.collection = self.client.get_or_create_collection(
            name     = settings.CHROMA_COLLECTION_NAME,
            metadata = {"hnsw:space": "cosine"},
        )

        print(
            f"[ChromaStore] Collection '{settings.CHROMA_COLLECTION_NAME}' ready.  "
            f"Documents stored: {self.collection.count()}"
        )

    # ── Write ─────────────────────────────────────────────────────────────────

    def ingest(self, chunks: list[ProductChunk], embeddings: list[list[float]]) -> None:
        """
        Batch-upsert all chunks into the collection.

        upsert() semantics:
          • Chunk ID already in collection → update document, metadata, embedding.
          • Chunk ID not in collection    → insert new document.
          • Safe to call multiple times with the same data (idempotent).

        Args:
            chunks:     List of ProductChunk objects from chunk_builder.build_chunks().
            embeddings: Parallel list of float vectors from embedder.embed().
                        Must have the same length and order as chunks.

        Raises:
            ValueError: If chunks and embeddings lengths do not match.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"[ChromaStore] Length mismatch: {len(chunks)} chunks vs "
                f"{len(embeddings)} embeddings.  They must correspond exactly."
            )

        print(f"[ChromaStore] Upserting {len(chunks)} chunk(s)…")

        self.collection.upsert(
            ids        = [c.chunk_id for c in chunks],
            documents  = [c.text     for c in chunks],
            metadatas  = [c.metadata for c in chunks],
            embeddings = embeddings,
        )

        print(f"[ChromaStore] Upsert complete.  "
              f"Collection now contains {self.collection.count()} document(s).")

    # ── Read ──────────────────────────────────────────────────────────────────

    def query(
        self,
        query_embedding: list[float],
        n_results:       int  = 5,
        where:           dict = None,
    ) -> dict:
        """
        Search the collection for documents nearest to the query vector.

        The optional 'where' filter is applied as a metadata pre-filter BEFORE
        the vector search.  For exact NAFDAC number lookups this means ChromaDB
        scans only the matching record(s) — effectively O(1).

        Args:
            query_embedding: L2-normalised float vector from Embedder.embed_single().
            n_results:       Maximum documents to return (before threshold filtering).
            where:           Optional ChromaDB metadata filter dict.
                             Single field  : {"nafdac_no_clean": "A8-4114"}
                             AND condition : {"$and": [{"subcategory": "Cosmetics"},
                                                       ...]}

        Returns:
            ChromaDB raw results dict with keys:
              ids        list[list[str]]   — chunk IDs
              documents  list[list[str]]   — chunk text strings
              metadatas  list[list[dict]]  — metadata dicts
              distances  list[list[float]] — cosine distances (0 = identical)
            All are nested lists; index [0] gives the results for this single query.
        """
        kwargs: dict = {
            "query_embeddings" : [query_embedding],
            "n_results"        : n_results,
            "include"          : ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        return self.collection.query(**kwargs)

    # ── Utility ───────────────────────────────────────────────────────────────

    def count(self) -> int:
        """Return the total number of documents currently in the collection."""
        return self.collection.count()

    def reset_collection(self) -> None:
        """
        Delete and recreate the collection.  USE WITH CAUTION.

        Only needed when the schema changes and existing embeddings must be
        discarded entirely.  In normal operation, upsert() handles updates
        without requiring a reset.
        """
        self.client.delete_collection(settings.CHROMA_COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name     = settings.CHROMA_COLLECTION_NAME,
            metadata = {"hnsw:space": "cosine"},
        )
        print(f"[ChromaStore] Collection '{settings.CHROMA_COLLECTION_NAME}' reset.")