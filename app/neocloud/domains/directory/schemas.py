"""Schemas for the directory (people lookup) API."""

from pydantic import BaseModel


class DirectoryUser(BaseModel):
    """Minimal, non-sensitive identity for pickers (account owner, etc.)."""

    sub: str
    email: str | None = None
    name: str | None = None
