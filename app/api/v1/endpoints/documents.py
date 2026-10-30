import os
import shutil
from datetime import datetime
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from app.db.models import DocumentMetadata, DocumentUploadResponse
from app.db.vector_store import vector_store
from app.core.indexing.chunkers import DocumentParser, StructureAwareChunker
from app.core.indexing.embeddings import embedding_client

router = APIRouter()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get("", response_model=List[DocumentMetadata])
async def list_documents():
    """Returns list of indexed documents in the knowledge repository."""
    docs_dir = settings.DOCUMENTS_DIR
    files = []
    if os.path.exists(docs_dir):
        for f in os.listdir(docs_dir):
            full_path = os.path.join(docs_dir, f)
            if os.path.isfile(full_path):
                size_kb = os.path.getsize(full_path) / 1024.0
                files.append(
                    DocumentMetadata(
                        id=f,
                        filename=f,
                        size=f"{size_kb:.1f} KB" if size_kb < 1024 else f"{(size_kb/1024):.1f} MB",
                        status="ready",
                        created_at=datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
                        chunk_count=vector_store.count(f),
                    )
                )
    return files


@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(file: UploadFile = File(...)):
    """Uploads, parses, chunks, embeds, and indexes a document (sync def: FastAPI runs it in a threadpool)."""
    filename = os.path.basename(file.filename or "")
    if not filename.endswith((".pdf", ".txt", ".md")):
        raise HTTPException(status_code=400, detail="Only .pdf, .txt, and .md files supported.")
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB).")

    file_path = os.path.join(settings.DOCUMENTS_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Ingestion Pipeline: Parse -> Chunk -> Embed -> Index
    try:
        pages = DocumentParser.parse_file(file_path)
        chunker = StructureAwareChunker()
        chunks = chunker.chunk_document(filename, pages)

        if chunks:
            contents = [c["content"] for c in chunks]
            ids = [c["chunk_id"] for c in chunks]
            metas = [{"source": c["source"], "page": c["page"]} for c in chunks]

            embeddings = embedding_client.embed_documents(contents)
            vector_store.upsert_chunks(
                chunk_ids=ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metas,
            )

        return DocumentUploadResponse(
            id=filename,
            filename=filename,
            status="indexed",
            message=f"Successfully indexed {len(chunks)} chunks.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
