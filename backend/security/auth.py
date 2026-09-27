"""
security/auth.py
Core auth primitives: password hashing/verification, JWT creation/decoding,
and generating a random temporary password for newly-created accounts.

Uses pwdlib (already installed in venv -- see routers/auth_router.py's
original draft) for hashing, and python-jose for JWT, both already in
requirements.txt.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from pwdlib import PasswordHash

from config.settings import settings

password_hasher = PasswordHash.recommended()


class AuthError(Exception):
    """Raised for any auth failure (bad token, expired token, etc.)."""
    pass


# --- Passwords ---------------------------------------------------------

def hash_password(plain_password: str) -> str:
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return password_hasher.verify(plain_password, hashed_password)
    except Exception:
        return False


def generate_temporary_password(length: int = 12) -> str:
    """
    Generates a random password like 'Xy8$mK2pQw!7' -- at least one
    uppercase, one lowercase, one digit, one symbol, guaranteed.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*" for c in pwd)
        ):
            return pwd


# --- JWT -----------------------------------------------------------------

def create_access_token(user_id: int, email: str, role: str, employee_id: int = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "employee_id": employee_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Returns the decoded payload, or raises AuthError if invalid/expired."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise AuthError(f"Invalid or expired token: {e}")
