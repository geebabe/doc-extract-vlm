from pydantic import BaseModel, Field
from typing import Optional, Tuple, Union

class BBoxField(BaseModel):
    value: Union[str, float, int, None] = Field(description="The extracted text or numeric value")
    bounding_box: Optional[Tuple[int, int, int, int]] = Field(
        default=None, 
        description="Bounding box coordinates [xmin, ymin, xmax, ymax] normalized to [0, 1000]"
    )

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
