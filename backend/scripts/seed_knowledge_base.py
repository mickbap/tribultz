"""
Seed Redis long-term memory with knowledge base chunks.

Sources:
- lei214_anexos.json  → 147 NCM codes + 15 annexes (LC 214/2024)
- classtrib.json      → 74 cClassTrib codes (NT 2025.002-RTC)
- kb_reforma_tributaria.json → 10 narrative chunks (material Roberta CRC)

Scoped under /global/knowledge_base/ (tenant-agnostic, shared by all crews).
TTL: 0 = never expires.

Usage (inside the api container on prod VM):
    PYTHONPATH=/app python /tmp/seed_knowledge_base.py
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any

import httpx
import redis

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
REDIS_URL = os.environ["REDIS_URL"]
DATA_DIR = os.environ.get("KB_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "app", "data"))

# Match the namespace used by RedisMemoryStorage at runtime
REDIS_NAMESPACE = "tribultz:crewai:memory"


def embed(texts: list[str]) -> list[list[float]]:
    """Get embeddings via OpenRouter in batches of 20."""
    all_embeddings: list[list[float]] = []
    batch_size = 20
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = httpx.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "openai/text-embedding-3-small", "input": batch},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        all_embeddings.extend([item["embedding"] for item in data])
        print(f"  Embedded batch {i // batch_size + 1} ({len(batch)} texts)")
    return all_embeddings


def store_record(
    r: redis.Redis,
    scope: str,
    content: str,
    metadata: dict[str, Any],
    embedding: list[float],
    source: str = "knowledge_base_seed",
) -> str:
    """Store a record in RedisMemoryStorage-compatible format.
    
    Uses the same namespace and format as RedisMemoryStorage for runtime compatibility.
    """
    record_id = str(uuid.uuid4())
    now = datetime.utcnow()
    now_iso = now.isoformat()
    
    # MemoryRecord-compatible format (crewai.memory.types.MemoryRecord)
    record = {
        "id": record_id,
        "content": content,
        "scope": scope,
        "categories": [metadata.get("category", "knowledge_base")],
        "metadata": metadata,
        "importance": metadata.get("importance", 0.7),
        "created_at": now_iso,
        "last_accessed": now_iso,
        "embedding": embedding,
        "source": source,
        "private": False,
    }
    
    # Use the same key format as RedisMemoryStorage
    key = f"{REDIS_NAMESPACE}:record:{record_id}"
    r.set(key, json.dumps(record, ensure_ascii=False))
    return record_id


def clean_old_format(r: redis.Redis) -> int:
    """Remove old format keys to avoid duplicates and namespace confusion."""
    old_keys = list(r.scan_iter(match="crew_memory:*"))
    if old_keys:
        r.delete(*old_keys)
    return len(old_keys)


def main() -> None:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    print(f"Redis ping: {r.ping()}")
    
    # Clean old format keys
    cleaned = clean_old_format(r)
    print(f"Cleaned {cleaned} old-format keys")
    print(f"Keys before seeding: {r.dbsize()}")

    # ── 1. CLASSTRIB ──────────────────────────────────────────
    print("\n=== CLASSTRIB (74 cClassTrib codes) ===")
    classtrib = json.load(open(os.path.join(DATA_DIR, "classtrib.json"), encoding="utf-8"))

    chunks_classtrib = []
    for code, v in classtrib["by_code"].items():
        cst = v.get("cst", "")
        cst_desc = v.get("cst_description", "")
        desc = v.get("description", "")
        red_ibs = v.get("reduction_ibs_pct", 0)
        red_cbs = v.get("reduction_cbs_pct", 0)
        tipo = v.get("tipo_aliquota", "")
        dfes = ", ".join(v.get("dfe_allowed", []))
        content = (
            f"cClassTrib {code}: {desc}. "
            f"CST {cst} ({cst_desc}). "
            f"Reducao IBS: {red_ibs}%, Reducao CBS: {red_cbs}%. "
            f"Tipo aliquota: {tipo}. "
            f"Documentos fiscais: {dfes}."
        )
        chunks_classtrib.append({
            "content": content,
            "metadata": {
                "source": "CLASSTRIB NT2025.002-RTC",
                "type": "classtrib_code",
                "cClassTrib": code,
                "cst": cst,
                "reduction_ibs_pct": red_ibs,
                "reduction_cbs_pct": red_cbs,
                "importance": 0.9,
                "category": "fiscal_classification",
            },
        })

    embeddings = embed([c["content"] for c in chunks_classtrib])
    scope = "/global/knowledge_base/classtrib"
    for chunk, emb in zip(chunks_classtrib, embeddings):
        store_record(r, scope, chunk["content"], chunk["metadata"], emb)
    print(f"Stored {len(chunks_classtrib)} cClassTrib records")

    # ── 2. LEI 214 ANNEXES ────────────────────────────────────
    print("\n=== LEI 214 ANNEXES + NCM chapters ===")
    lei214 = json.load(open(os.path.join(DATA_DIR, "lei214_anexos.json"), encoding="utf-8"))

    chunks_lei214: list[dict] = []

    # One chunk per annex
    for annex_name, annex_data in lei214["by_annex"].items():
        red_pct = annex_data.get("reduction_pct", 0)
        regime = annex_data.get("regime", "")
        items = annex_data.get("items", [])
        items_text = "; ".join(
            f"{it.get('item_number', '')}) {it.get('description', '')[:80]}"
            for it in items[:20]
        )
        if len(items) > 20:
            items_text += f"... e mais {len(items) - 20} itens"
        content = (
            f"Anexo LC 214: {annex_name}. "
            f"Regime: {regime}. Reducao: {red_pct}% de IBS e CBS. "
            f"{len(items)} itens. Exemplos: {items_text}."
        )
        chunks_lei214.append({
            "content": content,
            "metadata": {
                "source": "LC 214/2024",
                "type": "lei214_annex",
                "annex": annex_name,
                "reduction_pct": red_pct,
                "regime": regime,
                "item_count": len(items),
                "importance": 0.85,
                "category": "fiscal_classification",
            },
        })

    # One chunk per NCM chapter
    ncm_by_chapter: dict[str, list] = {}
    for ncm, ncm_data in lei214["by_ncm"].items():
        chapter = ncm[:2]
        ncm_by_chapter.setdefault(chapter, []).append((ncm, ncm_data))

    for chapter, ncm_list in ncm_by_chapter.items():
        ncm_text = "; ".join(
            f"NCM {ncm}: {data['description'][:60]} (reducao {data['reduction_pct']}%)"
            for ncm, data in ncm_list[:10]
        )
        content = (
            f"Capitulo NCM {chapter} - LC 214/2024. "
            f"{len(ncm_list)} codigos com beneficio fiscal. {ncm_text}."
        )
        chunks_lei214.append({
            "content": content,
            "metadata": {
                "source": "LC 214/2024",
                "type": "lei214_ncm_chapter",
                "ncm_chapter": chapter,
                "ncm_count": len(ncm_list),
                "importance": 0.8,
                "category": "fiscal_classification",
            },
        })

    embeddings = embed([c["content"] for c in chunks_lei214])
    scope = "/global/knowledge_base/lei214"
    for chunk, emb in zip(chunks_lei214, embeddings):
        store_record(r, scope, chunk["content"], chunk["metadata"], emb)
    print(f"Stored {len(chunks_lei214)} LEI 214 records")

    # ── 3. KB REFORMA TRIBUTARIA ──────────────────────────────
    print("\n=== KB REFORMA TRIBUTARIA (10 chunks) ===")
    kb = json.load(open(os.path.join(DATA_DIR, "kb_reforma_tributaria.json"), encoding="utf-8"))

    chunks_kb = []
    for chunk in kb["chunks"]:
        content = f"{chunk['title']}: {chunk['content']}"
        chunks_kb.append({
            "content": content,
            "metadata": {
                "source": chunk.get("source", "Material educacional Roberta CRC"),
                "type": "kb_chunk",
                "chunk_id": chunk["id"],
                "topic": chunk.get("topic", ""),
                "importance": 0.75,
                "category": "knowledge_base",
            },
        })

    embeddings = embed([c["content"] for c in chunks_kb])
    scope = "/global/knowledge_base/reforma_tributaria"
    for chunk, emb in zip(chunks_kb, embeddings):
        store_record(r, scope, chunk["content"], chunk["metadata"], emb)
    print(f"Stored {len(chunks_kb)} KB records")

    # ── Summary ───────────────────────────────────────────────
    total = len(chunks_classtrib) + len(chunks_lei214) + len(chunks_kb)
    print(f"\nKeys after seeding: {r.dbsize()}")
    print(f"Total records seeded: {total}")
    print("Knowledge base ready for semantic search.")


if __name__ == "__main__":
    main()
