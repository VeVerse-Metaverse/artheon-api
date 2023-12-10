import logging
import os

import inject
import time
from typing import Optional, Any
from string import Template

# from faker import Faker
# from faker.providers import internet, misc, person
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Path
from fastapi.responses import HTMLResponse
from fastapi_caching import ResponseCache
from sqlalchemy.orm import Session
from starlette import status
from starlette.requests import Request

from app import schemas, crud, models, templates
from app.config import settings
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError
from app.dependencies import auth, database
from app.schemas.payload import Payload
from app.schemas.wallet import Web3Sign
from app.services import cache
from app.services import email

router = APIRouter()

# Faker is used to generate random user email and name when registering using device id.
# Faker.seed(int(time.time()))
# fake = Faker()
# fake.add_provider(internet)
# fake.add_provider(person)
# fake.add_provider(misc)


# noinspection PyShadowingNames
@router.get("", response_model=Payload[schemas.EntityBatch[schemas.UserRef]])
async def index_users(query: Optional[str] = '', offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users", params=params, result=None, user_id=requester.id)

    try:
        users = crud.user.index_with_query(db, requester=requester, offset=offset, limit=limit, query=query)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    action.result = {"code": 200, "count": len(users.entities), "total": users.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.UserRef]](data=users)


# noinspection PyShadowingNames
@router.get("/address/{ethAddress}", response_model=Payload[schemas.UserRef])
async def index_users(ethAddress: Optional[str] = '', db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"ethAddress": ethAddress}
    action = schemas.ApiActionCreate(method="get", route="/users/address", params=params, result=None, user_id=requester.id)

    try:
        user = crud.user.get_by_eth_address(db, requester=requester, address=ethAddress)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.UserRef](data=user)


@router.post("", response_model=Payload[schemas.User])
def register(request: Request, user: schemas.UserCreate, db: Session = Depends(database.session)):
    params = {"name": user.name, "email": user.email, "invite": user.invite_code}
    action = schemas.ApiActionCreate(method="post", route="/users", params=params, result=None, user_id=None)

    requester = crud.user.get_internal_user(db)
    if requester:
        action.user_id = requester.id

    try:
        user = crud.user.create(db, requester=None, entity=user, ip=request.client.host)
    except EntityParameterError as e:
        if requester:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        if requester:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        if requester:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=user)


@router.get("/activate/{token}", response_class=HTMLResponse)
def activate_with_token(token: str, db: Session = Depends(database.session)):
    params = {"token": token}
    action = schemas.ApiActionCreate(method="get", route="/users/activate/{token}", params=params, result=None, user_id=None)

    requester = crud.user.get_internal_user(db)
    if requester:
        action.user_id = requester.id

    try:
        user = crud.user.activate_with_token(db, token=token)
    except EntityParameterError as e:
        if str(e) == 'already activated':
            if requester:
                action.result = {"code": 200, "ok": False}
                crud.user.report_api_action(db, requester=requester, action=action)
            return templates.html.already_activated
        if requester:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        if requester:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        if requester:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if user:
        action.user_id = user.id
        action.result = {"code": 200, "ok": True}
        crud.user.report_api_action(db, requester=requester, action=action)
        return templates.html.activated


@router.get("/confirm/wallet/{address}/{token}")
def confirm_wallet_with_token(address: str, token: str, db: Session = Depends(database.session)):
    params = {"address": address, "token": token}
    action = schemas.ApiActionCreate(method="get", route="/users/confirm/wallet/{address}/{token}", params=params, result=None, user_id=None)

    requester = crud.user.get_internal_user(db)
    if requester:
        action.user_id = requester.id

    try:
        user = crud.user.confirm_wallet_with_token(db, address=address, token=token)
    except EntityParameterError as e:
        if str(e) == 'already confirmed':
            if requester:
                action.result = {"code": 200, "ok": False}
                crud.user.report_api_action(db, requester=requester, action=action)
            return templates.wallet_confirmed.already_confirmed
        if requester:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        if requester:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        if requester:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if user:
        action.user_id = user.id
        action.result = {"code": 200, "ok": True}
        crud.user.report_api_action(db, requester=requester, action=action)
        return templates.wallet_confirmed.confirmed


