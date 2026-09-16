"""
Auth0 JWT token validation middleware for FastAPI.
Protects API endpoints by verifying JWT tokens from Auth0.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from typing import Optional
import httpx
import os
from functools import lru_cache

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "dev-i4m880asz7y6j5sk.us.auth0.com")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", f"https://{AUTH0_DOMAIN}/api/v2/")
ALGORITHMS = ["RS256"]

security = HTTPBearer()


@lru_cache()
def get_jwks():
    """Fetch Auth0 public keys for JWT verification (cached)."""
    try:
        response = httpx.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to fetch Auth0 JWKS: {str(e)}"
        )


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify Auth0 JWT token and return decoded payload.
    
    Args:
        credentials: HTTP Bearer token from Authorization header
        
    Returns:
        dict: Decoded JWT payload with user information
        
    Raises:
        HTTPException: If token is invalid or verification fails
    """
    token = credentials.credentials
    
    try:
        # Get Auth0 public keys
        jwks = get_jwks()
        
        # Decode token header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        
        # Find matching key in JWKS
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break
        
        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key"
            )
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token_payload: dict = Depends(verify_token)) -> dict:
    """
    Extract user information from verified JWT token.
    
    Args:
        token_payload: Decoded JWT payload from verify_token
        
    Returns:
        dict: User information (sub, email, etc.)
    """
    return {
        "user_id": token_payload.get("sub"),
        "email": token_payload.get("email"),
        "permissions": token_payload.get("permissions", [])
    }


# Optional: Dependency for endpoints that don't require auth but can use it if present
def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[dict]:
    """
    Get current user if token is present, otherwise return None.
    Useful for endpoints that are optionally authenticated.
    """
    if credentials is None:
        return None
    
    try:
        return get_current_user(verify_token(credentials))
    except HTTPException:
        return None
