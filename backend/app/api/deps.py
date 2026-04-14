from fastapi import Depends

from backend.app.core.config import Settings, get_settings
from backend.app.core.storage import Storage

_storage: Storage | None = None


def get_storage(settings: Settings = Depends(get_settings)) -> Storage:
    global _storage
    if _storage is None:
        _storage = Storage(settings)
    return _storage
