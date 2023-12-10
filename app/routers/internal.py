import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from starlette import status

from app import crud, models, schemas
from app.crud.entity import EntityParameterError, EntityAccessError
from app.dependencies import database, auth
from app.schemas.payload import Payload

router = APIRouter()


@router.get("/build_jobs/pending", response_model=Payload[schemas.BuildJob])
def get_pending_build_job(platforms: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    logging.log(logging.INFO, f"auth check build job")

    if requester.is_internal:
        try:
            response = crud.build_job.get_pending_job(db=db, requester=requester, platforms=platforms)
        except EntityAccessError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityParameterError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return Payload(data=response)


@router.get("/build_jobs", response_model=Payload[List[schemas.BuildJob]])
def get_build_jobs(platforms: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    logging.log(logging.INFO, f"auth check build job")

    if requester.is_internal or requester.is_admin:
        try:
            response = crud.build_job.get_jobs(db=db, requester=requester, platforms=platforms)
        except EntityAccessError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityParameterError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return Payload(data=response)


@router.post("/build_jobs", response_model=Payload[schemas.BuildJob])
def add_pending_build_job(mod_id: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    logging.log(logging.INFO, f"auth check build job")

    if requester.is_internal:
        try:
            response = crud.build_job.add_pending_job(mod_id=mod_id, db=db, requester=requester)
        except EntityAccessError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityParameterError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return Payload(data=response)


@router.patch("/build_jobs", response_model=Payload[schemas.BuildJob])
def update_build_job(job_id: str, job_status: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    logging.log(logging.INFO, f"auth check build job")

    if requester.is_internal or requester.is_admin:
        try:
            response = crud.build_job.update_job(job_id=job_id, job_status=job_status, db=db, requester=requester)
        except EntityAccessError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityParameterError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return Payload(data=response)


@router.put("/subscribe", response_model=Payload[schemas.SubscriptionResponse])
def subscribe(email: (Optional[str]) = Body(...), platform: Optional[str] = Body(""), notes: Optional[str] = Body(""), type: Optional[str] = Body(""), name: Optional[str] = Body(""), db: Session = Depends(database.session),
              requester: models.User = Depends(auth.requester)):
    logging.log(logging.INFO, f"subscribe; email: ${email}, platform: ${platform}, notes: ${notes}")

    if requester.is_internal or requester.is_admin:
        try:
            response = crud.subscription.subscribe(email=email, platform=platform, notes=notes, type=type, name=name, db=db, requester=requester)
        except EntityAccessError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityParameterError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return Payload(data=response)
