import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth import get_current_user
from app.db import fetch_maybe_one, get_user_client
from app.models import DocumentOut
from app.rag import BUCKET, chunk_text, delete_document_vectors, embed_and_store_chunks, extract_text

router = APIRouter(tags=["documents"])

ALLOWED_MIME_TYPES = {"text/plain", "text/markdown", "application/pdf"}


@router.post("/projects/{project_id}/documents", response_model=DocumentOut)
async def upload_document(project_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported file type")

    client = get_user_client(user["token"])
    content = await file.read()

    document_id = str(uuid.uuid4())
    storage_path = f"{project_id}/{document_id}/{file.filename}"

    document = client.table("documents").insert(
        {
            "id": document_id,
            "project_id": project_id,
            "filename": file.filename,
            "mime_type": file.content_type,
            "storage_path": storage_path,
            "status": "pending",
        }
    ).execute().data[0]

    try:
        client.storage.from_(BUCKET).upload(storage_path, content, {"content-type": file.content_type})
        text = extract_text(file.content_type, content)
        chunks = chunk_text(text)

        chunk_rows = []
        for index, chunk_content in enumerate(chunks):
            row = client.table("document_chunks").insert(
                {
                    "document_id": document_id,
                    "project_id": project_id,
                    "chunk_index": index,
                    "content": chunk_content,
                }
            ).execute().data[0]
            chunk_rows.append({"chunk_id": row["id"], "chunk_index": index, "content": chunk_content})

        embed_and_store_chunks(project_id, document_id, file.filename, chunk_rows)
        updated = client.table("documents").update({"status": "indexed"}).eq("id", document_id).execute().data[0]
    except Exception as exc:
        client.table("document_chunks").delete().eq("document_id", document_id).execute()
        delete_document_vectors(document_id)
        updated = (
            client.table("documents")
            .update({"status": "failed", "error": str(exc)})
            .eq("id", document_id)
            .execute()
            .data[0]
        )

    return updated


@router.get("/projects/{project_id}/documents", response_model=list[DocumentOut])
def list_documents(project_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    return (
        client.table("documents")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )


@router.delete("/projects/{project_id}/documents/{document_id}")
def delete_document(project_id: str, document_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    document = fetch_maybe_one(
        client.table("documents").select("storage_path").eq("id", document_id).eq("project_id", project_id)
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    client.storage.from_(BUCKET).remove([document["storage_path"]])
    delete_document_vectors(document_id)
    client.table("documents").delete().eq("id", document_id).execute()
    return {"status": "deleted"}
