from pathlib import Path

from fastapi import Depends
from fastapi_caching import hashers, RedisBackend, CacheManager
from fastapi_caching.objects import NoOpResponseCache

from app.config import settings

app_version = "-".join(
    [hashers.installed_packages_hash(), hashers.files_hash(Path(__file__).parent)]
)
backend = RedisBackend(
    host='127.0.0.1',
    port=6379,
    prefix="artheon-api-cache",
    app_version=app_version,
)
manager = CacheManager(backend)


def from_request() -> Depends:
    if settings.use_cache:
        return manager.from_request()
    return Depends(NoOpResponseCache)
