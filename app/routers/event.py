import logging
import os
import uuid
from typing import Optional

import stripe as stripe
from fastapi import APIRouter, Depends, HTTPException, Header, Body, Request
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


# This is your Stripe CLI webhook secret for testing your endpoint locally.
# local_test_endpoint_secret = ''


# noinspection PyShadowingNames
@router.get("", response_model=Payload[schemas.EntityBatch[schemas.EventRef]])
async def index_events(query: Optional[str] = '', offset: int = 0, limit: int = 10, sort: int = -1, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                       cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/events", params=params, result=None, user_id=requester.id)
    cached: bool = False

    if settings.use_cache and cache.exists():
        cached = True
        events = cache.data
    else:
        try:
            events = crud.event.index_with_query_sorted(db, requester=requester, offset=offset, limit=limit, query=query, sort=sort, options=joinedload(models.Event.owner))
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(events, tag="event_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(events.entities), "total": events.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=events)


@router.post("", response_model=Payload[schemas.EventRef])
def create_event(entity: schemas.EventCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"name": entity.name, "description": entity.description, "public": entity.public}
    action = schemas.ApiActionCreate(method="post", route="/events", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.event.create_for_requester(db, requester=requester, source=entity, unique_fields=["name"])
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
@router.get("/{id}", response_model=Payload[schemas.EventRef])
async def get_event(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                    cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/events/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        event = cache.data
    else:
        try:
            event = crud.event.get(db, requester=requester, id=id, options=joinedload(models.Event.owner))
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
            await cache.set(event, tag="event_get", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=event)


@router.patch("/{id}", response_model=Payload[schemas.EventRef])
def update_event(id: str, patch: schemas.EventUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "name": patch.name, "description": patch.description}
    action = schemas.ApiActionCreate(method="patch", route="/events/{id}", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.event.update(db, requester=requester, entity=id, patch=patch, unique_fields=["name"])
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

    return Payload[schemas.EventRef](data=entity)

