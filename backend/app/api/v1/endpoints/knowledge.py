"""
/api/v1/knowledge — upload docs, trigger indexing, semantic search
"""
import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.lead import KnowledgeDoc
from app.schemas.lead import KnowledgeDocCreate, KnowledgeDocOut, KnowledgeSearchRequest, KnowledgeSearchResult
from app.core.redis import QueueName, enqueue, get_redis
import redis.asyncio as aioredis

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

DbDep    = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]


@router.post("", response_model=KnowledgeDocOut, status_code=status.HTTP_201_CREATED)
async def upload_doc(payload: KnowledgeDocCreate, db: DbDep, redis: RedisDep):
    content_hash = hashlib.sha256(payload.content.encode()).hexdigest()

    existing = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.content_hash == content_hash)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Document with identical content already exists")

    doc = KnowledgeDoc(
        title=payload.title,
        source_url=payload.source_url,
        content=payload.content,
        content_hash=content_hash,
    )
    db.add(doc)
    await db.flush()

    # Queue indexing job
    await enqueue(redis, QueueName.ONBOARDING_TASKS, {
        "type": "index_doc",
        "doc_id": str(doc.id),
    })

    return doc


@router.post("/upload-file", response_model=KnowledgeDocOut, status_code=status.HTTP_201_CREATED)
async def upload_file(db: DbDep, redis: RedisDep, file: UploadFile = File(...)):
    """Accept plain text or markdown file uploads."""
    if file.content_type not in ("text/plain", "text/markdown", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Only .txt and .md files supported")

    raw = await file.read()
    content = raw.decode("utf-8", errors="replace")
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    existing = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.content_hash == content_hash)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Document already indexed")

    doc = KnowledgeDoc(
        title=file.filename or "Uploaded document",
        content=content,
        content_hash=content_hash,
    )
    db.add(doc)
    await db.flush()

    await enqueue(redis, QueueName.ONBOARDING_TASKS, {
        "type": "index_doc",
        "doc_id": str(doc.id),
    })
    return doc


@router.get("", response_model=list[KnowledgeDocOut])
async def list_docs(db: DbDep):
    result = await db.execute(
        select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc())
    )
    return result.scalars().all()


@router.post("/search", response_model=list[KnowledgeSearchResult])
async def search_knowledge(payload: KnowledgeSearchRequest, db: DbDep):
    """Semantic search via Pinecone. Loaded in Phase 6 — returns stub here."""
    # Vector search is wired in the Onboarding Agent (Phase 6).
    # This endpoint imports and calls that service directly.
    try:
        from app.services.vector_store import search_knowledge_base
        results = await search_knowledge_base(payload.query, top_k=payload.top_k)
        return results
    except ImportError:
        raise HTTPException(status_code=503, detail="Vector store not yet initialised")
