from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status
from starlette.requests import Request

from app import schemas, crud, models
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError
from app.dependencies import database, auth
from app.schemas.payload import Payload

router = APIRouter()


@router.post("/launcher", response_model=Payload[schemas.Ok])
def post_launcher_action(request: Request, create_data: schemas.LauncherActionCreate, db: Session = Depends(database.session), requester=Depends(auth.requester)):
    if not create_data.address:
        create_data.address = request.client.host
    create_data.user_id = requester.id

    action = schemas.ApiActionCreate(method="post", route="/actions/launcher", params=None, result=None, user_id=requester.id)

    try:
        result = crud.user.report_launcher_action(db, action=create_data, requester=requester.id)
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

    action.result = {"code": 200, "id": result.id}
    crud.user.report_api_action(db, requester=requester, action=action)

    return Payload(data=schemas.Ok(ok=True))
