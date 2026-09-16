from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Basic liveness check — confirms the Backend API container is up.

    Sprint 1 scope: this is the one endpoint that should already work
    once `docker-compose up backend` runs, to verify the skeleton is
    wired correctly before any RAG logic exists.
    """
    return {"status": "ok"}
