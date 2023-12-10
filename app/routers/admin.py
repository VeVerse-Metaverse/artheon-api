from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import HTMLResponse

from app import crud, models, schemas
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError
from app.dependencies import database, auth
from app.schemas.payload import Payload
from app.services import k8s

router = APIRouter()


# Admin only route
@router.delete("/entities/batch", response_model=None)
async def delete_batch(ids: List[str], db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"ids": ids}
    action = schemas.ApiActionCreate(method="delete", route="/admin/entities/batch", params=params, result=None, user_id=requester.id)

    try:
        total = await crud.entity.delete_batch(db, requester=requester, ids=ids)
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

    action.result = {"code": 200, "total": total}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=total)


@router.put("/users/password", response_model=None)
def set_password(id: str, password: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"id": id}
    action = schemas.ApiActionCreate(method="put", route="/admin/users/password", params=params, result=None, user_id=requester.id)

    try:
        crud.user.set_user_password(db, requester=requester, user=id, password=password)
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

    return Payload(data={"ok": True})


@router.get("/servers/", response_model=None)
def list_servers(requester: models.User = Depends(auth.requester)):
    if requester.is_super_admin():
        k8s_service = k8s.k8sServiceInstance
        response = k8s_service.list_servers()
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return Payload(data={"ok": True, "response": response})


@router.post("/servers/{space_id}", response_model=None)
def create_server(space_id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    if requester.is_super_admin():
        k8s_service = k8s.k8sServiceInstance
        response = k8s_service.create_server(db=db, requester=requester, space_id=space_id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return Payload(data={"ok": True, "response": response})


@router.delete("/servers/{server_id}", response_model=None)
def delete_server(server_id: str, requester: models.User = Depends(auth.requester)):
    if requester.is_super_admin():
        k8s_service = k8s.k8sServiceInstance
        response = k8s_service.delete_server(server_id=server_id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return Payload(data={"ok": True, "response": response})


@router.get("/portals", response_class=HTMLResponse)
async def read_items(requester: models.User = Depends(auth.requester)):
    if requester.is_admin():
        # with open('static/portals.html', 'r') as file:
        with open('app/templates/portals.html', 'r') as file:
            data = file.read()
            return data
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
