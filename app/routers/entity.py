from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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


@router.get("/{id}", response_model=Payload[schemas.EntityRef])
def get_entity(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/entities/{id}", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.entity.get(db, requester=requester, id=id)
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


@router.delete("/{id}")
def delete_entity(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="delete", route="/entities/{id}", params=params, result=None, user_id=requester.id)

    try:
        crud.entity.delete(db, requester=requester, entity=id)
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


@router.post("/{id}/views", response_model=Payload[schemas.Views])
def view_entity(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="post", route="/entities/{id}/view", params=params, result=None, user_id=requester.id)

    try:
        views: int = crud.entity.increment_view_count(db, requester=requester, entity=id)
    except EntityParameterError as e:
        action.result = {"code": 400}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "views": views}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.Views(views=views))


@router.put("/{id}/access", response_model=Payload[schemas.Ok])
def update_entity_access(id: str, patch: schemas.AccessibleUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "user_id": patch.user_id, "can_view": patch.can_view, "can_edit": patch.can_edit, "can_delete": patch.can_delete}
    action = schemas.ApiActionCreate(method="put", route="/entities/{id}/access", params=params, result=None, user_id=requester.id)

    ok: bool = False
    try:
        ok = crud.entity.create_or_update_accessible(db, requester=requester, entity=id, patch=patch)
    except EntityParameterError as e:
        action.result = {"code": 400, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=ok)


# noinspection PyShadowingNames
@router.get("/{id}/properties", response_model=Payload[schemas.EntityBatch[schemas.PropertyRef]])
async def get_entity_properties(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                                cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/entities/{id}/properties", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        properties = cache.data
    else:
        try:
            properties = crud.entity.index_properties(db, requester=requester, entity=id, offset=offset, limit=limit)
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
            await cache.set(properties, tag="entity_properties", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(properties.entities), "total": properties.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=properties)


# noinspection PyShadowingBuiltins
@router.put("/{id}/properties", response_model=Payload[schemas.Ok])
def create_or_update_entity_property(id: str, property: schemas.PropertyCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "type": property.type, "name": property.name, "value": property.value}
    action = schemas.ApiActionCreate(method="put", route="/entities/{id}/properties", params=params, result=None, user_id=requester.id)

    ok: bool = False
    try:
        ok = crud.entity.create_or_update_property(db, requester=requester, entity=id, patch=property)
    except EntityParameterError as e:
        action.result = {"code": 400, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.Ok(ok=ok))


@router.delete("/{id}/properties/{name}")
def delete_entity_property(id: str, name: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "name": name}
    action = schemas.ApiActionCreate(method="delete", route="/entities/{id}/properties", params=params, result=None, user_id=requester.id)

    try:
        crud.entity.delete_property(db, requester=requester, entity=id, name=name)
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


# noinspection PyShadowingNames
@router.get("/{id}/tags", response_model=Payload[EntityBatch[schemas.TagRef]])
async def get_entity_tags(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/entities/{id}/tags", params=params, result=None, user_id=requester.id)

    try:
        tags = crud.entity.index_tags(db, requester=requester, entity=id, offset=offset, limit=limit)
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

    action.result = {"code": 200, "count": len(tags.entities), "total": tags.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=tags)


# noinspection PyShadowingBuiltins
@router.put("/{id}/tags", response_model=Payload[schemas.Ok])
def update_entity_tags(id: str, tags: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "tags": tags.split(',')}
    action = schemas.ApiActionCreate(method="put", route="/entities/{id}/tags", params=params, result=None, user_id=requester.id)

    ok: bool = False
    try:
        ok = crud.entity.update_tags(db, requester=requester, entity=id, tags=tags)
    except EntityParameterError as e:
        action.result = {"code": 400, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.Ok(ok=ok))


# noinspection PyShadowingBuiltins
@router.delete("/{id}/tag", response_model=Payload[schemas.Ok])
def delete_entity_tag(id: str, tag: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "tag": tag}
    action = schemas.ApiActionCreate(method="delete", route="/entities/{id}/tag", params=params, result=None, user_id=requester.id)

    ok: bool = False
    try:
        ok = crud.entity.delete_tag(db, requester=requester, entity=id, tag=tag)
    except EntityParameterError as e:
        action.result = {"code": 400, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404, "ok": ok}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "ok": ok}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.Ok(ok=ok))


