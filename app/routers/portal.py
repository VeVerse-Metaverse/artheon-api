from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi_caching import ResponseCache
from sqlalchemy.orm import Session, joinedload
from starlette import status

from app import schemas, crud, models
from app.config import settings
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError
from app.dependencies import database, auth
from app.helpers import is_valid_uuid
from app.schemas.payload import Payload
from app.services import cache

router = APIRouter()


# noinspection PyShadowingNames
@router.get("", response_model=Payload[schemas.EntityBatch[schemas.PortalRef]])
async def index_portals(query: Optional[str] = '', offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                        cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/portals", params=params, result=None, user_id=requester.id)
    cached: bool = False

    if settings.use_cache and cache.exists():
        cached = True
        portals = cache.data
    else:
        try:
            portals = crud.portal.index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, options=joinedload(models.Portal.owner))
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(portals, tag="portal_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(portals.entities), "total": portals.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=portals)


@router.post("", response_model=Payload[schemas.PortalRef])
def create_portal(entity: schemas.PortalCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"name": entity.name, "public": entity.public}
    action = schemas.ApiActionCreate(method="post", route="/portals", params=params, result=None, user_id=requester.id)

    # Set default unused portal ID at start
    if not is_valid_uuid(entity.destination_id):
        entity.destination_id = '98b40f67-9003-4676-8ff4-819546c47bf3'

    try:
        entity = crud.portal.create_for_requester(db, requester=requester, source=entity)
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
@router.get("/{id}", response_model=Payload[schemas.PortalRef])
async def get_portal(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                     cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/portals/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        portal = cache.data
    else:
        try:
            portal = crud.portal.get(db, requester=requester, id=id, options=joinedload(models.Portal.owner))
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
            await cache.set(portal, tag="portal_get", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=portal)


# noinspection PyShadowingNames
@router.get("/{id}/simple", response_model=Payload[schemas.PortalSimple])
async def get_portal(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                     cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/portals/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        portal = cache.data
    else:
        try:
            portal = crud.portal.get(db, requester=requester, id=id, options=joinedload(models.Portal.owner))
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
            await cache.set(portal, tag="portal_get", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=portal)


@router.patch("/{id}", response_model=Payload[schemas.PortalRef])
def update_portal(id: str, patch: schemas.PortalUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "name": patch.name}
    action = schemas.ApiActionCreate(method="patch", route="/portals/{id}", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.portal.update(db, requester=requester, entity=id, patch=patch)
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

    return Payload[schemas.PortalRef](data=entity)
