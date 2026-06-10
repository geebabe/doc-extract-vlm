from pydantic import BaseModel, Field
from typing import List, Optional

from .base import BBoxField

class VendorInfo(BaseModel):
    name: BBoxField = Field(description='Full legal name of the issuing company/vendor. Often labelled: "Đơn vị bán hàng", "Công ty", "Seller", "Vendor".')
    address: BBoxField = Field(description='Full address of the vendor. Often labelled: "Địa chỉ:", "Address:". Include street, district, city.')
    tax_code: BBoxField = Field(description='Tax identification number of the vendor. Often labelled: "Mã số thuế:", "MST:", "Tax Code:", "Tax ID:". Typically a 10 or 13-digit number.')
    phone: BBoxField = Field(description='Phone or fax number of the vendor. Often labelled: "Điện thoại:", "ĐT:", "Tel:", "Phone:".')

class InvoiceItem(BaseModel):
    description: BBoxField = Field(description='Name or description of the product/service. Often in the "Tên hàng hóa, dịch vụ", "Description", "Diễn giải" column.')
    quantity: BBoxField = Field(description='Number of units. Often in the "Số lượng", "Qty", "SL" column. Preserve exact value (e.g. "2", "1.5").')
    unit_price: BBoxField = Field(description='Price per unit. Often in the "Đơn giá", "Unit Price" column. Preserve exact numeric formatting.')
    total_amount: BBoxField = Field(description='Line total for this item (quantity × unit_price). Often in the "Thành tiền", "Amount", "Tổng" column. Preserve exact numeric formatting.')

class InvoiceExtraction(BaseModel):
    invoice_number: BBoxField = Field(description='The unique identifier of this invoice (e.g. "0001234", "INV-2024-001"). Often labelled: "Số hóa đơn", "Số:", "Invoice No.", "No.".')
    invoice_date: BBoxField = Field(description='The date the invoice was issued. Often labelled: "Ngày", "Date", "Ngày lập", "Ngày phát hành". Preserve exact formatting (e.g. "15/03/2024").')
    vendor: VendorInfo = Field(description="Vendor (seller) information.")
    items: List[InvoiceItem] = Field(default_factory=list, description="List of line items in the invoice. Extract ALL line items from the invoice table.")
    total_amount: BBoxField = Field(description='Final invoice amount due including all taxes and fees. Often labelled: "Tổng cộng", "Total", "Số tiền thanh toán", "Amount Due". Preserve exact numeric formatting.')
    currency: BBoxField = Field(description='Currency code or symbol used in the invoice (e.g. "VND", "USD", "đ"). If no explicit currency is stated, output null.')

class InvoiceResponse(BaseModel):
    success: bool
    data: Optional[InvoiceExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