@router.post("/link/address", response_model=Payload[Web3Sign])
def link_wallet_address(address: str = Body(...), signature: str = Body(...), emailAddress: str = Body(...), db: Session = Depends(database.session)):
    params = {"address": address, "signature": signature, "email": emailAddress}
    requester = crud.user.get_internal_user(db)
    action = schemas.ApiActionCreate(method="post", route="/link/address", params=params, result=None, user_id=None)

    message = 'Please sign to link wallet & account email: {email}'.format(email=emailAddress)

    try:
        result = crud.user.verifySignedMsg(db, requester=requester, address=address, signature=signature, message=message, email=emailAddress)
        if result["verified"]:
            user = result["user"]
            if user.is_address_confirmed is None or user.is_address_confirmed is False:
                crud.user.confirm_link(requester=user, address=address)

    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    return Payload(data={"code": 200, "verified": result["verified"]})


@router.post("/invite", response_model=Payload[schemas.Ok])
def invite(email: str, db: Session = Depends(database.session), requester=Depends(auth.requester)):
    params = {"email": email}
    action = schemas.ApiActionCreate(method="post", route="/users/invite", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.user.invite(db, requester=requester, email=email)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.Ok(ok=ok))


# noinspection PyShadowingNames
@router.get("/admins", response_model=Payload[schemas.EntityBatch[schemas.UserRef]])
async def get_admins(offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                     cache: ResponseCache = cache.from_request()):
    params = {"offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/admins", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        admins = cache.data
    else:
        try:
            admins = crud.user.index_admins(db, requester=requester, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(admins, tag="user_admins", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(admins.entities), "total": admins.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.UserAdminRef]](data=admins)


# noinspection PyShadowingNames
@router.get("/muted", response_model=Payload[schemas.EntityBatch[schemas.UserRef]])
async def get_muted(offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                    cache: ResponseCache = cache.from_request()):
    params = {"offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/muted", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        users = cache.data
    else:
        try:
            users = crud.user.index_muted(db, requester=requester, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(users, tag="user_muted", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(users.entities), "total": users.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.UserRef]](data=users)


# noinspection PyShadowingNames
@router.get("/banned", response_model=Payload[schemas.EntityBatch[schemas.UserRef]])
async def get_banned(offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                     cache: ResponseCache = cache.from_request()):
    params = {"offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/banned", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        users = cache.data
    else:
        try:
            users = crud.user.index_banned(db, requester=requester, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(users, tag="user_banned", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(users.entities), "total": users.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.UserRef]](data=users)


# region Me
@router.get("/me", response_model=Payload[schemas.User])
async def get_me(db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    action = schemas.ApiActionCreate(method="get", route="/users/me", params=None, result={"code": 200}, user_id=requester.id)
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=requester)


@router.patch("/me", response_model=Payload[schemas.UserRef])
def update_me(patch: schemas.UserUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"name": patch.name, "description": patch.description}
    action = schemas.ApiActionCreate(method="patch", route="/users/me", params=params, result=None, user_id=requester.id)

    try:
        requester = crud.user.update(db, requester=requester, entity=requester, patch=patch)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.UserRef](data=requester)


# todo: implement password reset functionality
@router.post("/password/reset", response_model=Payload[schemas.Ok])
def reset_password(email: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    pass


@router.patch("/me/password", response_model=Payload[schemas.UserRef])
def update_password(patch: schemas.UserUpdatePassword, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    action = schemas.ApiActionCreate(method="patch", route="/users/me/password", params=None, result=None, user_id=requester.id)

    try:
        ok = crud.user.update_password(db, requester=requester, entity=requester, patch=patch)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.Ok(ok=ok))


@router.patch("/me/heartbeat", response_model=Payload[schemas.Ok])
def heartbeat_user(space_id: str = None, server_id: str = None, presence_status: str = 'offline', db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    try:
        ok = crud.user.heartbeat(db, requester=requester, space_id=space_id, server_id=server_id, status=presence_status)
    except EntityParameterError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return Payload(data=schemas.Ok(ok=ok))


@router.put("/me/avatars", response_model=Payload[schemas.FileRef])
async def upload_avatar(uploaded_file: UploadFile = File(...), db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"name": uploaded_file.filename}
    action = schemas.ApiActionCreate(method="put", route="/users/me/avatars", params=params, result=None, user_id=requester.id)

    try:
        file = await crud.user.upload_avatar(db, requester=requester, entity=requester, upload_file=uploaded_file)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    action.result = {"code": 200, "id": file.id, "url": file.url, "size": file.size, "mime": file.mime}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.FileRef](data=file)


@router.delete("/me/avatars")
async def delete_avatar(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="delete", route="/users/me/avatars", params=params, result=None, user_id=requester.id)

    try:
        await crud.user.delete_avatar(db, requester=requester, entity=requester, id=id)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)


@router.get("/me/invitations", response_model=Payload[schemas.InvitationTotal])
def get_invitations(db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    action = schemas.ApiActionCreate(method="delete", route="/users/me/avatars", params=None, result=None, user_id=requester.id)

    try:
        total = crud.user.get_invitations(db, requester=requester)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=total)


# endregion

# noinspection PyShadowingNames
@router.get("/{id}", response_model=Payload[schemas.UserRef])
async def get_user(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}", params=params, result=None, user_id=requester.id)

    try:
        user = crud.user.get(db, requester=requester, id=id)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=user)


@router.get("/{id}/experience", response_model=Payload[schemas.UserExperienceRef])
async def get_user(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/experience/{id}", params=params, result=None, user_id=requester.id)

    try:
        user = crud.user.get(db, requester=requester, id=id)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "experience": user.experience, "level": user.level}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=user)


