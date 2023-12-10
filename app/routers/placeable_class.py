from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi_caching import ResponseCache
from sqlalchemy.orm import Session, joinedload
from starlette import status

from app import schemas, crud, models
from app.config import settings
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError
from app.dependencies import database, auth
from app.schemas.payload import Payload
from app.services import cache

router = APIRouter()


# noinspection PyShadowingNames
@router.get("", response_model=Payload[schemas.EntityBatch[schemas.PlaceableClass]])
async def index_placeable_classes(query: Optional[str] = '', offset: int = 0, limit: int = 10, category: Optional[str] = '', db: Session = Depends(database.session),
                       requester: models.User = Depends(auth.requester), cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/placeable_classes", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        placeable_classes = cache.data
    else:
        try:
            placeable_classes = crud.placeable_class.index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, category=category, options=None)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(placeable_classes, tag="placeable_class_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(placeable_classes.entities), "total": placeable_classes.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=placeable_classes)


# noinspection PyShadowingNames
@router.get("/categories", response_model=Payload[schemas.EntityBatch[str]])
async def index_placeable_class_catetories(query: Optional[str] = '', offset: int = 0, limit: int = 10, db: Session = Depends(database.session),
                       requester: models.User = Depends(auth.requester), cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/placeable_class_categories", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        placeable_classes = cache.data
    else:
        try:
            placeable_class_categories = crud.placeable_class.index_categories_with_query(db, requester=requester, offset=offset, limit=limit, query=query, options=None)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(placeable_class_categories, tag="placeable_class_category_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(placeable_class_categories.entities), "total": placeable_class_categories.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=placeable_class_categories)

