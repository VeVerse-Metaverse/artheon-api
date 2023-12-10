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
@router.get("", response_model=Payload[schemas.EntityBatch[schemas.SpaceRef]])
async def index_spaces(query: Optional[str] = '', type: Optional[str] = None, offset: int = 0, limit: int = 10, db: Session = Depends(database.session),
                       requester: models.User = Depends(auth.requester), cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/spaces", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        spaces = cache.data
    else:
        try:
            spaces = crud.space.index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, type=type, options=joinedload(models.Space.owner))
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(spaces, tag="space_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(spaces.entities), "total": spaces.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=spaces)


@router.post("", response_model=Payload[schemas.SpaceRef])
def create_space(entity: schemas.SpaceCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"name": entity.name, "description": entity.description, "public": entity.public}
    action = schemas.ApiActionCreate(method="post", route="/spaces", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.space.create_for_requester(db, requester=requester, source=entity, unique_fields=["name"])
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
@router.get("/{id}", response_model=Payload[schemas.SpaceRef])
async def get_space(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                    cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/spaces/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        space = cache.data
    else:
        try:
            space = crud.space.get(db, requester=requester, id=id, options=joinedload(models.Space.owner))
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
            await cache.set(space, tag="space_get", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=space)


@router.patch("/{id}", response_model=Payload[schemas.SpaceRef])
def update_space(id: str, patch: schemas.SpaceUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "name": patch.name, "description": patch.description}
    action = schemas.ApiActionCreate(method="patch", route="/spaces/{id}", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.space.update(db, requester=requester, entity=id, patch=patch)
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

    return Payload[schemas.SpaceRef](data=entity)


# noinspection PyShadowingNames
@router.get("/{id}/placeables", response_model=Payload[schemas.EntityBatch[schemas.PlaceableRef]])
async def get_space_placeables(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                               cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/spaces/{id}/placeables", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        placeables = cache.data
    else:
        try:
            placeables = crud.space.index_placeables(db, requester=requester, space=id, offset=offset, limit=limit)
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
            await cache.set(placeables, tag="space_placeables", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(placeables.entities), "total": placeables.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=placeables)

# noinspection PyShadowingNames
@router.get("/{id}/portals", response_model=Payload[schemas.EntityBatch[schemas.PortalRef]])
async def get_space_portals(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                               cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/spaces/{id}/portals", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        portals = cache.data
    else:
        try:
            portals = crud.space.index_portals(db, requester=requester, space=id, offset=offset, limit=limit)
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
            await cache.set(portals, tag="space_portals", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(portals.entities), "total": portals.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=portals)


# noinspection PyShadowingNames
@router.get("/placeables/{id}", response_model=Payload[schemas.PlaceableRef])
async def get_placeable(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                        cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/spaces/placeables/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        placeable = cache.data
    else:
        try:
            placeable = crud.placeable.get(db, requester=requester, id=id)
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
            await cache.set(placeable, tag="placeable", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=placeable)


@router.put("/{id}/placeables", response_model=Payload[schemas.PlaceableRef])
def create_or_update_space_placeable(id: str, patch: schemas.PlaceableUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "entity_id": patch.entity_id}
    action = schemas.ApiActionCreate(method="put", route="/spaces/{id}/placeables", params=params, result=None, user_id=requester.id)

    try:
        placeable = crud.space.create_or_update_placeable(db, requester=requester, space=id, placeable_class=patch.placeable_class_id, patch=patch)
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

    action.result = {"code": 200, "id": placeable.id,
                     "p": {"x": placeable.p_x, "y": placeable.p_y, "z": placeable.p_z},
                     "r": {"x": placeable.r_x, "y": placeable.r_y, "z": placeable.r_z},
                     "s": {"x": placeable.s_x, "y": placeable.s_y, "z": placeable.s_z}}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=placeable)


@router.patch("/placeables/{id}/transform", response_model=Payload[schemas.PlaceableRef])
def update_placeable_transform(id: str, patch: schemas.PlaceableTransformUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="patch", route="/spaces/placeables/{id}/transform", params=params, result=None, user_id=requester.id)

    try:
        placeable = crud.space.update_placeable_transform(db, requester=requester, id=id, patch=patch)
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

    action.result = {"code": 200, "id": placeable.id,
                     "p": {"x": placeable.p_x, "y": placeable.p_y, "z": placeable.p_z},
                     "r": {"x": placeable.r_x, "y": placeable.r_y, "z": placeable.r_z},
                     "s": {"x": placeable.s_x, "y": placeable.s_y, "z": placeable.s_z}}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=placeable)


@router.patch("/placeables/{id}/entity/{entity_id}", response_model=Payload[schemas.PlaceableRef])
def update_placeable_entity(id: str, entity_id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="patch", route="/spaces/placeables/{id}/entity/{entity_id}", params=params, result=None, user_id=requester.id)

    try:
        placeable = crud.space.update_placeable_entity(db, requester=requester, id=id, entity_id=entity_id)
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

    action.result = {"code": 200, "id": placeable.id, "e_id": entity_id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=placeable)


@router.delete("/placeables/{placeable_id}", response_model=Payload[schemas.Ok])
def delete_space_placeable(placeable_id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"placeable_id": placeable_id}
    action = schemas.ApiActionCreate(method="delete", route="/spaces/{id}/placeables", params=params, result=None, user_id=requester.id)

    try:
        crud.space.delete_placeable(db, requester=requester, placeable=placeable_id)
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

    return Payload(data=schemas.Ok(ok=True))
