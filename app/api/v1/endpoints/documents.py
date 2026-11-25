import os
import shutil
import hmac
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException, Header
from app.config import settings
from app.db.models import DocumentMetadata, DocumentUploadResponse
from app.db.vector_store import vector_store
from app.core.indexing.chunkers import DocumentParser, StructureAwareChunker
from app.core.indexing.embeddings import embedding_client
from app.core.tools.local_retriever import local_retriever
from app.core.privacy import privacy_guard

router = APIRouter()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get("", response_model=List[DocumentMetadata])
async def list_documents(tenant_id: Optional[str] = Query(default="default")):
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
def upload_document(file: UploadFile = File(...), tenant_id: str = Form(default="default")):
    """Uploads, parses, chunks, embeds, and indexes a document (sync def: FastAPI runs it in a threadpool)."""
    filename = os.path.basename(file.filename or "")
    if not filename.endswith((".pdf", ".txt", ".md")):
        raise HTTPException(status_code=400, detail="Only .pdf, .txt, and .md files supported.")
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB).")

    file_path = os.path.join(settings.DOCUMENTS_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Ingestion Pipeline: Parse -> Chunk -> Redact Secrets -> Embed -> Index
    try:
        pages = DocumentParser.parse_file(file_path)
        chunker = StructureAwareChunker()
        chunks = chunker.chunk_document(filename, pages)

        if chunks:
            contents = [privacy_guard.redact_secrets(c["content"]) for c in chunks]
            ids = [c["chunk_id"] for c in chunks]
            metas = [{"source": c["source"], "page": c["page"], "tenant_id": tenant_id or "default"} for c in chunks]

            embeddings = embedding_client.embed_documents(contents)
            vector_store.delete_by_source(filename)
            vector_store.upsert_chunks(
                chunk_ids=ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metas,
            )
            local_retriever.invalidate_cache()

        return DocumentUploadResponse(
            id=filename,
            filename=filename,
            status="indexed",
            message=f"Successfully indexed {len(chunks)} chunks.",
        )
    except Exception as e:
        safe_err = privacy_guard.sanitize_for_log(str(e))
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {safe_err}")


@router.delete("/{filename}")
def delete_document(filename: str, x_admin_pin: str = Header(default="")):
    """Deletes a document from the local store and vector DB after validating admin pin."""
    expected_pin = settings.ADMIN_DELETE_PIN
    if not expected_pin or not hmac.compare_digest(x_admin_pin, expected_pin):
        raise HTTPException(status_code=403, detail="Invalid admin PIN. Unauthorized to delete.")

    file_path = os.path.join(settings.DOCUMENTS_DIR, os.path.basename(filename))
    if os.path.exists(file_path):
        os.remove(file_path)

    vector_store.delete_by_source(filename)
    local_retriever.invalidate_cache()
    return {"status": "deleted", "filename": filename}
