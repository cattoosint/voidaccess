"""
Admin routes for VoidAccess API.

Provides administrative endpoints for monitoring and managing the system.
"""

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from search.circuit_breaker import get_all_states, record_success

router = APIRouter(tags=["admin"])


@router.get("/circuit-breakers", dependencies=[Depends(get_current_user)])
async def get_circuit_breakers() -> dict:
    """
    Get the current state of all search engine circuit breakers.
    Returns state, failure count, and last success timestamp for each engine.
    """
    return await get_all_states()


@router.post("/circuit-breakers/{engine_name}/reset", dependencies=[Depends(get_current_user)])
async def reset_circuit_breaker(engine_name: str) -> dict:
    """Reset a circuit breaker to closed state manually."""
    await record_success(engine_name)
    return {"engine": engine_name, "state": "closed", "message": "Circuit breaker reset"}


@router.post("/circuit-breakers/reset-all", dependencies=[Depends(get_current_user)])
async def reset_all_circuit_breakers() -> dict:
    """Reset all circuit breakers to closed state."""
    from search import SEARCH_ENGINES
    for engine in SEARCH_ENGINES:
        await record_success(engine["name"])
    return {"reset_count": len(SEARCH_ENGINES), "state": "all closed"}