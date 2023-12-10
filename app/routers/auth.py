import json

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from starlette import status
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_403_FORBIDDEN

from app import schemas, models, crud
from app.config import settings
from app.constants import COOKIE_NAME, COOKIE_DOMAIN
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError
from app.dependencies import database, auth
from app.schemas.wallet import Web3Sign
from app.schemas.payload import Payload

router = APIRouter()


@router.post("/login/web3", response_model=Payload[Web3Sign])
async def login_web3(address: str = Body(...),
                     signature: str = Body(...),
                     timestamp: int = Body(...),
                     db: Session = Depends(database.session)):
    params = {"address": address, "signature": signature, "timestamp": timestamp}
    requester = crud.user.get_internal_user(db)
    action = schemas.ApiActionCreate(method="post", route="/login/web3", params=params, result=None,
                                     user_id=requester.id)

    message = 'Greetings from Veverse! Sign this message to log into Veverse Dashboard. Timestamp: {timestamp}'.format(
        timestamp=timestamp)

    try:
        result = crud.user.verifySignedMsg(db, requester=requester, address=address, signature=signature,
                                           message=message)
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    return Payload(data={"code": 200, "verified": result["verified"], "user": result["user"]})


@router.post("/login", response_model=Payload[schemas.User])
async def login(response: Response,
                email: str = Body(...),
                password: str = Body(...),
                device_id: str = Body(None),
                db: Session = Depends(database.session)):
    params = {"email": email, "device_id": device_id, "password": not not password}
    params = {k: v for k, v in params.items() if (v is not None)}
    requester = crud.user.get_internal_user(db)
    action = schemas.ApiActionCreate(method="post", route="/login", params=params, result=None, user_id=requester.id)

    try:
        user: models.User = crud.user.authenticate(db, email=email, password=password, device_id=device_id)
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

    if user is None:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials")
    else:
        response.set_cookie(
            COOKIE_NAME,
            value=str(user.api_key),
            domain=COOKIE_DOMAIN,
            httponly=True,
            max_age=1800,
            expires=1800,
        )

        # Report user login action.
        params = {"email": email, "password": not not password, "device_id": not not device_id}
        result = {"code": 200}
        crud.user.report_api_action(db, requester=user,
                                    action=schemas.ApiActionCreate(user_id=user.id, version=settings.version,
                                                                   method="post", route="/login", params=params,
                                                                   body=None, result=result))

    return Payload[schemas.User](data=user)


@router.get("/logout")
async def logout(db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    response = RedirectResponse(url="")
    response.delete_cookie(COOKIE_NAME, domain=COOKIE_DOMAIN)

    # Report user logout action.
    result = {"code": 200}
    crud.user.report_api_action(db, requester=requester,
                                action=schemas.ApiActionCreate(user_id=requester.id, version=settings.version,
                                                               method="get", route="/logout", result=result))

    return response
