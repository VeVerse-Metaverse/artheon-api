from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app import schemas, crud
from app.dependencies import database

router = APIRouter()


@router.get("/windows")
def download_windows(request: Request, source: str = '', invite: str = "", db: Session = Depends(database.session)):
    ip = request.headers.get("X-Forwarded-For")
    if not ip:
        ip = request.client.host

    action = schemas.ApiActionCreate(method="get", route="/download/windows", params={"ip": ip, "source": source, "invite": invite}, result=None)

    requester = crud.user.get_internal_user(db)
    if requester:
        action.user_id = requester.id

    action.result = {"code": 307}
    crud.user.report_api_action(db, requester=requester, action=action)

    return RedirectResponse(url="https://release.prod.veverse.com/launcher/Setup.exe")


@router.get("/mac")
def download_mac(request: Request, source: str = '', invite: str = "", db: Session = Depends(database.session)):
    ip = request.headers.get("X-Forwarded-For")
    if not ip:
        ip = request.client.host

    action = schemas.ApiActionCreate(method="get", route="/download/mac", params={"ip": ip, "source": source, "invite": invite}, result=None)

    requester = crud.user.get_internal_user(db)
    if requester:
        action.user_id = requester.id

    action.result = {"code": 307}
    crud.user.report_api_action(db, requester=requester, action=action)

    return RedirectResponse(url="https://release.prod.veverse.com/mac/VeVerse.pkg")


@router.get("/linux")
def download_mac(request: Request, source: str = '', invite: str = "", db: Session = Depends(database.session)):
    ip = request.headers.get("X-Forwarded-For")
    if not ip:
        ip = request.client.host

    action = schemas.ApiActionCreate(method="get", route="/download/windows", params={"ip": ip, "source": source, "invite": invite}, result=None)

    requester = crud.user.get_internal_user(db)
    if requester:
        action.user_id = requester.id

    action.result = {"code": 307}
    crud.user.report_api_action(db, requester=requester, action=action)

    return RedirectResponse(url="https://release.prod.veverse.com/linux/veverse.tar.gz")