@router.patch("/{id}", response_model=Payload[schemas.UserRef])
def update_user(id: str, patch: schemas.UserUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "name": patch.name, "description": patch.description}
    action = schemas.ApiActionCreate(method="patch", route="/users/id", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.user.update(db, requester=requester, entity=id, patch=patch)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=entity)


@router.delete("/{id}")
def delete_user(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="delete", route="/users/{id}", params=params, result=None, user_id=requester.id)

    try:
        crud.user.delete(db, requester=requester, entity=id)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)


# noinspection PyShadowingNames
@router.get("/{id}/liked/spaces", response_model=Payload[schemas.EntityBatch[schemas.SpaceRef]])
async def get_user_liked_spaces(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                                cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/liked/spaces", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        spaces = cache.data
    else:
        try:
            spaces = crud.user.index_liked_entities(db, requester=requester, user=id, model=models.Space, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(spaces, tag="user_liked_spaces", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(spaces.entities), "total": spaces.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.SpaceRef]](data=spaces)


# noinspection PyShadowingNames
@router.get("/{id}/liked/objects", response_model=Payload[schemas.EntityBatch[schemas.ObjectRef]])
async def get_user_liked_objects(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                                 cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/liked/spaces", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        objects = cache.data
    else:
        try:
            objects = crud.user.index_liked_entities(db, requester=requester, user=id, model=models.Object, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(objects, tag="user_liked_objects", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(objects.entities), "total": objects.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.ObjectRef]](data=objects)


# noinspection PyShadowingNames
@router.get("/{id}/liked/collections", response_model=Payload[schemas.EntityBatch[schemas.CollectionRef]])
async def get_user_liked_collections(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                                     cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/liked/spaces", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        collections = cache.data
    else:
        try:
            collections = crud.user.index_liked_entities(db, requester=requester, user=id, model=models.Collection, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(collections, tag="user_liked_collections", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(collections.entities), "total": collections.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.CollectionRef]](data=collections)


# noinspection PyShadowingNames
@router.get("/{id}/liked/users", response_model=Payload[schemas.EntityBatch[schemas.UserRef]])
async def get_user_liked_users(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                               cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/liked/spaces", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        users = cache.data
    else:
        try:
            users = crud.user.index_liked_entities(db, requester=requester, user=id, model=models.User, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(users, tag="user_liked_users", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(users.entities), "total": users.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.UserRef]](data=users)


# noinspection PyShadowingNames
@router.get("/{id}/followers", response_model=Payload[schemas.EntityBatch[schemas.UserFriendRef]])
async def get_user_followers(id: str, offset: int = 0, limit: int = 10, include_friends: bool = True, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/followers", params=params, result=None, user_id=requester.id)

    try:
        followers = crud.user.index_followers(db, requester=requester, user=id, offset=offset, limit=limit, include_friends=include_friends)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "count": len(followers.entities), "total": followers.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.UserRef]](data=followers)


# noinspection PyShadowingNames
@router.get("/{id}/leaders", response_model=Payload[schemas.EntityBatch[schemas.UserFriendRef]])
async def get_user_leaders(id: str, offset: int = 0, limit: int = 10, include_friends: bool = True, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/leaders", params=params, result=None, user_id=requester.id)

    try:
        leaders = crud.user.index_leaders(db, requester=requester, user=id, offset=offset, limit=limit, include_friends=include_friends)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "count": len(leaders.entities), "total": leaders.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.UserRef]](data=leaders)


# noinspection PyShadowingNames
@router.get("/{id}/friends", response_model=Payload[schemas.EntityBatch[schemas.UserFriendRef]])
async def get_user_friends(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/friends", params=params, result=None, user_id=requester.id)

    try:
        friends = crud.user.index_friends(db, requester=requester, user=id, offset=offset, limit=limit)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "count": len(friends.entities), "total": friends.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.UserRef]](data=friends)


# noinspection PyShadowingNames
@router.get("/{follower_id}/follows/{leader_id}", response_model=Payload[schemas.Ok])
async def get_user_follows(follower_id: str, leader_id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                           cache: ResponseCache = cache.from_request()):
    params = {"follower_id": follower_id, "leader_id": leader_id}
    action = schemas.ApiActionCreate(method="get", route="/users/{follower_id}/follows/{leader_id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        ok = cache.data
    else:
        try:
            ok = crud.user.follows(db, requester=requester, follower=follower_id, leader=leader_id)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(ok, tag="user_follows_entity", ttl=60)

    action.result = {"code": 200, "ok": ok, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.put("/{id}/follow", response_model=Payload[schemas.Ok])
def follow_user(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="put", route="/users/{id}/follow", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.user.follow(db, requester=requester, entity=id)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.delete("/{id}/follow", response_model=Payload[schemas.Ok])
def unfollow_user(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="delete", route="/users/{id}/unfollow", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.user.unfollow(db, requester=requester, entity=id)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 402, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


# noinspection PyShadowingNames
@router.get("/{id}/spaces", response_model=Payload[schemas.EntityBatch[schemas.SpaceRef]])
async def get_user_spaces(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                          cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/spaces", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        spaces = cache.data
    else:
        try:
            spaces = crud.user.index_entities(db, requester=requester, user=id, model=models.Space, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(spaces, tag="user_spaces", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(spaces.entities), "total": spaces.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.SpaceRef]](data=spaces)


# noinspection PyShadowingNames
@router.get("/{id}/personas", response_model=Payload[schemas.EntityBatch[schemas.PersonaRef]])
async def get_user_personas(id: str, query: Optional[str] = '', offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                            cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/personas", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        personas = cache.data
    else:
        try:
            personas = crud.user.index_entities_with_query(db, requester=requester, user=id, model=models.Persona, offset=offset, limit=limit, query=query, fields=['type'])
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(personas, tag="user_spaces", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(personas.entities), "total": personas.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.PersonaRef]](data=personas)


# noinspection PyShadowingNames
@router.get("/personas/{id}", response_model=Payload[schemas.PersonaRef])
async def get_persona(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester), cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/personas/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        persona = cache.data
    else:
        try:
            persona = crud.persona.get(db, requester=requester, id=id)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(persona, tag="personas", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.PersonaRef](data=persona)


@router.post("/me/personas", response_model=Payload[schemas.PersonaRef])
def add_my_persona(create_data: schemas.PersonaUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": requester.id}
    action = schemas.ApiActionCreate(method="post", route="/me/personas/{id}", params=params, result=None, user_id=requester.id)

    try:
        comment = crud.user.create_persona(db, requester=requester, entity=requester, source=create_data)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "id": comment.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=comment)


@router.post("/me/personas/default", response_model=Payload[schemas.PersonaRef])
def add_my_persona(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": requester.id}
    action = schemas.ApiActionCreate(method="post", route="/me/personas/{id}", params=params, result=None, user_id=requester.id)

    try:
        comment = crud.user.set_default_persona(db, requester=requester, entity=requester, id=id)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "id": comment.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=comment)


@router.patch("/me/personas/{id}", response_model=Payload[schemas.PersonaRef])
def patch_my_persona(id: str, patch_data: schemas.PersonaUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="patch", route="/me/personas/{id}", params=params, result=None, user_id=requester.id)

    try:
        comment = crud.user.update_persona(db, requester=requester, entity=requester, id=id, patch=patch_data)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "id": comment.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=comment)


@router.delete("/me/personas/{id}", response_model=Payload[schemas.Ok])
def delete_my_persona(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="delete", route="/me/personas/{id}", params=params, result=None, user_id=requester.id)

    try:
        comment = crud.user.delete_persona(db, requester=requester, entity=requester, id=id)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=True))


# noinspection PyShadowingNames
@router.get("/{id}/objects", response_model=Payload[schemas.EntityBatch[schemas.ObjectRef]])
async def get_user_objects(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                           cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/spaces", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        objects = cache.data
    else:
        try:
            objects = crud.user.index_entities(db, requester=requester, user=id, model=models.Object, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(objects, tag="user_objects", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(objects.entities), "total": objects.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.ObjectRef]](data=objects)


# noinspection PyShadowingNames
@router.get("/{id}/collections", response_model=Payload[schemas.EntityBatch[schemas.CollectionRef]])
async def get_user_collections(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                               cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/collections", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        collections = cache.data
    else:
        try:
            collections = crud.user.index_entities(db, requester=requester, user=id, model=models.Collection, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(collections, tag="user_collections", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(collections.entities), "total": collections.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.CollectionRef]](data=collections)


# noinspection PyShadowingNames
@router.get("/{id}/mods", response_model=Payload[schemas.EntityBatch[schemas.ModRef]])
async def get_user_mods(id: str, offset: int = 0, limit: int = 10, query: str = '', sort: int = -1, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                        cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit, "query": query, "sort": sort}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/mods", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        mods = cache.data
    else:
        try:
            mods = crud.user.index_entities_with_query_sorted(db, requester=requester, user=id, model=models.Mod, offset=offset, limit=limit, query=query, sort=sort,
                                                              fields=['name', 'summary', 'description'])
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(mods, tag="user_mods", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(mods.entities), "total": mods.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.ModRef]](data=mods)


# noinspection PyShadowingNames
@router.get("/{id}/events", response_model=Payload[schemas.EntityBatch[schemas.EventRef]])
async def get_user_events(id: str, offset: int = 0, limit: int = 10, query: str = '', sort: int = -1, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                          cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit, "query": query, "sort": sort}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/events", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        events = cache.data
    else:
        try:
            events = crud.user.index_entities_with_query_sorted(db, requester=requester, user=id, model=models.Event, offset=offset, limit=limit, query=query, sort=sort,
                                                                fields=['name', 'summary', 'description'])
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(events, tag="user_events", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(events.entities), "total": events.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.EventRef]](data=events)


# noinspection PyShadowingNames
@router.get("/{id}/avatars", response_model=Payload[schemas.EntityBatch[schemas.AvatarRef]])
async def get_user_avatars(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                           cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/avatars", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        avatars = cache.data
    else:
        try:
            avatars = crud.user.index_avatars(db, requester=requester, user=id, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(avatars, tag="user_avatars", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(avatars.entities), "total": avatars.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.AvatarRef]](data=avatars)


# noinspection PyShadowingNames
@router.get("/{id}/avatar_meshes", response_model=Payload[schemas.EntityBatch[schemas.AvatarRef]])
async def get_user_avatar_meshes(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                                 cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/avatar_meshes", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        avatars = cache.data
    else:
        try:
            avatars = crud.user.index_avatar_meshes(db, requester=requester, user=id, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(avatars, tag="user_avatar_meshes", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(avatars.entities), "total": avatars.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.EntityBatch[schemas.AvatarRef]](data=avatars)


# noinspection PyShadowingNames
@router.get("/{id}/avatar_mesh", response_model=Payload[schemas.AvatarRef])
async def get_user_avatar_mesh(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                               cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/avatar_meshes", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        avatars = cache.data
    else:
        try:
            avatars = crud.user.index_avatar_meshes(db, requester=requester, user=id, offset=0, limit=1)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(avatars, tag="user_avatar_meshes", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    avatar: Optional[models.File]
    if len(avatars.entities) > 0:
        avatar = avatars.entities[0]
    else:
        avatar = None

    return Payload[schemas.AvatarRef](data=avatar)


# noinspection PyShadowingNames
@router.get("/{id}/online_game", response_model=Payload[schemas.OnlineGameRef])
async def get_user_online_game(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                               cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/online_game", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        online_game = cache.data
    else:
        try:
            online_game = crud.user.get_online_game(db, requester=requester, entity=id)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(online_game, tag="user_online_game", ttl=60)

    action.result = {"code": 200, "cached": cached, "id": online_game.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.OnlineGameRef](data=online_game)


# noinspection PyShadowingNames
@router.get("/{id}/last_seen", response_model=Payload[schemas.OnlinePlayerLastSeen])
async def get_user_last_seen(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                             cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/users/{id}/last_seen", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        user = cache.data
    else:
        try:
            user = crud.user.get_last_seen(db, requester=requester, entity=id)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(user, tag="user_last_seen", ttl=60)

    action.result = {"code": 200, "cached": cached, "last_seen_at": user.last_seen_at}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=user)


@router.patch("/{id}/mute", response_model=Payload[schemas.Ok])
def mute_user(id: str, mute: bool = True, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "mute": mute}
    action = schemas.ApiActionCreate(method="patch", route="/users/{id}/mute", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.user.toggle_state(db, requester=requester, entity=id, key="is_muted", value=mute)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.patch("/{id}/unmute", response_model=Payload[schemas.Ok])
def unmute_user(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="patch", route="/users/{id}/unmute", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.user.toggle_state(db, requester=requester, entity=id, key="is_muted", value=False)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.patch("/{id}/ban", response_model=Payload[schemas.Ok])
def ban_user(id: str, ban: bool = True, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "ban": ban}
    action = schemas.ApiActionCreate(method="patch", route="/users/{id}/ban", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.user.toggle_state(db, requester=requester, entity=id, key="is_banned", value=ban)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.patch("/{id}/unban", response_model=Payload[schemas.Ok])
def unban_user(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="patch", route="/users/{id}/unban", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.user.toggle_state(db, requester=requester, entity=id, key="is_banned", value=False)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.patch("/{id}/activate", response_model=Payload[schemas.Ok])
def activate_user(id: str, activate: bool = True, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "activate": activate}
    action = schemas.ApiActionCreate(method="patch", route="/users/{id}/activate", params=params, result=None, user_id=requester.id)
    try:
        ok = crud.user.toggle_state(db, requester=requester, entity=id, key="is_active", value=activate)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.patch("/{id}/deactivate", response_model=Payload[schemas.Ok])
def activate_user(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="patch", route="/users/{id}/deactivate", params=params, result=None, user_id=requester.id)
    try:
        ok = crud.user.toggle_state(db, requester=requester, entity=id, key="is_active", value=False)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.post("/action/client", response_model=Payload[schemas.Ok])
def report_client_action(action: schemas.ClientActionCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    try:
        ok = crud.user.report_client_action(db, requester=requester, action=action)
    except EntityParameterError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.post("/action/client/interaction", response_model=Payload[schemas.Ok])
def report_client_interaction(action: schemas.ClientInteractionCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    try:
        ok = crud.user.report_client_interaction(db, requester=requester, action=action)
    except EntityParameterError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.post("/feedback", response_model=Payload[schemas.FeedbackCreate], include_in_schema=True)
def create_feedback(feedback: schemas.FeedbackCreate, db: Session = Depends(database.session),
                    requester: models.User = Depends(auth.requester)):
    params = {"email": feedback.email, "text": feedback.text}

    action = schemas.ApiActionCreate(method="post", route="/users/feedback", params=params, result=None, user_id=requester.id)
    m_feedback = crud.feedback.create_by_user(db, source_object=feedback, requester=requester)

    action.result = {"code": 200}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=m_feedback)