# noinspection PyShadowingNames
@router.get("/{id}/comments", response_model=Payload[schemas.EntityBatch[schemas.CommentRef]])
async def get_entity_comments(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                              cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/entities/{id}/comments", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        comments = cache.data
    else:
        try:
            comments = crud.entity.index_comments(db, requester=requester, entity=id, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(comments, tag="entity_comments", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(comments.entities), "total": comments.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=comments)


@router.post("/{id}/comments", response_model=Payload[schemas.CommentRef])
def comment_entity(id: str, create_data: schemas.CommentCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "text": create_data.text}
    action = schemas.ApiActionCreate(method="post", route="/entities/{id}/comments", params=params, result=None, user_id=requester.id)

    try:
        comment = crud.entity.create_comment(db, requester=requester, entity=id, source=create_data)
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

    action.result = {"code": 200, "id": comment.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=comment)


@router.delete("/{id}/comments/{comment_id}")
def delete_entity_comment(id: str, comment_id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "comment_id": comment_id}
    action = schemas.ApiActionCreate(method="delete", route="/entities/{id}/comments/comment_id", params=params, result=None, user_id=requester.id)

    try:
        crud.entity.delete_comment(db, requester=requester, entity=id, comment=comment_id)
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


# noinspection PyShadowingNames
@router.get("/{id}/likes", response_model=Payload[schemas.EntityBatchLiked[schemas.LikeRef]])
async def get_entity_likes(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                           cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/entities/{id}/likes", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        likes = cache.data
    else:
        try:
            likes = crud.entity.index_likes(db, requester=requester, entity=id, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(likes, tag="entity_likes", ttl=60)

    liked = crud.entity.get_liked_by_requester(db, requester=requester, entity=id)
    likes.liked = liked

    action.result = {"code": 200, "cached": cached, "count": len(likes.entities), "total": likes.total, "liked": liked}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=likes)


@router.put("/{id}/likes", response_model=Payload[schemas.EntityTotal])
def like_entity(id: str, rating: int = 1, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "rating": rating}
    action = schemas.ApiActionCreate(method="put", route="/entities/{id}/like", params=params, result=None, user_id=requester.id)

    try:
        likable = crud.entity.create_or_update_likable(db, requester=requester, entity=id, rating=rating)
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

    try:
        likes = crud.entity.get_likes(db, requester=requester, entity=id)
    except EntityParameterError as e:
        action.result = {"code": 400}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "id": likable.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.EntityTotal(total=likes.total))


@router.put("/{id}/unlike", response_model=Payload[schemas.Ok])
def unlike_entity(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="put", route="/entities/{id}/unlike", params=params, result=None, user_id=requester.id)

    try:
        likable = crud.entity.create_or_update_likable(db, requester=requester, entity=id, rating=0)
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

    action.result = {"code": 200, "id": likable.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.Ok(ok=not not likable))


# noinspection PyShadowingNames
@router.get("/{id}/dislikes", response_model=Payload[schemas.EntityTotalDisliked])
async def get_entity_dislikes(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                              cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/entities/{id}/dislikes", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        dislikes = cache.data
    else:
        try:
            dislikes = crud.entity.get_dislikes(db, requester=requester, entity=id)
        except EntityParameterError as e:
            action.result = {"code": 400, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(dislikes, tag="entity_dislikes", ttl=60)

    disliked = crud.entity.get_disliked_by_requester(db, requester=requester, entity=id)
    dislikes.disliked = disliked

    action.result = {"code": 200, "cached": cached, "total": dislikes.total, "disliked": disliked}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=dislikes)


@router.put("/{id}/dislikes", response_model=Payload[schemas.EntityTotal])
def dislike_entity(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="put", route="/entities/{id}/dislike", params=params, result=None, user_id=requester.id)

    try:
        likable = crud.entity.create_or_update_likable(db, requester=requester, entity=id, rating=-1)
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

    try:
        dislikes = crud.entity.get_likes(db, requester=requester, entity=id)
    except EntityParameterError as e:
        action.result = {"code": 400}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityAccessError as e:
        action.result = {"code": 403}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityNotFoundError as e:
        action.result = {"code": 404}
        crud.user.report_api_action(db, requester=requester, action=action)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    action.result = {"code": 200, "id": likable.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.EntityTotal(total=dislikes.total))


# noinspection PyShadowingNames
@router.get("/{id}/files", response_model=Payload[schemas.EntityBatch[schemas.FileRef]])
async def get_entity_files(id: str, offset: int = 0, limit: int = 10, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                           cache: ResponseCache = cache.from_request()):
    params = {"id": id, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/entities/{id}/files", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        files = cache.data
    else:
        try:
            files = crud.entity.index_files(db, requester=requester, entity=id, offset=offset, limit=limit)
        except EntityParameterError as e:
            action.result = {"code": 400, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            action.result = {"code": 404, "cached": cached}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

        if settings.use_cache:
            await cache.set(files, tag="entity_files", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(files.entities), "total": files.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=files)


@router.post("/{id}/files/{type}", response_model=Payload[schemas.FileRef])
async def add_entity_file_link(id: str, type: str, file: str, mime: str = "binary/octet-stream", size: int = 0, platform: Optional[str] = None, version: Optional[int] = None,
                               deployment_type: Optional[str] = None, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "type": type, "name": file}
    action = schemas.ApiActionCreate(method="post", route="/entities/{id}/files", params=params, result=None, user_id=requester.id)

    try:
        file =  crud.entity.add_file(db, requester=requester, entity=id, filename=file, type=type, mime=mime, size=size, platform=platform, version=version, deployment_type=deployment_type)
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

    action.result = {"code": 200, "id": file.id, "url": file.url, "size": file.size, "mime": file.mime}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=file)


@router.patch("/{id}/files/{type}", response_model=Payload[schemas.FileRef])
async def replace_entity_file_link(id: str, type: str, file: str, mime: str = "binary/octet-stream", size: int = 0, platform: Optional[str] = None, version: Optional[int] = None,
                                   deployment_type: Optional[str] = None, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "type": type, "name": file}
    action = schemas.ApiActionCreate(method="patch", route="/entities/{id}/files", params=params, result=None, user_id=requester.id)

    try:
        file = await crud.entity.replace_file(db, requester=requester, entity=id, filename=file, type=type, mime=mime, size=size, platform=platform, version=version, deployment_type=deployment_type)
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

    action.result = {"code": 200, "id": file.id, "url": file.url, "size": file.size, "mime": file.mime}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=file)


@router.put("/{id}/files/{type}", response_model=Payload[schemas.FileRef])
async def upload_entity_file(id: str, type: str, platform: Optional[str] = None, version: Optional[int] = None, file: UploadFile = File(...),
                             deployment_type: Optional[str] = None, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "type": type, "platform": platform, "version": version, "name": file.filename}
    action = schemas.ApiActionCreate(method="put", route="/entities/{id}/files", params=params, result=None, user_id=requester.id)

    try:
        file = await crud.entity.upload_file(db, requester=requester, entity=id, upload=file, type=type, platform=platform, version=version, deployment_type=deployment_type)
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

    action.result = {"code": 200, "id": file.id, "url": file.url, "size": file.size, "mime": file.mime}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=file)


@router.delete("/{id}/files/{file_id}")
async def delete_entity_file(id: str, file_id: str,
                             db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "file_id": file_id}
    action = schemas.ApiActionCreate(method="delete", route="/entities/{id}/files", params=params, result=None, user_id=requester.id)

    try:
        await crud.entity.delete_file_by_id(db, requester=requester, entity=id, id=file_id)
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
