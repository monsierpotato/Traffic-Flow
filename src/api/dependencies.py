from fastapi import Depends, HTTPException, status

from shared.database import get_database


def require_database(db=Depends(get_database)):
    """Return the active persistence adapter or a truthful readiness error."""
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not connected",
        )
    return db
