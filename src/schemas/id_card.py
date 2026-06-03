from pydantic import BaseModel, Field
from typing import Optional
from .base import BBoxField

class IDCardExtraction(BaseModel):
    id_number: BBoxField = Field(description="ID number (Số căn cước công dân)")
    full_name: BBoxField = Field(description="Full name (Họ và tên)")
    date_of_birth: BBoxField = Field(description="Date of birth (Ngày sinh)")
    gender: BBoxField = Field(description="Gender (Giới tính)")
    nationality: BBoxField = Field(description="Nationality (Quốc tịch)")
    place_of_origin: BBoxField = Field(description="Place of origin (Quê quán)")
    place_of_residence: BBoxField = Field(description="Place of residence (Nơi thường trú)")
    expiry_date: BBoxField = Field(description="Expiry date (Có giá trị đến)")
    issue_date: BBoxField = Field(description="Date of issue (Ngày cấp)")
    issue_place: BBoxField = Field(description="Place of issue (Nơi cấp)")

class IDCardResponse(BaseModel):
    success: bool
    data: Optional[IDCardExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
