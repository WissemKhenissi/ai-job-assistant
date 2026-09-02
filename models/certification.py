from datetime import date
from typing import Optional

from pydantic import BaseModel


class Certification(BaseModel):
    id: str

    name: str

    organization: str

    obtained_date: Optional[date] = None

    expiration_date: Optional[date] = None

    credential_id: Optional[str] = None

    credential_url: Optional[str] = None

    description: str = ""