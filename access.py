from fastapi import Depends, HTTPException, Request


def authorize(required_role: str):
    async def dependency(request: Request):
        user_role = getattr(request.state, "role", "guest")
        if user_role != required_role:
            raise HTTPException(status_code=403, detail=f"Role '{required_role}' required")
        return True

    return Depends(dependency)
