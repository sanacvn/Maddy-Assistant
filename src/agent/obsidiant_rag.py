
import os
import glob
import frontmatter
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path

VAULT_PATH = "/path/to/obsidian/vault"  # Sesuaikan
DB_PATH = "./chroma_db"

embedder = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection("obsidian_vault")

def index_vault():
    """Scan semua .md dan masukkan ke vector DB."""
    md_files = glob.glob(f"{VAULT_PATH}/**/*.md", recursive=True)
    
    for filepath in md_files:
        post = frontmatter.load(filepath)
        content = post.content
        rel_path = str(Path(filepath).relative_to(VAULT_PATH))
        
        # Split per chunk agar tidak terlalu panjang
        chunks = chunk_text(content, chunk_size=500)
        
        for i, chunk in enumerate(chunks):
            doc_id = f"{rel_path}::chunk_{i}"
            embedding = embedder.encode(chunk).tolist()
            
            collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{"filepath": rel_path, "title": post.get("title", rel_path)}]
            )
    
    print(f"Indexed {len(md_files)} files.")

def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Split teks jadi chunk-chunk kecil dengan overlap."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - 50):  # 50 kata overlap
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def search_vault(query: str, n_results: int = 5) -> list[dict]:
    """Cari catatan yang relevan dengan query."""
    query_embedding = embedder.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    
    output = []
    for i, doc in enumerate(results["documents"][0]):
        output.append({
            "content": doc,
            "filepath": results["metadatas"][0][i]["filepath"],
            "title": results["metadatas"][0][i]["title"],
            "score": 1 - results["distances"][0][i]  # cosine similarity
        })
    return output