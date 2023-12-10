from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi_caching import ResponseCache
from sqlalchemy.orm import Session, joinedload
from starlette import status

from app import schemas, crud, models
from app.config import settings
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError, EntityBatch
from app.dependencies import database, auth
from app.schemas.payload import Payload
from app.services import cache

router = APIRouter()


# noinspection PyShadowingNames
@router.get("", response_model=Payload[schemas.EntityBatch[schemas.ModRef]])
async def index_mods(query: Optional[str] = '', offset: int = 0, limit: int = 10, sort: int = -1, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                     cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/mods", params=params, result=None, user_id=requester.id)
    cached: bool = False

    if settings.use_cache and cache.exists():
        cached = True
        mods = cache.data
    else:
        try:
            mods = crud.mod.index_with_query_sorted(db, requester=requester, offset=offset, limit=limit, query=query, sort=sort, options=joinedload(models.Mod.owner))
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(mods, tag="mod_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(mods.entities), "total": mods.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=mods)


@router.post("", response_model=Payload[schemas.ModRef])
def create_mod(entity: schemas.ModCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"name": entity.name, "description": entity.description, "public": entity.public}
    action = schemas.ApiActionCreate(method="post", route="/mods", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.mod.create_for_requester(db, requester=requester, source=entity, unique_fields=["name"])
    except EntityParameterError as e:
        action.result = {"code": 400, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "message": str(e)}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    action.result = {"code": 200, "id": entity.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=entity)


# noinspection PyShadowingNames
@router.get("/{id}", response_model=Payload[schemas.ModRef])
async def get_mod(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                  cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/mods/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        mod = cache.data
    else:
        try:
            mod = crud.mod.get(db, requester=requester, id=id, options=joinedload(models.Mod.owner))
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
            await cache.set(mod, tag="mod_get", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=mod)


@router.patch("/{id}", response_model=Payload[schemas.ModRef])
def update_mod(id: str, patch: schemas.ModUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "name": patch.name, "description": patch.description}
    action = schemas.ApiActionCreate(method="patch", route="/mods/{id}", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.mod.update(db, requester=requester, entity=id, patch=patch, unique_fields=[])
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

    return Payload[schemas.ModRef](data=entity)


# noinspection PyShadowingNames
@router.get("/{id}/spaces", response_model=Payload[schemas.EntityBatch[schemas.SpaceRef]])
async def get_mod_spaces(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                            cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/mods/{id}/spaces", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        spaces = cache.data
    else:
        try:
            spaces = crud.mod.index_spaces(db, requester=requester, mod=id, offset=offset, limit=limit)
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
            await cache.set(spaces, tag="mod_spaces", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(spaces.entities), "total": spaces.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=spaces)
