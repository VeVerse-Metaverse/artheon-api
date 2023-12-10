import datetime
from typing import Optional, Any, Dict

from app.config import settings
from app.schemas.config import CamelCaseModel


class Action(CamelCaseModel):
    id: str
    created_at: datetime.datetime
    user_id: str
    action_type: str
    version: Optional[str]

    class Config:
        orm_mode = True


class ActionCreate(CamelCaseModel):
    user_id: Optional[str]
    version: Optional[str]

    class Config:
        orm_mode = True


class ApiAction(Action):
    route: Optional[str]
    params: Optional[Dict]

    class Config:
        orm_mode = True


class ApiActionCreate(ActionCreate):
    method: str
    route: str
    params: Optional[Dict] = None
    result: Optional[Dict] = None
    version: str = settings.version

    class Config:
        orm_mode = True


class LauncherAction(Action):
    name: str
    machine_id: str
    os: str
    address: Optional[str]
    details: Optional[str]

    class Config:
        orm_mode = True


class LauncherActionCreate(ActionCreate):
    name: str
    machine_id: str
    os: str
    address: Optional[str]
    details: Optional[Dict]

    class Config:
        orm_mode = True


class ClientAction(Action):
    category: str
    name: str
    details: str

    class Config:
        orm_mode = True


class ClientActionCreate(ActionCreate):
    category: str
    name: str
    details: Optional[Dict]

    class Config:
        orm_mode = True


class ClientInteraction(ClientAction):
    interactive_id: str
    interactive_name: str
    interaction_type: str

    class Config:
        orm_mode = True


class ClientInteractionCreate(ClientActionCreate):
    interactive_id: Optional[str]
    interactive_name: Optional[str]
    interaction_type: Optional[str]

    class Config:
        orm_mode = True
