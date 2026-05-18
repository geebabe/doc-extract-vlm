from pydantic import BaseModel, Field
from typing import Optional, List
from .base import BBoxField

class GenericField(BaseModel):
    key: str = Field(description="The name or label of the field")
    value: BBoxField = Field(description="The extracted value and its bounding box")

class GeneralDocumentExtraction(BaseModel):
    title: Optional[BBoxField] = Field(default=None, description="Document title")
    document_number: Optional[BBoxField] = Field(default=None, description="Document reference number")
    date: Optional[BBoxField] = Field(default=None, description="Document date")
    issuer: Optional[BBoxField] = Field(default=None, description="Issuing organization or person")
    recipients: Optional[List[BBoxField]] = Field(default_factory=list, description="List of recipients")
    summary: Optional[BBoxField] = Field(default=None, description="Brief summary or abstract of the document")

    additional_fields: List[GenericField] = Field(
        default_factory=list,
        description="A list of key-value pairs for specific data points found in the document"
    )

    full_text: Optional[str] = Field(default=None, description="Complete raw text of the document")

class GeneralDocumentResponse(BaseModel):
    success: bool
    data: Optional[GeneralDocumentExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
