from typing import List, Optional

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str

    name: str

    description: str = ""

    role: Optional[str] = None

    objectives: List[str] = Field(default_factory=list)

    responsibilities: List[str] = Field(default_factory=list)

    tools: List[str] = Field(default_factory=list)

    skills: List[str] = Field(default_factory=list)

    results: List[str] = Field(default_factory=list)

    challenges: List[str] = Field(default_factory=list)