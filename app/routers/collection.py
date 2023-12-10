from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi_caching import ResponseCache
from sqlalchemy.orm import Session, joinedload, lazyload
from starlette import status

from app import schemas, crud, models
from app.config import settings
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError
from app.dependencies import database, auth
from app.schemas.payload import Payload
from app.services import cache

router = APIRouter()


# noinspection PyShadowingNames
@router.get("", response_model=Payload[schemas.EntityBatch[schemas.CollectionRef]])
async def index_collections(query: Optional[str] = '', offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                            cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/collections", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        collections = cache.data
    else:
        try:
            collections = crud.collection.index_with_query(db, requester=requester, offset=offset, limit=limit, query=query,
                                                           options=joinedload(models.Collection.owner))
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(collections, tag="collection_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(collections.entities), "total": collections.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=collections)


@router.post("", response_model=Payload[schemas.CollectionRef])
def create_collection(entity: schemas.CollectionCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"name": entity.name, "description": entity.description, "public": entity.public}
    action = schemas.ApiActionCreate(method="post", route="/collections", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.collection.create_for_requester(db, requester=requester, source=entity)
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
@router.get("/{id}", response_model=Payload[schemas.CollectionRef])
async def get_collection(id: str, db: Session = Depends(database.session), requester: models.Collection = Depends(auth.requester),
                         cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/collections/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        collection = cache.data
    else:
        try:
            collection = crud.collection.get(db, requester=requester, id=id, options=lazyload(models.Collection.owner))
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
            await cache.set(collection, tag="collection_get", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=collection)


@router.patch("/{id}", response_model=Payload[schemas.CollectionRef])
def update_collection(id: str, patch: schemas.CollectionUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "name": patch.name, "description": patch.description}
    action = schemas.ApiActionCreate(method="patch", route="/collections/{id}", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.collection.update(db, requester=requester, entity=id, patch=patch)
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


# noinspection PyShadowingNames
@router.get("/{id}/collectables", response_model=Payload[schemas.EntityBatch[schemas.CollectableRef]])
async def get_collection_collectables(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                                      cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/collections/{id}/collectables", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        collectables = cache.data
    else:
        try:
            collectables = crud.collection.index_collectables(db, requester=requester, entity=id, offset=offset, limit=limit)
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
            await cache.set(collectables, tag="collection_collectables", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(collectables.entities), "total": collectables.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=collectables)


@router.post("/{id}/collectables", response_model=Payload[schemas.Id])
def create_collection_collectable(id: str, patch: schemas.CollectableCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "object_id": patch.object_id}
    action = schemas.ApiActionCreate(method="post", route="/collections/{id}/collectables", params=params, result=None, user_id=requester.id)

    try:
        collectable = crud.collection.create_or_update_collectable(db, requester=requester, collection=id, patch=patch)
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

    action.result = {"code": 200, "id": collectable.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=collectable)


@router.delete("/{id}/collectables/{collectable_id}")
def delete_collection_collectable(id: str, collectable_id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "collectable_id": collectable_id}
    action = schemas.ApiActionCreate(method="delete", route="/collections/{id}/collectables", params=params, result=None, user_id=requester.id)

    try:
        crud.collection.delete_collectable(db, requester=requester, collection=id, collectable_id=collectable_id)
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
