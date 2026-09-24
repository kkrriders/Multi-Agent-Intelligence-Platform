import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import Connection, text

from app import storage
from app.db import get_db, maybe_one, one, rows
from app.models import DocumentOut
from app.rag import chunk_text, delete_document_vectors, embed_and_store_chunks, extract_text

router = APIRouter(tags=["documents"])

ALLOWED_MIME_TYPES = {"text/plain", "text/markdown", "application/pdf"}


@router.post("/projects/{project_id}/documents", response_model=DocumentOut)
async def upload_document(project_id: str, file: UploadFile = File(...), conn: Connection = Depends(get_db)):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported file type")
    if not file.filename:
        raise HTTPException(status_code=422, detail="Filename is required")
    filename = file.filename

    content = await file.read()

    document_id = str(uuid.uuid4())
    # The stored path only ever uses the bare file name, so a client-supplied "../x" cannot escape.
    storage_path = f"{project_id}/{document_id}/{Path(filename).name}"

    # RLS's `with check` rejects a foreign project_id here, so bytes are only written for owned projects.
    conn.execute(
        text(
            "insert into documents (id, project_id, filename, mime_type, storage_path, status) "
            "values (:id, :p, :f, :m, :s, 'pending')"
        ),
        {"id": document_id, "p": project_id, "f": filename, "m": file.content_type, "s": storage_path},
    )

    try:
        storage.save(storage_path, content)
        extracted = extract_text(file.content_type, content)
        chunks = chunk_text(extracted)

        chunk_rows = []
        for index, chunk_content in enumerate(chunks):
            row = one(
                conn.execute(
                    text(
                        "insert into document_chunks (document_id, project_id, chunk_index, content) "
                        "values (:d, :p, :i, :c) returning id"
                    ),
                    {"d": document_id, "p": project_id, "i": index, "c": chunk_content},
                )
            )
            chunk_rows.append({"chunk_id": row["id"], "chunk_index": index, "content": chunk_content})

        embed_and_store_chunks(project_id, document_id, filename, chunk_rows)
        updated = one(
            conn.execute(
                text("update documents set status = 'indexed' where id = :i returning *"), {"i": document_id}
            )
        )
    except Exception as exc:
        conn.execute(text("delete from document_chunks where document_id = :d"), {"d": document_id})
        delete_document_vectors(document_id)
        updated = one(
            conn.execute(
                text("update documents set status = 'failed', error = :e where id = :i returning *"),
                {"e": str(exc), "i": document_id},
            )
        )

    return updated


@router.get("/projects/{project_id}/documents", response_model=list[DocumentOut])
def list_documents(project_id: str, conn: Connection = Depends(get_db)):
    return rows(
        conn.execute(
            text("select * from documents where project_id = :p order by created_at desc"), {"p": project_id}
        )
    )


@router.delete("/projects/{project_id}/documents/{document_id}")
def delete_document(project_id: str, document_id: str, conn: Connection = Depends(get_db)):
    document = maybe_one(
        conn.execute(
            text("select storage_path from documents where id = :i and project_id = :p"),
            {"i": document_id, "p": project_id},
        )
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    storage.delete(document["storage_path"])
    delete_document_vectors(document_id)
    conn.execute(text("delete from documents where id = :i"), {"i": document_id})
    return {"status": "deleted"}
