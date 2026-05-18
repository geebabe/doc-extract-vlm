from pydantic import BaseModel

class ExtractURLRequest(BaseModel):
    url: str
