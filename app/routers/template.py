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
@router.get("", response_model=Payload[schemas.EntityBatch[schemas.TemplateRef]])
async def index_templates(query: Optional[str] = '', offset: int = 0, limit: int = 10, sort: int = -1, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                     cache: ResponseCache = cache.from_request()):
    params = {"query": query, "offset": offset, "limit": limit}
    action = schemas.ApiActionCreate(method="get", route="/templates", params=params, result=None, user_id=requester.id)
    cached: bool = False

    if settings.use_cache and cache.exists():
        cached = True
        templates = cache.data
    else:
        try:
            templates = crud.template.index_with_query_sorted(db, requester=requester, offset=offset, limit=limit, query=query, sort=sort, options=joinedload(models.Entity.owner))
        except EntityParameterError as e:
            action.result = {"code": 400, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            action.result = {"code": 403, "message": str(e)}
            crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        if settings.use_cache:
            await cache.set(templates, tag="template_index", ttl=60)

    action.result = {"code": 200, "cached": cached, "count": len(templates.entities), "total": templates.total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=templates)


@router.post("", response_model=Payload[schemas.TemplateRef])
def create_template(entity: schemas.TemplateCreate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"name": entity.name, "description": entity.description, "public": entity.public}
    action = schemas.ApiActionCreate(method="post", route="/templates", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.template.create_for_requester(db, requester=requester, source=entity, unique_fields=["name"])
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
@router.get("/{id}", response_model=Payload[schemas.TemplateRef])
async def get_template(id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester),
                  cache: ResponseCache = cache.from_request()):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="get", route="/templates/{id}", params=params, result=None, user_id=requester.id)
    cached = False

    if settings.use_cache and cache.exists():
        cached = True
        template = cache.data
    else:
        try:
            template = crud.template.get(db, requester=requester, id=id, options=joinedload(models.Entity.owner))
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
            await cache.set(template, tag="template_get", ttl=60)

    action.result = {"code": 200, "cached": cached}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=template)


@router.patch("/{id}", response_model=Payload[schemas.TemplateRef])
def update_template(id: str, patch: schemas.TemplateUpdate, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id, "name": patch.name, "description": patch.description}
    action = schemas.ApiActionCreate(method="patch", route="/templates/{id}", params=params, result=None, user_id=requester.id)

    try:
        entity = crud.template.update(db, requester=requester, entity=id, patch=patch)
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

    return Payload[schemas.TemplateRef](data=entity)
