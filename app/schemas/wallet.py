from pydantic import BaseModel
from typing import Optional

from app import schemas


class Web3Sign(BaseModel):
    code: int
    verified: bool
    user: Optional[schemas.User]
