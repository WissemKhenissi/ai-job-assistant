from typing import List, Optional

from pydantic import BaseModel, Field


class Skill(BaseModel):
    id: str

    name: str

    category: Optional[str] = None

    level: Optional[str] = None

    years_experience: Optional[float] = None

    description: str = ""

    contexts: List[str] = Field(default_factory=list)

    evidence: List[str] = Field(default_factory=list)

    related_experiences: List[str] = Field(default_factory=list)

    related_projects: List[str] = Field(default_factory=list)