"""Directory API: read-only people lookup for pickers (account owner, etc.).

Guarded by authentication only (any internal signed-in user). Exposes a
minimal, non-sensitive {sub, email, name} projection of the Cognito pool.
"""

from fastapi import APIRouter, Depends, Query

from neocloud.auth.dependencies import CurrentUser, get_current_user
from neocloud.core.config import Settings, get_settings
from neocloud.domains.directory.schemas import DirectoryUser
from neocloud.domains.directory.service import DirectoryService

router = APIRouter(prefix="/directory", tags=["Directory"])


def _service(settings: Settings = Depends(get_settings)) -> DirectoryService:
    return DirectoryService(settings)


@router.get("/users", response_model=list[DirectoryUser])
async def list_directory_users(
    q: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=60, ge=1, le=60),
    _user: CurrentUser = Depends(get_current_user),
    service: DirectoryService = Depends(_service),
) -> list[DirectoryUser]:
    return service.list_users(q=q, limit=limit)
