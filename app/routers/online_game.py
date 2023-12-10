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


@router.get("", response_model=Payload[EntityBatch[schemas.OnlineGameRef]])
async def index_online_games(build_id: str = "", query: str = "", offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                             cache: ResponseCache = cache.from_request()):
    params = {"build_id": build_id, "offset": offset, "limit": limit, "query": query}
    action = schemas.ApiActionCreate(method="get", route="/online_games", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        online_games = cache.data
    else:
        try:
            online_games = crud.online_game.index(db, requester=requester, query=query, build_id=build_id, offset=offset, limit=limit)
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
            await cache.set(online_games, tag="online_game_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(online_games.entities), "total": online_games.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[EntityBatch[schemas.OnlineGameRef]](data=online_games)


@router.get("/{space_id}", response_model=Payload[EntityBatch[schemas.OnlineGameRef]])
async def index_online_games_by_space(space_id: str, build_id: str = "1", offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                                      cache: ResponseCache = cache.from_request()):
    params = {"space_id": space_id, "build_id": build_id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/online_games/space_id", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        online_games = cache.data
    else:
        try:
            online_games = crud.online_game.index_by_foreign_key_value(db, requester=requester, build_id=build_id, key='space_id', value=space_id, offset=offset, limit=limit)
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
            await cache.set(online_games, tag="online_game_index_by_space", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(online_games.entities), "total": online_games.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[EntityBatch[schemas.OnlineGameRef]](data=online_games)


@router.get("/match/{space_id}", response_model=Payload[schemas.OnlineGameRef])
async def match_online_game(space_id: str, build_id: str = "1", db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                            cache: ResponseCache = cache.from_request()):
    params = {"space_id": space_id, "build_id": build_id}
    action = schemas.ApiActionCreate(method="get", route="/online_games/match/space_id", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        online_game = cache.data
    else:
        try:
            online_game: models.OnlineGame = crud.online_game.match(db, requester=requester, build_id=build_id, space_id=space_id)
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

        await cache.set(online_game, tag="online_game_match", ttl=60)

    action.result = {"code": 200, "cached": cached, "id": online_game.id if online_game else ""}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload[schemas.OnlineGameRef](data=online_game)


@router.post("/register", response_model=Payload[schemas.OnlineGameRef])
def register_online_game(create_data: schemas.OnlineGameCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {
        "build": create_data.build,
        "space_id": create_data.space_id,
        "map": create_data.map,
        "address": create_data.address,
        "port": create_data.address,
        "max_players": create_data.max_players,
        "public": create_data.public
    }
    action = schemas.ApiActionCreate(method="post", route="/online_games/register", params=params, result=None, user_id=requester.id)

    try:
        online_game = crud.online_game.register(db, create_data=create_data, requester=requester.id)
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

    action.result = {"code": 200, "id": online_game.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=online_game)


@router.post("/authenticate", response_model=Payload[dict])
def register_online_game(db=Depends(database.session), authenticated=Depends(auth.check_is_internal), requester=Depends(auth.requester)):
    action = schemas.ApiActionCreate(method="post", route="/online_games/authenticate", params=None, user_id=requester.id, result={"ok": True})
    crud.user.report_api_action(db, requester=requester, action=action)
    return Payload[dict](data={"success": authenticated})


@router.patch("/heartbeat/{online_game_id}", response_model=Payload[schemas.Ok])
def heartbeat_online_game(online_game_id: str, db: Session = Depends(database.session),
                          requester: models.User = Depends(auth.requester)):
    try:
        ok = crud.online_game.heartbeat(db, requester=requester, entity=online_game_id)
    except EntityParameterError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return Payload(data=schemas.Ok(ok=ok))


@router.post("/{online_game_id}/connect", response_model=Payload[schemas.Ok])
def connect_online_player(online_game_id: str, user_id: str, db: Session = Depends(database.session),
                          requester: models.User = Depends(auth.requester)):
    params = {"online_game_id": online_game_id, "user_id": user_id}
    action = schemas.ApiActionCreate(method="post", route="/online_games/id/connect", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.online_game.connect_online_player(db, requester=requester, online_game=online_game_id, user=user_id)
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


@router.delete("/{online_game_id}/disconnect", response_model=Payload[schemas.Ok])
def disconnect_online_player(online_game_id: str, user_id: str, db: Session = Depends(database.session),
                             requester: models.User = Depends(auth.requester)):
    params = {"online_game_id": online_game_id, "user_id": user_id}
    action = schemas.ApiActionCreate(method="post", route="/collections", params=params, result=None, user_id=requester.id)

    try:
        ok = crud.online_game.disconnect_online_player(db, requester=requester, online_game=online_game_id, user=user_id)
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
