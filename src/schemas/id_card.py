from pydantic import BaseModel, Field
from typing import Optional
from .base import BBoxField

class IDCardExtraction(BaseModel):
    id_number: BBoxField = Field(description="ID number (Số căn cước công dân / Số/No.) printed near the top or below the portrait.")
    full_name: BBoxField = Field(description="Full name (Họ và tên / Full name). Printed in plain text.")
    date_of_birth: BBoxField = Field(description='Date of birth (Ngày sinh / Date of birth). Preserve exact format (e.g. "01/01/1990").')
    gender: BBoxField = Field(description='Gender (Giới tính / Sex). Values: "Nam" or "Nữ".')
    nationality: BBoxField = Field(description='Nationality (Quốc tịch / Nationality). Usually "Việt Nam".')
    place_of_origin: BBoxField = Field(description="Place of origin (Quê quán / Place of origin).")
    place_of_residence: BBoxField = Field(description="Place of residence (Nơi thường trú / Place of residence). May span multiple lines — concatenate with a single space.")
    expiry_date: BBoxField = Field(description="Expiry date (Có giá trị đến / Date of expiry). Printed on newer cards on the front.")
    issue_date: BBoxField = Field(description="Date of issue (Ngày, tháng, năm / Date of issue). Printed near the issuing officer's signature on the back.")
    issue_place: BBoxField = Field(description='Place of issue (Nơi cấp). Often "CỤC TRƯỞNG CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI" or "BỘ CÔNG AN".')

class IDCardResponse(BaseModel):
    success: bool
    data: Optional[IDCardExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
