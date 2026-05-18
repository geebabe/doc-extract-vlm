from pydantic import BaseModel, Field
from typing import Optional
from .base import BBoxField

class IDCardExtraction(BaseModel):
    id_number: Optional[BBoxField] = Field(default=None, description="ID number (Số căn cước công dân)")
    full_name: Optional[BBoxField] = Field(default=None, description="Full name (Họ và tên)")
    date_of_birth: Optional[BBoxField] = Field(default=None, description="Date of birth (Ngày sinh)")
    gender: Optional[BBoxField] = Field(default=None, description="Gender (Giới tính)")
    nationality: Optional[BBoxField] = Field(default=None, description="Nationality (Quốc tịch)")
    place_of_origin: Optional[BBoxField] = Field(default=None, description="Place of origin (Quê quán)")
    place_of_residence: Optional[BBoxField] = Field(default=None, description="Place of residence (Nơi thường trú)")
    expiry_date: Optional[BBoxField] = Field(default=None, description="Expiry date (Có giá trị đến)")
    issue_date: Optional[BBoxField] = Field(default=None, description="Date of issue (Ngày cấp)")
    issue_place: Optional[BBoxField] = Field(default=None, description="Place of issue (Nơi cấp)")

class IDCardResponse(BaseModel):
    success: bool
    data: Optional[IDCardExtraction] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
