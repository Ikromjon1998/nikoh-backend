"""
Custom exception classes for the Nikoh application.
Provides structured error handling with machine-readable error codes.
"""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Error codes matching frontend for consistency"""

    # Authentication errors (401)
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_NOT_AUTHENTICATED = "AUTH_NOT_AUTHENTICATED"

    # Authorization errors (403)
    AUTHZ_FORBIDDEN = "AUTHZ_FORBIDDEN"
    AUTHZ_INSUFFICIENT_PERMISSIONS = "AUTHZ_INSUFFICIENT_PERMISSIONS"
    AUTHZ_EMAIL_NOT_VERIFIED = "AUTHZ_EMAIL_NOT_VERIFIED"

    # Resource errors (404, 409)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"

    # Validation errors (400, 422)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VALIDATION_INVALID_FORMAT = "VALIDATION_INVALID_FORMAT"
    VALIDATION_REQUIRED_FIELD = "VALIDATION_REQUIRED_FIELD"

    # Payment errors (402)
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_SUBSCRIPTION_EXPIRED = "PAYMENT_SUBSCRIPTION_EXPIRED"

    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (500+)
    SERVER_ERROR = "SERVER_ERROR"
    SERVER_UNAVAILABLE = "SERVER_UNAVAILABLE"


class AppException(Exception):
    """
    Base exception class for application errors.
    All custom exceptions should inherit from this class.
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.SERVER_ERROR,
        status_code: int = 500,
        field: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.field = field
        self.metadata = metadata or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to response dictionary"""
        response = {
            "detail": self.message,
            "code": self.code.value,
        }
        if self.field:
            response["field"] = self.field
        if self.metadata:
            response["metadata"] = self.metadata
        return response


# Authentication Errors (401)


class AuthenticationError(AppException):
    """Base authentication error"""

    def __init__(
        self,
        message: str = "Authentication required",
        code: ErrorCode = ErrorCode.AUTH_NOT_AUTHENTICATED,
        field: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=401,
            field=field,
            metadata=metadata,
        )


class InvalidCredentialsError(AuthenticationError):
    """Invalid email or password"""

    def __init__(
        self,
        message: str = "Noto'g'ri email yoki parol",
        field: str | None = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.AUTH_INVALID_CREDENTIALS,
            field=field,
        )


class TokenExpiredError(AuthenticationError):
    """JWT token has expired"""

    def __init__(self, message: str = "Sessiya muddati tugadi"):
        super().__init__(
            message=message,
            code=ErrorCode.AUTH_TOKEN_EXPIRED,
        )


class TokenInvalidError(AuthenticationError):
    """JWT token is invalid"""

    def __init__(self, message: str = "Token yaroqsiz"):
        super().__init__(
            message=message,
            code=ErrorCode.AUTH_TOKEN_INVALID,
        )


# Authorization Errors (403)


class AuthorizationError(AppException):
    """Base authorization error"""

    def __init__(
        self,
        message: str = "Bu amalni bajarishga ruxsat yo'q",
        code: ErrorCode = ErrorCode.AUTHZ_FORBIDDEN,
        field: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=403,
            field=field,
            metadata=metadata,
        )


class InsufficientPermissionsError(AuthorizationError):
    """User lacks required permissions"""

    def __init__(self, message: str = "Sizda yetarli huquqlar mavjud emas"):
        super().__init__(
            message=message,
            code=ErrorCode.AUTHZ_INSUFFICIENT_PERMISSIONS,
        )


class EmailNotVerifiedError(AuthorizationError):
    """Email verification required"""

    def __init__(self, message: str = "Iltimos, email manzilingizni tasdiqlang"):
        super().__init__(
            message=message,
            code=ErrorCode.AUTHZ_EMAIL_NOT_VERIFIED,
        )


# Resource Errors (404, 409)


class NotFoundError(AppException):
    """Resource not found"""

    def __init__(
        self,
        message: str = "So'ralgan ma'lumot topilmadi",
        resource: str | None = None,
    ):
        metadata = {"resource": resource} if resource else None
        super().__init__(
            message=message,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            status_code=404,
            metadata=metadata,
        )


class AlreadyExistsError(AppException):
    """Resource already exists"""

    def __init__(
        self,
        message: str = "Bu ma'lumot allaqachon mavjud",
        field: str | None = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.RESOURCE_ALREADY_EXISTS,
            status_code=409,
            field=field,
        )


class ConflictError(AppException):
    """Resource conflict"""

    def __init__(
        self,
        message: str = "Ma'lumotlar bir-biriga zid",
        field: str | None = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.RESOURCE_CONFLICT,
            status_code=409,
            field=field,
        )


# Validation Errors (400, 422)


class ValidationError(AppException):
    """Validation error"""

    def __init__(
        self,
        message: str = "Iltimos, kiritilgan ma'lumotlarni tekshiring",
        field: str | None = None,
        code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=422,
            field=field,
        )


class InvalidFormatError(ValidationError):
    """Invalid data format"""

    def __init__(
        self,
        message: str = "Ma'lumot formati noto'g'ri",
        field: str | None = None,
    ):
        super().__init__(
            message=message,
            field=field,
            code=ErrorCode.VALIDATION_INVALID_FORMAT,
        )


class RequiredFieldError(ValidationError):
    """Required field missing"""

    def __init__(
        self,
        message: str = "Ushbu maydon to'ldirilishi shart",
        field: str | None = None,
    ):
        super().__init__(
            message=message,
            field=field,
            code=ErrorCode.VALIDATION_REQUIRED_FIELD,
        )


# Payment Errors (402)


class PaymentRequiredError(AppException):
    """Payment required to access feature"""

    def __init__(
        self,
        message: str = "Bu funksiyadan foydalanish uchun to'lov talab qilinadi",
        code: ErrorCode = ErrorCode.PAYMENT_REQUIRED,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=402,
            metadata=metadata,
        )


class PaymentFailedError(PaymentRequiredError):
    """Payment processing failed"""

    def __init__(
        self,
        message: str = "To'lov amalga oshmadi",
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.PAYMENT_FAILED,
            metadata=metadata,
        )


class SubscriptionExpiredError(PaymentRequiredError):
    """Subscription has expired"""

    def __init__(
        self,
        message: str = "Obuna muddati tugagan",
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.PAYMENT_SUBSCRIPTION_EXPIRED,
            metadata=metadata,
        )


# Rate Limiting (429)


class RateLimitError(AppException):
    """Rate limit exceeded"""

    def __init__(
        self,
        message: str = "Juda ko'p so'rov yuborildi. Biroz kuting",
        retry_after: int = 60,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=429,
            metadata={"retry_after": retry_after},
        )


# Server Errors (500)


class ServerError(AppException):
    """Internal server error"""

    def __init__(
        self,
        message: str = "Server xatoligi yuz berdi",
        code: ErrorCode = ErrorCode.SERVER_ERROR,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=500,
        )
