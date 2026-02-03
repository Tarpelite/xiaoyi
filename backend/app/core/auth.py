from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.algorithms import RSAAlgorithm
import json
import urllib.request
from typing import Dict, Any

from app.core.config import settings

security = HTTPBearer()


class AuthError(Exception):
    def __init__(self, error: str, status_code: int):
        self.error = error
        self.status_code = status_code


class User:
    def __init__(self, payload: Dict[str, Any]):
        self.sub = payload.get("sub")
        self.name = payload.get("name")
        self.email = payload.get("email")
        self.raw_payload = payload


# Cache for JWKS
_jwks_cache = {}


def get_jwks():
    """Fetch and cache JWKS"""
    global _jwks_cache
    if not _jwks_cache:
        jwks_url = f"{settings.AUTHING_ISSUER}/.well-known/jwks.json"
        with urllib.request.urlopen(jwks_url) as response:
            _jwks_cache = json.loads(response.read())
    return _jwks_cache


def get_public_key(token: str):
    """Get public key from JWKS for the token header"""
    try:
        header = jwt.get_unverified_header(token)
        jwks = get_jwks()

        for key in jwks["keys"]:
            if key["kid"] == header["kid"]:
                return RSAAlgorithm.from_jwk(json.dumps(key))

        # If key not found, try refreshing cache once
        global _jwks_cache
        _jwks_cache = {}
        jwks = get_jwks()
        for key in jwks["keys"]:
            if key["kid"] == header["kid"]:
                return RSAAlgorithm.from_jwk(json.dumps(key))

        raise AuthError("Public key not found", 401)
    except Exception as e:
        raise AuthError(f"Invalid token header: {str(e)}", 401)


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Verify JWT token from Authing
    """
    token = credentials.credentials

    try:
        public_key = get_public_key(token)

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.AUTHING_APP_ID,
            issuer=settings.AUTHING_ISSUER,
        )

        return User(payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.error,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
