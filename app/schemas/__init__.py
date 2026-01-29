"""Pydantic schemas for API request/response validation."""

from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    Token,
    TokenRefresh,
)
from app.schemas.trademark import (
    TrademarkCreate,
    TrademarkUpdate,
    TrademarkResponse,
    TrademarkListResponse,
    RegistrationCreate,
    RegistrationUpdate,
    RegistrationResponse,
    RenewalActionCreate,
    ClassResponse,
    TerritoryResponse,
    RightsHolderResponse,
)

__all__ = [
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "Token",
    "TokenRefresh",
    # Trademark
    "TrademarkCreate",
    "TrademarkUpdate",
    "TrademarkResponse",
    "TrademarkListResponse",
    "RegistrationCreate",
    "RegistrationUpdate",
    "RegistrationResponse",
    "RenewalActionCreate",
    "ClassResponse",
    "TerritoryResponse",
    "RightsHolderResponse",
]
