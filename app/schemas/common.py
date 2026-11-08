from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

