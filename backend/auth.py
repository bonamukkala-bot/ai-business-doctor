import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase_client import supabase, create_authenticated_client

security_scheme = HTTPBearer(auto_error=False)

class SupabaseUser:
    def __init__(self, id: str, email: str):
        self.id = id
        self.email = email


class AuthenticatedSupabaseUser(SupabaseUser):
    def __init__(self, id: str, email: str, supabase_client):
        super().__init__(id, email)
        self.supabase = supabase_client


def _normalize_supabase_auth_response(result):
    if result is None:
        return None, "No response from Supabase auth."

    if isinstance(result, dict):
        error = result.get("error")
        data = result.get("data") or result.get("user")
        return data, error

    error = getattr(result, "error", None)
    data = getattr(result, "data", None) or getattr(result, "user", None)
    return data, error


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> SupabaseUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials or credentials.scheme != "Bearer":
        raise credentials_exception

    token = credentials.credentials
    try:
        result = supabase.auth.get_user(token)
    except Exception:
        raise credentials_exception

    user_data, error = _normalize_supabase_auth_response(result)
    if error or not user_data:
        raise credentials_exception

    if isinstance(user_data, dict):
        email = user_data.get("email")
        user_id = user_data.get("id")
    else:
        email = getattr(user_data, "email", None)
        user_id = getattr(user_data, "id", None)

    if not email or not user_id:
        raise credentials_exception

    try:
        authenticated_client = create_authenticated_client(token)
    except Exception:
        raise credentials_exception

    return AuthenticatedSupabaseUser(id=str(user_id), email=email, supabase_client=authenticated_client)
