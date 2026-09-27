"""
security/permissions.py
DEPRECATED -- do not use.

This file's earlier require_role() had two real bugs: (1) it decoded
tokens with the literal string "SECRET_KEY" while auth_router.py signed
them with a different literal string "SKILLSPRINT_SECRET_KEY", so every
valid token would fail to decode; (2) `token: str` had no FastAPI security
scheme attached, so FastAPI never extracted it from the Authorization
header in the first place -- it would always be empty.

Both are fixed in security/rbac.py (get_current_user / require_roles),
which is what every router actually uses now. Nothing imports from this
file anymore; it's kept only so old imports don't hard-crash.
"""

from security.rbac import get_current_user, require_roles  # noqa: F401
