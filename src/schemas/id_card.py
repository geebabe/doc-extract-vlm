from pydantic import BaseModel, Field
from typing import Optional
from .base import BBoxField


class IDCardFront(BaseModel):
    id_number: BBoxField = Field(description="ID number (Số căn cước công dân / Số/No.) printed near the top or below the portrait.")
    full_name: BBoxField = Field(description="Full name (Họ và tên / Full name). Printed in plain text.")
    date_of_birth: BBoxField = Field(description='Date of birth (Ngày sinh / Date of birth). Preserve exact format (e.g. "01/01/1990").')
    gender: BBoxField = Field(description='Gender (Giới tính / Sex). Values: "Nam" or "Nữ".')
    nationality: BBoxField = Field(description='Nationality (Quốc tịch / Nationality). Usually "Việt Nam".')
    place_of_origin: BBoxField = Field(description="Place of origin (Quê quán / Place of origin).")
    place_of_residence: BBoxField = Field(description="Place of residence (Nơi thường trú / Place of residence). May span multiple lines — concatenate with a single space.")
    expiry_date: BBoxField = Field(description="Expiry date (Có giá trị đến / Date of expiry). Printed on the front of the card.")


class IDCardBack(BaseModel):
    id_number: BBoxField = Field(description="ID number decoded from MRZ (positions 6–17 after 'IDVNM' prefix).")
    full_name: BBoxField = Field(description="Full name decoded from MRZ name section (after '<<'). Restore Vietnamese diacritics where obvious. Prefer printed text if visible.")
    date_of_birth: BBoxField = Field(description='Date of birth decoded from MRZ (YYMMDD → DD/MM/YYYY). Prefer printed text if visible.')
    gender: BBoxField = Field(description='Gender decoded from MRZ (M → "Nam", F → "Nữ"). Prefer printed text if visible.')
    nationality: BBoxField = Field(description='Nationality decoded from MRZ ("VNM" → "Việt Nam"). Prefer printed text if visible.')
    expiry_date: BBoxField = Field(description='Expiry date decoded from MRZ second line (YYMMDD → DD/MM/YYYY). Also may be printed as "Có giá trị đến: DD/MM/YYYY".')
    place_of_residence: BBoxField = Field(description="Place of residence (Nơi thường trú) if printed on the back. Null if absent.")
    issue_date: BBoxField = Field(description="Date of issue (Ngày, tháng, năm / Date of issue). Printed near the issuing officer's signature.")
    issue_place: BBoxField = Field(description='Place of issue (Nơi cấp). Often "CỤC TRƯỞNG CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI" or "BỘ CÔNG AN".')


class IDCardExtraction(BaseModel):
    """Union schema for API responses — accepts output from either IDCardFront or IDCardBack."""
    id_number: Optional[BBoxField] = None
    full_name: Optional[BBoxField] = None
    date_of_birth: Optional[BBoxField] = None
    gender: Optional[BBoxField] = None
    nationality: Optional[BBoxField] = None
    place_of_origin: Optional[BBoxField] = None
    place_of_residence: Optional[BBoxField] = None
    expiry_date: Optional[BBoxField] = None
    issue_date: Optional[BBoxField] = None
    issue_place: Optional[BBoxField] = None


class IDCardResponse(BaseModel):
    success: bool
    data: Optional[IDCardExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
