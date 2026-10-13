"""Componentes centrais do VerificaLab."""

from .authorization import Authorization, AuthorizationError, require_authorization

__all__ = ["Authorization", "AuthorizationError", "require_authorization"]
