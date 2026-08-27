from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: int
    title: str
    filename: str
    status: str
    file_size_bytes: Optional[int] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class DocumentRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class UploadResponse(BaseModel):
    message: str
    documents: list[DocumentResponse]