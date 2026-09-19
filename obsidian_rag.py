from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import chromadb
import frontmatter
from sentence_transformers import SentenceTransformer


COLLECTION_NAME = "obsidian_vault"


def _vault_path() -> Path:
    raw_path = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if not raw_path:
        raise ValueError("OBSIDIAN_VAULT_PATH is not configured")
    return Path(raw_path).expanduser().resolve()


def _chroma_db_path() -> Path:
    return Path(os.getenv("OBSIDIAN_CHROMA_DB_PATH", "./chroma_db")).expanduser().resolve()


@lru_cache(maxsize=1)
def _embedder() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2")


def _collection():
    db_path = _chroma_db_path()
    db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_path))
    return client.get_or_create_collection(COLLECTION_NAME)


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    words = text.split()
    if not words:
        return []

    overlap = min(50, max(0, chunk_size - 1))
    step = max(1, chunk_size - overlap)
    chunks: list[str] = []
    for start_index in range(0, len(words), step):
        chunk = " ".join(words[start_index : start_index + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def index_vault() -> None:
    vault_path = _vault_path()
    if not vault_path.exists():
        raise FileNotFoundError(f"Obsidian vault not found: {vault_path}")

    collection = _collection()
    embedder = _embedder()
    md_files = sorted(vault_path.rglob("*.md"))

    for file_path in md_files:
        upsert_note_index(file_path, vault_path=vault_path, collection=collection, embedder=embedder)


def upsert_note_index(
    file_path: Path,
    *,
    vault_path: Path | None = None,
    collection=None,
    embedder: SentenceTransformer | None = None,
) -> None:
    active_vault_path = vault_path or _vault_path()
    active_collection = collection or _collection()
    active_embedder = embedder or _embedder()

    post = frontmatter.load(file_path)
    content = post.content or ""
    if not content.strip():
        return

    relative_path = str(file_path.relative_to(active_vault_path))
    title = str(post.get("title") or file_path.stem)
    chunks = chunk_text(content, chunk_size=500)

    for chunk_index, chunk in enumerate(chunks):
        document_id = f"{relative_path}::chunk_{chunk_index}"
        embedding = active_embedder.encode(chunk).tolist()
        active_collection.upsert(
            ids=[document_id],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[{"filepath": relative_path, "title": title}],
        )


def search_vault(query: str, n_results: int = 5) -> list[dict]:
    collection = _collection()
    if collection.count() == 0:
        return []

    embedder = _embedder()
    query_embedding = embedder.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    output: list[dict] = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else 1.0
        output.append(
            {
                "content": document,
                "filepath": metadata.get("filepath", ""),
                "title": metadata.get("title", ""),
                "score": 1 - distance,
            }
        )
    return output
