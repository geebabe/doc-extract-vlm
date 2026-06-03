from pydantic import BaseModel, Field
from typing import List, Optional

from .base import BBoxField

class VendorInfo(BaseModel):
    name: BBoxField = Field(description="Vendor name")
    address: BBoxField = Field(description="Vendor address")
    tax_code: BBoxField = Field(description="Vendor tax code")
    phone: BBoxField = Field(description="Vendor phone")

class InvoiceItem(BaseModel):
    description: BBoxField = Field(description="Item name or description")
    quantity: BBoxField = Field(description="Quantity of the item")
    unit_price: BBoxField = Field(description="Price per unit")
    total_amount: BBoxField = Field(description="Total amount for this item")

class InvoiceExtraction(BaseModel):
    invoice_number: BBoxField = Field(description="Invoice number")
    invoice_date: BBoxField = Field(description="Invoice date")
    vendor: VendorInfo = Field(description="Vendor information")
    items: List[InvoiceItem] = Field(default_factory=list, description="List of items in the invoice")
    total_amount: BBoxField = Field(description="Total invoice amount")
    currency: BBoxField = Field(description="Currency code (e.g., VND, USD)")

class InvoiceResponse(BaseModel):
    success: bool
    data: Optional[InvoiceExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
