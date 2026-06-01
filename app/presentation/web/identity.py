from __future__ import annotations

import re
import secrets

from flask import Flask, g, request


_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{8,128}$')


def _is_valid_id(value: str) -> bool:
    return bool(value and _ID_RE.match(value))


def resolve_participant_id() -> str:
    """Return the participant id for the current request.

    Called by UserScopedJsonStore on every request; result is cached on the
    Flask request context (g.participant_id) so all repositories within one
    request land in the same store.
    """
    return g.participant_id


def register_identity(app: Flask, cookie_name: str, cookie_max_age: int) -> None:
    """Wire anonymous-identity cookie logic into the Flask app.

    before_request: read the cookie; if missing or malformed, generate a fresh id.
    after_request:  if the id is new (or the cookie was absent), set the cookie.
    """

    @app.before_request
    def _load_participant_id():
        raw = request.cookies.get(cookie_name, "")
        if _is_valid_id(raw):
            g.participant_id = raw
            g.participant_id_is_new = False
        else:
            g.participant_id = secrets.token_urlsafe(16)
            g.participant_id_is_new = True

    @app.after_request
    def _set_participant_cookie(response):
        if getattr(g, "participant_id_is_new", False):
            response.set_cookie(
                cookie_name,
                g.participant_id,
                max_age=cookie_max_age,
                httponly=True,
                samesite="Lax",
            )
        return response
