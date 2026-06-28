import io
import logging
import uuid
from typing import List

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_embedding_model: SentenceTransformer | None = None
_chroma_client: chromadb.ClientAPI | None = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading sentence-transformers model (first-time download may take a moment)...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def _get_chroma_client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path="./chroma_db")
    return _chroma_client


def _extract_text(file_bytes: bytes, filename: str) -> str:
    name_lower = filename.lower()
    if name_lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip())
    # Plain-text fallback (.txt, .md, etc.)
    return file_bytes.decode("utf-8", errors="replace")


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk:
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def ingest_document(file_bytes: bytes, filename: str, collection_name: str) -> int:
    """Extract, chunk, embed a document and store chunks in ChromaDB. Returns chunk count."""
    text = _extract_text(file_bytes, filename)
    if not text.strip():
        logger.warning("No text extracted from '%s' — may be a scanned image PDF", filename)
        return 0

    chunks = _chunk_text(text)
    if not chunks:
        return 0

    model = _get_embedding_model()
    embeddings = model.encode(chunks, show_progress_bar=False).tolist()

    client = _get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        collection = client.create_collection(collection_name)

    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]
    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)

    logger.info("Ingested %d chunks from '%s' into collection '%s'", len(chunks), filename, collection_name)
    return len(chunks)


def retrieve_chunks(query: str, collection_name: str, k: int = 5) -> List[dict]:
    """Return top-k semantically relevant chunks for query. Returns list of {content, source}."""
    client = _get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return []

    count = collection.count()
    if count == 0:
        return []

    model = _get_embedding_model()
    query_embedding = model.encode([query], show_progress_bar=False).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=min(k, count))

    return [
        {"content": doc, "source": meta.get("source", "Uploaded Document")}
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]


def collection_has_data(collection_name: str) -> bool:
    """Return True if the user's collection exists and has at least one chunk."""
    try:
        return _get_chroma_client().get_collection(collection_name).count() > 0
    except Exception:
        return False


def get_chunk_count(collection_name: str) -> int:
    """Return total number of chunks stored for this user."""
    try:
        return _get_chroma_client().get_collection(collection_name).count()
    except Exception:
        return 0


def delete_collection(collection_name: str) -> None:
    """Permanently delete a user's document collection."""
    try:
        _get_chroma_client().delete_collection(collection_name)
    except Exception:
        pass
