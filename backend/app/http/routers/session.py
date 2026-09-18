from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.settings.models import ActiveNetworkPut
from app.settings.service import dump_session, get_session, set_active_network

router = APIRouter()


@router.get("/session")
def get_session_route() -> dict[str, Any]:
    return dump_session(get_session())


@router.put("/session/active-network")
def put_active_network(body: ActiveNetworkPut) -> dict[str, Any]:
    return dump_session(set_active_network(body.network_id))
