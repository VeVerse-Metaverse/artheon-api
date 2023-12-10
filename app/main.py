import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from app import models
from app.database import engine
from app.routers import auth, collection, object, user, entity, space, online_game, admin, actions, download, mod, server, portal, internal, w3, file, template, event, payment, placeable_class

models.Base.metadata.create_all(bind=engine)

env = os.getenv("ENVIRONMENT")
if env == "prod":
    docs_url = None
    log_level = "info"
else:
    docs_url = "/docs"
    if env == "test":
        log_level = "info"
    else:
        log_level = "debug"

# setup loggers
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logging.conf')
logging.config.fileConfig(log_file_path, disable_existing_loggers=False)
logger = logging.getLogger(__name__)

logger.info("starting application")

app = FastAPI(title="VeVerse API",
              description="Version 1.0.0.48",
              docs_url=docs_url, redoc_url=None)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    print(_, exc)
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc}),
    )


class CustomHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        url = str(request.url)
        if 'static' in url:
            if url.endswith('.json'):
                response.headers['content-type'] = 'application/json; charset=utf-8'
            if url.endswith('.js'):
                response.headers['content-type'] = 'application/javascript; charset=utf-8'
            elif url.endswith('.css'):
                response.headers['content-type'] = 'text/css; charset=utf-8'
        return response


app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])
app.add_middleware(CustomHeaderMiddleware)


@app.get("/")
async def home():
    return jsonable_encoder({"data": "access denied"})


app.mount("/static", StaticFiles(directory="app/static"), name="static")
# app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)

app.include_router(entity.router, prefix="/entities", tags=["entities"])
app.include_router(user.router, prefix="/users", tags=["users"])
app.include_router(space.router, prefix="/spaces", tags=["spaces"])
app.include_router(placeable_class.router, prefix="/placeable_classes", tags=["placeable_classes"])
app.include_router(object.router, prefix="/objects", tags=["objects"])
app.include_router(collection.router, prefix="/collections", tags=["collections"])
app.include_router(online_game.router, prefix="/online_games", tags=["online games"])
app.include_router(server.router, prefix="/servers", tags=["servers"])
app.include_router(actions.router, prefix="/actions", tags=["actions"])
app.include_router(download.router, prefix="/download", tags=["downloads"])
app.include_router(mod.router, prefix="/mods", tags=["mods"])
app.include_router(portal.router, prefix="/portals", tags=["portals"])
app.include_router(file.router, prefix="/files", tags=["files"])
app.include_router(template.router, prefix="/templates", tags=["templates"])
app.include_router(event.router, prefix="/events", tags=["events"])
app.include_router(payment.router, prefix="/payments", tags=["payments"])
# app.include_router(threefold.router, prefix="/threefold", tags=["threefold"])

app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(internal.router, prefix="/internal", tags=["internal"])

app.include_router(w3.router, prefix="/w3", tags=["w3"])

if __name__ == "__main__":
    print("Starting application...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=log_level)
