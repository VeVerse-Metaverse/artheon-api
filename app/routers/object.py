from typing import Optional, Any

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
@router.get("", response_model=Payload[schemas.EntityBatch[schemas.ObjectRef]])
async def index_objects(query: Optional[str] = '', offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                        cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/objects", params=params, result=None, user_id=requester.id)
    cached: bool = False

    if settings.use_cache and cache.exists():
        cached = True
        objects = cache.data
    else:
        try:
            objects = crud.object.index_with_query(db, requester=requester, offset=offset, limit=limit, query=query, options=joinedload(models.Object.owner))
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(objects, tag="object_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(objects.entities), "total": objects.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=objects)


@router.post("", response_model=Payload[schemas.ObjectRef])
def create_object(entity: schemas.ObjectCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"name": entity.name,
              "description": entity.description,
              "type": entity.type,
              "artist": entity.artist,
              "date": entity.date,
              "medium": entity.medium,
              "width": entity.width,
              "height": entity.height,
              "source": entity.source,
              "license": entity.license,
              "credit": entity.credit,
              "location": entity.location,
              "origin": entity.origin,
              "public": entity.public}
    params = {k: v for k, v in params.items() if (v is not None)}
    action = schemas.ApiActionCreate(method="post", route="/objects", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.object.create_for_requester(db, requester=requester, source=entity)
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
@router.get("/types", response_model=Payload[schemas.EntityBatch[Any]], description="List available object types to use with search.")
async def get_types(query: str = None, offset: int = 0, limit: int = 10, requester: models.User = Depends(auth.requester), db: Session = Depends(database.session),
                    cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/objects/types", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        types = cache.data
    else:
        try:
            types = crud.object.index_types(db, query=query, requester=requester, offset=offset, limit=limit)
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
            await cache.set(types, tag="object_types", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(types.entities), "total": types.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=types)


# noinspection PyShadowingNames
@router.get("/museums", response_model=Payload[schemas.EntityBatch[Any]], description="List available object museums to use with search.")
async def get_museums(query: str = None, offset: int = 0, limit: int = 10, requester: models.User = Depends(auth.requester), db: Session = Depends(database.session),
                      cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/objects/museums", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        museums = cache.data
    else:
        try:
            museums = crud.object.index_museums(db, query=query, requester=requester, offset=offset, limit=limit)
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
            await cache.set(museums, tag="object_museums", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(museums.entities), "total": museums.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=museums)


# noinspection PyShadowingNames
@router.get("/artists", response_model=Payload[schemas.EntityBatch[Any]], description="List available object artists to use with search.")
async def get_artists(query: str = None, offset: int = 0, limit: int = 10, requester: models.User = Depends(auth.requester), db: Session = Depends(database.session),
                      cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/objects/artists", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        artists = cache.data
    else:
        try:
            artists = crud.object.index_artists(db, query=query, requester=requester, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(artists, tag="object_artists", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(artists.entities), "total": artists.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=artists)


# noinspection PyShadowingNames
@router.get("/media", response_model=Payload[schemas.EntityBatch[Any]],
            description="List available object media to use with search. Requester can use query for type ahead functionality. The query must include not less than three characters.")
async def get_media(query: str = None, offset: int = 0, limit: int = 10, requester: models.User = Depends(auth.requester), db: Session = Depends(database.session),
                    cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/objects/media", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        media = cache.data
    else:
        try:
            media = crud.object.index_media(db, query=query, requester=requester, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 404, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(media, tag="object_media")

    action.result = {"code": 200, "cached": cached, "count": len(media.entities), "total": media.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=media, ttl=60)


# noinspection PyShadowingNames
@router.get("/search", response_model=Payload[schemas.EntityBatch[schemas.ObjectRef]])
async def search_objects(name: Optional[str] = None, description: Optional[str] = None,
                         artist: Optional[str] = None, type: Optional[str] = None,
                         medium: Optional[str] = None, museum: Optional[str] = None,
                         year_min: Optional[int] = None, year_max: Optional[int] = None,
                         width_min: Optional[float] = None, width_max: Optional[float] = None,
                         height_min: Optional[float] = None, height_max: Optional[float] = None,
                         views_min: Optional[int] = None, views_max: Optional[int] = None,
                         offset: int = 0, limit: int = 10,
                         db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                         cache: ResponseCache = cache.from_request()):
    params = {"name": name,
              "description": description,
              "artist": artist,
              "type": type,
              "medium": medium,
              "museum": museum,
              "year_min": year_min, "year_max": year_max,
              "width_min": width_min, "width_max": width_max,
              "height_min": height_min, "height_max": height_max,
              "views_min": views_min, "views_max": views_max,
              "offset": offset, "limit": limit}
    params = {k: v for k, v in params.items() if (v is not None)}
    action = schemas.ApiActionCreate(method="get", route="/objects/search", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        objects = cache.data
    else:
        try:
            objects = crud.object.index_search(db, requester=requester, name=name, description=description, artist=artist, type=type, medium=medium, museum=museum,
                                               year_min=year_min, year_max=year_max,
                                               width_min=width_min, width_max=width_max,
                                               height_min=height_min, height_max=height_max,
                                               views_min=views_min, views_max=views_max,
                                               offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(objects, tag="object_search", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(objects.entities), "total": objects.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=objects)


# noinspection PyShadowingNames,PyShadowingBuiltins
@router.get("/{id}", response_model=Payload[schemas.ObjectRef])
async def get_object(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                     cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/objects/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        object = cache.data
    else:
        try:
            object = crud.object.get(db, requester=requester, id=id, options=joinedload(models.Object.owner))
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
            await cache.set(object, tag="object_get", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=object)


@router.patch("/{id}", response_model=Payload[schemas.ObjectRef])
def update_object(id: str, patch: schemas.ObjectUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id,
              "name": patch.name,
              "description": patch.description,
              "type": patch.type,
              "artist": patch.artist,
              "date": patch.date,
              "medium": patch.medium,
              "width": patch.width,
              "height": patch.height,
              "source": patch.source,
              "license": patch.license,
              "credit": patch.credit,
              "location": patch.location,
              "origin": patch.origin}
    params = {k: v for k, v in params.items() if (v is not None)}
    action = schemas.ApiActionCreate(method="patch", route="/objects/{id}", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.object.update(db, requester=requester, entity=id, patch=patch)
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
@router.get("/{id}/similar", response_model=Payload[schemas.EntityBatch[schemas.ObjectRef]])
async def read_similar_objects(id: str, offset: int = 0, limit: int = 10, requester: models.User = Depends(auth.requester), db: Session = Depends(database.session),
                               cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/objects/{id}/similar", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        objects = cache.data
    else:
        try:
            objects = crud.object.index_similar(db, requester=requester, id=id, offset=offset, limit=limit, options=joinedload(models.Object.owner))
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
            await cache.set(objects, tag="object_similar", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=objects)
