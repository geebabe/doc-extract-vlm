from pydantic import BaseModel, Field
from typing import Optional, List
from .base import BBoxField

class GenericField(BaseModel):
    key: str = Field(description="The name or label of the field")
    value: BBoxField = Field(description="The extracted value and its bounding box")

class GeneralDocumentExtraction(BaseModel):
    title: BBoxField = Field(description="Document title or heading. Often found at the top of the document.")
    document_number: BBoxField = Field(description='Document reference number or ID (e.g., report number, case ID). Often labelled: "Number", "Reference", "ID", "Số hiệu", "Mã số".')
    date: BBoxField = Field(description='Document date or issue date. Often labelled: "Date", "Issued", "Ngày", "Ngày lập".')
    issuer: BBoxField = Field(description='Organization, person, or entity that issued the document. Often labelled: "Issued by", "From", "Author", "Cơ quan cấp".')
    recipients: List[BBoxField] = Field(default_factory=list, description='List of recipients or intended parties. Often labelled: "To", "Recipient", "Gửi tới", "Người nhận".')
    summary: BBoxField = Field(description="Brief summary, abstract, or main content of the document.")
    additional_fields: List[GenericField] = Field(
        default_factory=list,
        description="List of key-value pairs for any other specific data points found in the document not covered by the standard fields."
    )
    full_text: Optional[str] = Field(default=None, description="Optional: complete raw text of the document if desired for further processing.")

class GeneralDocumentResponse(BaseModel):
    success: bool
    data: Optional[GeneralDocumentExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
