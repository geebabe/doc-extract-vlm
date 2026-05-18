from pydantic import BaseModel, Field
from typing import Optional, Tuple, Union

class BBoxField(BaseModel):
    value: Union[str, float, int, None] = Field(description="The extracted text or numeric value")
    bounding_box: Optional[Tuple[int, int, int, int]] = Field(
        default=None, 
        description="Bounding box coordinates [xmin, ymin, xmax, ymax] normalized to [0, 1000]"
    )
