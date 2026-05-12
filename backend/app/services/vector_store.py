"""
Vector store — Pinecone-backed RAG for the Onboarding Agent.
Handles:
  - Document chunking with overlap
  - Embedding via OpenAI text-embedding-3-small
  - Upsert to Pinecone with metadata
  - Semantic search returning ranked chunks
  - Automatic re-indexing when docs change
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

from openai import AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.schemas.lead import KnowledgeSearchResult

logger = logging.getLogger(__name__)

# ── Chunking parameters ───────────────────────────────────────────────────────
CHUNK_SIZE    = 500   # characters
CHUNK_OVERLAP = 80


# ── Clients ───────────────────────────────────────────────────────────────────

_openai: AsyncOpenAI | None = None
_pinecone_index = None


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai


def _get_index():
    global _pinecone_index
    if _pinecone_index is None:
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        existing = [i.name for i in pc.list_indexes()]
        if settings.PINECONE_INDEX not in existing:
            pc.create_index(
                name=settings.PINECONE_INDEX,
                dimension=1536,   # text-embedding-3-small output dim
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            logger.info(f"Created Pinecone index: {settings.PINECONE_INDEX}")
        _pinecone_index = pc.Index(settings.PINECONE_INDEX)
    return _pinecone_index


# ── Text chunker ──────────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks. Tries to break on sentence boundaries."""
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))

        # Try to find a sentence boundary near the end
        if end < len(text):
            for sep in (". ", ".\n", "\n\n", "\n", " "):
                boundary = text.rfind(sep, start + size // 2, end)
                if boundary != -1:
                    end = boundary + len(sep)
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c.strip()]


# ── Embedding ─────────────────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
)
async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed texts. OpenAI allows up to 2048 inputs per call."""
    client = _get_openai()
    # Process in batches of 100
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), 100):
        batch = texts[i:i + 100]
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=batch,
        )
        all_embeddings.extend([item.embedding for item in response.data])
    return all_embeddings


# ── Index a document ─────────────────────────────────────────────────────────

async def index_document(
    doc_id: str,
    title: str,
    content: str,
    source_url: str | None = None,
) -> list[str]:
    """
    Chunk, embed, and upsert a document to Pinecone.
    Returns list of vector IDs created.
    """
    chunks = chunk_text(content)
    if not chunks:
        return []

    embeddings = await embed_texts(chunks)
    index = _get_index()

    vectors = []
    vector_ids = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vid = f"{doc_id}_{i}"
        vector_ids.append(vid)
        vectors.append({
            "id": vid,
            "values": embedding,
            "metadata": {
                "doc_id":     doc_id,
                "title":      title,
                "source_url": source_url or "",
                "chunk_index": i,
                "chunk_text": chunk[:1000],   # Pinecone metadata limit
            },
        })

    # Upsert in batches of 100
    for i in range(0, len(vectors), 100):
        index.upsert(vectors=vectors[i:i + 100])

    logger.info(f"Indexed doc {doc_id!r}: {len(chunks)} chunks → Pinecone")
    return vector_ids


async def delete_document(vector_ids: list[str]) -> None:
    """Remove document vectors from Pinecone."""
    if not vector_ids:
        return
    index = _get_index()
    index.delete(ids=vector_ids)


# ── Search ────────────────────────────────────────────────────────────────────

async def search_knowledge_base(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.30,
) -> list[KnowledgeSearchResult]:
    """
    Embed query, search Pinecone, return ranked chunks above threshold.
    """
    embeddings = await embed_texts([query])
    query_vec  = embeddings[0]

    index   = _get_index()
    results = index.query(
        vector=query_vec,
        top_k=top_k,
        include_metadata=True,
    )

    output: list[KnowledgeSearchResult] = []
    for match in results.matches:
        if match.score < score_threshold:
            continue
        meta = match.metadata or {}
        output.append(KnowledgeSearchResult(
            chunk=meta.get("chunk_text", ""),
            source_title=meta.get("title", ""),
            source_url=meta.get("source_url") or None,
            score=round(float(match.score), 4),
        ))

    return output


# ── DB-backed indexing job (called by knowledge endpoint worker) ──────────────

async def run_indexing_job(doc_id: str) -> None:
    """
    Load KnowledgeDoc from DB, index it, update is_indexed + pinecone_ids.
    Designed to be called from the ONBOARDING_TASKS queue consumer.
    """
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.lead import KnowledgeDoc
    from datetime import datetime, timezone

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            logger.warning(f"KnowledgeDoc {doc_id} not found for indexing")
            return

        # Delete old vectors if re-indexing
        if doc.pinecone_ids:
            await delete_document(doc.pinecone_ids)

        vector_ids = await index_document(
            doc_id=str(doc.id),
            title=doc.title,
            content=doc.content,
            source_url=doc.source_url,
        )

        doc.is_indexed   = True
        doc.pinecone_ids = vector_ids
        doc.indexed_at   = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"Doc indexed: {doc.title!r} ({len(vector_ids)} vectors)")
