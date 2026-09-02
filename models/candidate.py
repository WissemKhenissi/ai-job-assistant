from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from models.experience import Experience

class Candidate(BaseModel):
    id: str

    first_name: str = ""
    last_name: str = ""

    email: str = ""
    phone: str = ""
    city: str = ""

    professional_title: str = ""
    summary: str = ""

    experiences: List[Experience] = Field(default_factory=list)
    skills: List[dict] = Field(default_factory=list)
    projects: List[dict] = Field(default_factory=list)
    education: List[dict] = Field(default_factory=list)
    certifications: List[dict] = Field(default_factory=list)
    languages: List[dict] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)