"""Clerk JWT verification via JWKS."""

from __future__ import annotations

import jwt
from jwt import PyJWKClient

from app.config import settings

_JWK_CLIENT: PyJWKClient | None = None


def _get_jwk_client() -> PyJWKClient:
    global _JWK_CLIENT
    if not settings.clerk_jwks_url:
        raise ValueError("clerk_jwks_url is not configured")
    if _JWK_CLIENT is None or _JWK_CLIENT.uri != settings.clerk_jwks_url:
        _JWK_CLIENT = PyJWKClient(settings.clerk_jwks_url)
    return _JWK_CLIENT


def verify_clerk_jwt(token: str) -> dict:
    """Verify a Clerk session JWT and return its claims."""
    if not settings.clerk_jwks_url:
        raise ValueError("clerk_jwks_url is not configured")

    signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
    decode_kwargs: dict = {
        "algorithms": ["RS256"],
        "options": {"require": ["exp", "sub"]},
    }
    if settings.clerk_issuer:
        decode_kwargs["issuer"] = settings.clerk_issuer

    return jwt.decode(token, signing_key.key, **decode_kwargs)
