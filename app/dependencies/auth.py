import logging

from fastapi import Security, Depends, HTTPException
from fastapi.security import APIKeyQuery, APIKeyHeader, APIKeyCookie
from sqlalchemy.orm import Session, Query, noload
from starlette.status import HTTP_403_FORBIDDEN

from app import models
from app.constants import COOKIE_NAME
from app.dependencies import database

api_key_query = APIKeyQuery(name=COOKIE_NAME, auto_error=False)
api_key_header = APIKeyHeader(name=COOKIE_NAME, auto_error=False)
api_key_cookie = APIKeyCookie(name=COOKIE_NAME, auto_error=False)


# Dependency
async def check(query_api_key: str = Security(api_key_query),
                header_api_key: str = Security(api_key_header),
                cookie_api_key: str = Security(api_key_cookie),
                db: Session = Depends(database.session)) -> bool:
    if query_api_key is not None:
        api_key = query_api_key
    elif header_api_key is not None:
        api_key = header_api_key
    elif cookie_api_key is not None:
        api_key = cookie_api_key
    else:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="failed to authenticate: no credentials provided")

    r: models.User = db.query(models.User).filter(models.User.api_key == api_key).first()
    if r is None or not r.id:
        logging.log(logging.ERROR, f"failed to authenticate: user not found")
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="failed to authenticate: user not found")

    logging.log(logging.INFO, f"auth check: {r.id}:{r.name}")

    return True


# Dependency
async def check_is_internal(query_api_key: str = Security(api_key_query),
                            header_api_key: str = Security(api_key_header),
                            cookie_api_key: str = Security(api_key_cookie),
                            db: Session = Depends(database.session)) -> bool:
    if query_api_key is not None:
        api_key = query_api_key
    elif header_api_key is not None:
        api_key = header_api_key
    elif cookie_api_key is not None:
        api_key = cookie_api_key
    else:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="failed to authenticate: no credentials provided")

    r: models.User = db.query(models.User).filter(models.User.api_key == api_key).first()
    if r is None or not r.id:
        logging.log(logging.ERROR, f"failed to authenticate: user not found")
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="failed to authenticate: user not found")

    logging.log(logging.INFO, f"auth check: {r.id}:{r.name}")

    return r.is_internal


# Dependency
async def requester(query_api_key: str = Security(api_key_query),
                    header_api_key: str = Security(api_key_header),
                    cookie_api_key: str = Security(api_key_cookie),
                    db: Session = Depends(database.session)) -> models.User:
    if query_api_key is not None:
        api_key = query_api_key
    elif header_api_key is not None:
        api_key = header_api_key
    elif cookie_api_key is not None:
        api_key = cookie_api_key
    else:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="not authenticated")

    q: Query = db.query(models.User)

    user: models.User = q.filter(
        models.User.api_key == api_key
    ).first()

    if user is None or not user.id:
        logging.log(logging.ERROR, f"failed to authenticate: user not found")
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="user not found")

    # if not user.is_active:
    #     raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="inactive")

    if user.is_banned:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="banned")

    # logging.log(logging.INFO, f"auth requester: {user.id}:{user.name}")

    return user
