import starlette
from fastapi import APIRouter, Depends, HTTPException
from fastapi_caching import ResponseCache
from sqlalchemy.orm import Session
from starlette import status

from app import schemas, crud, models
from app.config import settings
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError
from app.dependencies import database, auth
from app.schemas import EntityBatch
from app.schemas.payload import Payload
from app.services import cache

router = APIRouter()


@router.get("", response_model=Payload[EntityBatch[schemas.ServerRef]])
async def index_servers(build_id: str = "", query: str = "", offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                        cache: ResponseCache = cache.from_request()):
    params = {"build_id": build_id, "offset": offset, "limit": limit, "query": query}
    action = schemas.ApiActionCreate(method="get", route="/servers", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        servers = cache.data
    else:
        try:
            servers = crud.server.index(db, requester=requester, query=query, build_id=build_id, offset=offset, limit=limit)
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
            await cache.set(servers, tag="server_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(servers.entities), "total": servers.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[EntityBatch[schemas.ServerRef]](data=servers)


@router.get("/scheduled", response_model=Payload[schemas.SpaceRef])
def get_scheduled_server(platform: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    action = schemas.ApiActionCreate(method="post", route="/servers/scheduled", params={}, result=None, user_id=requester.id)

    try:
        space = crud.server.get_scheduled(db, platform=platform, requester=requester)
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

    action.result = {"code": 200, "id": space.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=space)


@router.get("/space/{space_id}", response_model=Payload[EntityBatch[schemas.ServerRef]])
async def index_servers_by_space(space_id: str, build_id: str = "1", offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                                 cache: ResponseCache = cache.from_request()):
    params = {"space_id": space_id, "build_id": build_id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/servers/space_id", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        servers = cache.data
    else:
        try:
            servers = crud.server.index_by_foreign_key_value(db, requester=requester, build_id=build_id, key='space_id', value=space_id, offset=offset, limit=limit)
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
            await cache.set(servers, tag="server_index_by_space", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(servers.entities), "total": servers.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[EntityBatch[schemas.ServerRef]](data=servers)


@router.get("/{server_id}", response_model=Payload[schemas.ServerRef])
async def get_server(server_id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                     cache: ResponseCache = cache.from_request()):
    params = {"server_id": server_id}
    action = schemas.ApiActionCreate(method="get", route="/servers/server_id", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        server = cache.data
    else:
        try:
            server = crud.server.get(db, requester=requester, id=server_id)
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
            await cache.set(server, tag="server_get", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.ServerRef](data=server)


@router.get("/match/{space_id}", response_model=Payload[schemas.ServerRef])
async def match_server(space_id: str, build_id: str = "", hostname: str = "", db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                       cache: ResponseCache = cache.from_request()):
    params = {"space_id": space_id, "build_id": build_id}
    action = schemas.ApiActionCreate(method="get", route="/servers/match/space_id", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        server = cache.data
    else:
        try:
            server: models.Server = crud.server.match(db, requester=requester, space_id=space_id, hostname=hostname, build=build_id)
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

        await cache.set(server, tag="server_match", ttl=60)

    action.result = {"code": 200, "cached": cached, "id": server.id if server else ""}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.ServerRef](data=server)


@router.post("", response_model=Payload[schemas.ServerRef])
def register_server(create_data: schemas.ServerCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {
        "space_id": create_data.space_id,
        "address": create_data.host,
        "port": create_data.port,
        "max_players": create_data.max_players,
        "public": create_data.public,
        "map": create_data.map,
    }
    action = schemas.ApiActionCreate(method="post", route="/servers/register", params=params, result=None, user_id=requester.id)

    try:
        server = crud.server.register(db, create_data=create_data, requester=requester.id)
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

    action.result = {"code": 200, "id": server.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=server)


@router.patch("/{id}", response_model=Payload[schemas.ServerRef])
def update_server(id: str, patch: schemas.ServerUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="patch", route="/servers/{id}", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.server.update(db, requester=requester, entity=id, patch=patch)
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


@router.delete("/{id}", response_model=Payload[schemas.Ok])
def unregister_server(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="patch", route="/servers/{id}", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.server.delete(db, requester=requester, entity=id)
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

    return Payload[schemas.Ok](data=schemas.Ok(ok=ok))


@router.post("/authenticate", response_model=Payload[dict])
def register_server(db=Depends(database.session), authenticated=Depends(auth.check_is_internal), requester=Depends(auth.requester)):
    action = schemas.ApiActionCreate(method="post", route="/servers/authenticate", params=None, user_id=requester.id, result={"ok": True})
    crud.user.report_api_action(db, requester=requester, action=action)
    return Payload[dict](data={"success": authenticated})


@router.patch("/heartbeat/{server_id}", response_model=Payload[schemas.Ok])
def heartbeat_server(server_id: str, status: str = "online", details: str = None, db: Session = Depends(database.session),
                     requester: models.User = Depends(auth.requester)):
    try:
        ok = crud.server.heartbeat(db, requester=requester, entity=server_id, status=status, details=details)
    except EntityParameterError as e:
        raise HTTPException(status_code=starlette.status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        raise HTTPException(status_code=starlette.status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        raise HTTPException(status_code=starlette.status.HTTP_404_NOT_FOUND, detail=str(e))

    return Payload(data=schemas.Ok(ok=ok))


@router.post("/{server_id}/connect", response_model=Payload[schemas.Ok])
def connect_online_player(server_id: str, user_id: str, db: Session = Depends(database.session),
                          requester: models.User = Depends(auth.requester)):
    params = {"server_id": server_id, "user_id": user_id}
    action = schemas.ApiActionCreate(method="post", route="/servers/id/connect", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.server.connect_online_player(db, requester=requester, server=server_id, user=user_id)
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


@router.delete("/{server_id}/disconnect", response_model=Payload[schemas.Ok])
def disconnect_online_player(server_id: str, user_id: str, db: Session = Depends(database.session),
                             requester: models.User = Depends(auth.requester)):
    params = {"server_id": server_id, "user_id": user_id}
    action = schemas.ApiActionCreate(method="post", route="/collections", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.server.disconnect_online_player(db, requester=requester, server=server_id, user=user_id)
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
