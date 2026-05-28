from pydantic import BaseModel, Field
from typing import List, Optional

from .base import BBoxField

class VendorInfo(BaseModel):
    name: Optional[BBoxField] = Field(default=None)
    address: Optional[BBoxField] = Field(default=None)
    tax_code: Optional[BBoxField] = Field(default=None)
    phone: Optional[BBoxField] = Field(default=None)

class InvoiceItem(BaseModel):
    description: BBoxField = Field(description="Item name or description")
    quantity: Optional[BBoxField] = Field(default=None, description="Quantity of the item")
    unit_price: Optional[BBoxField] = Field(default=None, description="Price per unit")
    total_amount: Optional[BBoxField] = Field(default=None, description="Total amount for this item")

class InvoiceExtraction(BaseModel):
    invoice_number: Optional[BBoxField] = Field(default=None)
    invoice_date: Optional[BBoxField] = Field(default=None)
    vendor: Optional[VendorInfo] = Field(default=None)
    items: List[InvoiceItem] = Field(default_factory=list, description="List of items in the invoice")
    # tax: Optional[BBoxField] = Field(default=None)
    total_amount: Optional[BBoxField] = Field(default=None)
    currency: Optional[BBoxField] = Field(default=None, description="Currency code (e.g., VND, USD)")

class InvoiceResponse(BaseModel):
    success: bool
    data: Optional[InvoiceExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
