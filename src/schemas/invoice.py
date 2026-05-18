from pydantic import BaseModel, Field
from typing import Optional

from .base import BBoxField

class VendorInfo(BaseModel):
    name: Optional[BBoxField] = Field(default=None)
    address: Optional[BBoxField] = Field(default=None)
    tax_code: Optional[BBoxField] = Field(default=None)
    phone: Optional[BBoxField] = Field(default=None)

class InvoiceExtraction(BaseModel):
    invoice_number: Optional[BBoxField] = Field(default=None)
    invoice_date: Optional[BBoxField] = Field(default=None)
    vendor: Optional[VendorInfo] = Field(default=None)
    subtotal: Optional[BBoxField] = Field(default=None)
    tax: Optional[BBoxField] = Field(default=None)
    total_amount: Optional[BBoxField] = Field(default=None)
    currency: Optional[BBoxField] = Field(default=None)

class InvoiceResponse(BaseModel):
    success: bool
    data: Optional[InvoiceExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
