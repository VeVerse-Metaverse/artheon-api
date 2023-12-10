import random
import string
from string import Template

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette import status
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from app import models, crud, schemas
from app.crud.entity import EntityParameterError, EntityAccessError, EntityNotFoundError
from app.dependencies import auth, database
from app.schemas.payload import Payload

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def metamask_login(requester: models.User = Depends(auth.requester)):
    if requester.is_active:
        try:
            with open('app/templates/w3/login.html', 'r') as file:
                template = Template(file.read())
                random_key_id = ''.join(random.sample(string.ascii_letters + string.digits + '_', 8))
                response_html = template.substitute(key=requester.api_key, keyId=random_key_id)
                return response_html
        except FileNotFoundError:
            with open('templates/w3/login.html', 'r') as file:
                template = Template(file.read())
                random_key_id = ''.join(random.sample(string.ascii_letters + string.digits + '_', 8))
                response_html = template.substitute(key=requester.api_key, keyId=random_key_id)
                return response_html
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


@router.get("/mint_land", response_class=HTMLResponse)
async def metamask_mint_land(tokenId: int = Query(0), requester: models.User = Depends(auth.requester)):
    if requester.is_active:
        try:
            with open('app/templates/w3/mint_land.html', 'r') as file:
                template = Template(file.read())
                random_key_id = 'k' + ''.join(random.sample(string.ascii_letters + string.digits + '_', 8))
                response_html = template.substitute(key=requester.api_key, tokenId=tokenId, keyId=random_key_id)
                return response_html
        except FileNotFoundError:
            with open('templates/w3/mint_land.html', 'r') as file:
                template = Template(file.read())
                random_key_id = 'k' + ''.join(random.sample(string.ascii_letters + string.digits + '_', 8))
                response_html = template.substitute(key=requester.api_key, tokenId=tokenId, keyId=random_key_id)
                return response_html
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


@router.get("/deploy_world_land_mint_contract", response_class=HTMLResponse)
async def metamask_mint_land( tokenId: int = Query(0), requester: models.User = Depends(auth.requester)):
    if requester.is_active:
        try:
            with open('app/templates/w3/land_mint_contract_template.html', 'r') as file:
                template = Template(file.read())
                random_key_id = 'k' + ''.join(random.sample(string.ascii_letters + string.digits + '_', 8))
                response_html = template.substitute(key=requester.api_key, tokenId=tokenId, keyId=random_key_id)
                return response_html
        except FileNotFoundError:
            with open('templates/w3/land_mint_contract_template.html', 'r') as file:
                template = Template(file.read())
                random_key_id = 'k' + ''.join(random.sample(string.ascii_letters + string.digits + '_', 8))
                response_html = template.substitute(key=requester.api_key, tokenId=tokenId, keyId=random_key_id)
                return response_html
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


@router.post("/login", response_model=Payload[schemas.Ok])
async def metamask_login_token(account: str, db: Session = Depends(database.session), requester: models.User = Depends(auth.requester)):
    params = {"account": account}
    action = schemas.ApiActionCreate(method="get", route="/w3/login/{account}", params=params, result=None, user_id=requester.id)
    if requester.is_active:
        try:
            ok = bool(crud.user.update_eth_account(db, requester=requester, eth_account=account))
        except EntityParameterError as e:
            if requester:
                action.result = {"code": 400, "message": str(e)}
                crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EntityAccessError as e:
            if requester:
                action.result = {"code": 403, "message": str(e)}
                crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except EntityNotFoundError as e:
            if requester:
                action.result = {"code": 404, "message": str(e)}
                crud.user.report_api_action(db, requester=requester, action=action)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        action.result = {"code": 200, "ok": True}
        crud.user.report_api_action(db, requester=requester, action=action)

        return Payload(data=schemas.Ok(ok=ok))
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
