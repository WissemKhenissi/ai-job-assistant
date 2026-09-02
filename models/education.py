from typing import Optional

from pydantic import BaseModel


class Education(BaseModel):
    id: str

    institution: str
    degree: str

    field_of_study: Optional[str] = None

    start_year: Optional[int] = None
    end_year: Optional[int] = None

    description: str = ""