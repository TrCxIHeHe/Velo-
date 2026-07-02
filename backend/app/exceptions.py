class AppException(Exception):
    """Base for all application exceptions.

    Every subclass must define `code` (the API error code string)
    and `http_status`. Routers map these to the standard error envelope
    automatically.
    """

    code: str = "INTERNAL_ERROR"
    http_status: int = 500

    def __init__(self, message: str | None = None):
        self.message = message or self._default_message()
        super().__init__(self.message)

    def _default_message(self) -> str:
        return "An unexpected error occurred."


# ── Auth exceptions (Track A) ────────────────────────────────────────────────

class InvalidFirebaseTokenError(AppException):
    code = "AUTH_INVALID_FIREBASE_TOKEN"
    http_status = 401

    def _default_message(self) -> str:
        return "Firebase ID token is invalid or expired."


class MissingPhoneNumberError(AppException):
    code = "AUTH_MISSING_PHONE"
    http_status = 400

    def _default_message(self) -> str:
        return "Firebase token does not contain a verified phone number."


class InvalidTokenError(AppException):
    code = "AUTH_INVALID_TOKEN"
    http_status = 401

    def _default_message(self) -> str:
        return "Access token is invalid."


class TokenExpiredError(AppException):
    code = "AUTH_TOKEN_EXPIRED"
    http_status = 401

    def _default_message(self) -> str:
        return "Access token has expired."


class RefreshTokenInvalidError(AppException):
    code = "AUTH_REFRESH_INVALID"
    http_status = 401

    def _default_message(self) -> str:
        return "Refresh token is invalid."


class RefreshTokenExpiredError(AppException):
    code = "AUTH_REFRESH_EXPIRED"
    http_status = 401

    def _default_message(self) -> str:
        return "Refresh token has expired."


class RefreshTokenReuseError(AppException):
    code = "AUTH_REFRESH_REUSE"
    http_status = 401

    def _default_message(self) -> str:
        return "Refresh token has already been used. All sessions have been revoked."


class UserDeactivatedError(AppException):
    code = "AUTH_USER_DEACTIVATED"
    http_status = 403

    def _default_message(self) -> str:
        return "This account has been deactivated."


class ForbiddenError(AppException):
    code = "AUTH_FORBIDDEN"
    http_status = 403

    def _default_message(self) -> str:
        return "You do not have permission to perform this action."


class UserNotFoundError(AppException):
    code = "AUTH_USER_NOT_FOUND"
    http_status = 404

    def _default_message(self) -> str:
        return "User not found."


# ── Wallet exceptions (Track B) ──────────────────────────────────────────────

class WalletNotFoundError(AppException):
    code = "WALLET_NOT_FOUND"
    http_status = 404

    def _default_message(self) -> str:
        return "Wallet not found."


class InsufficientBalanceError(AppException):
    code = "WALLET_INSUFFICIENT_BALANCE"
    http_status = 400

    def _default_message(self) -> str:
        return "Wallet balance is insufficient for this operation."


# ── Dock exceptions (Track B, used from Phase 3 onward) ──────────────────────

class DockNotFoundError(AppException):
    code = "DOCK_NOT_FOUND"
    http_status = 404

    def _default_message(self) -> str:
        return "Dock not found."


class DockFullError(AppException):
    code = "DOCK_FULL"
    http_status = 400

    def _default_message(self) -> str:
        return "This dock has no available slots."


class SlotOccupiedError(AppException):
    code = "DOCK_SLOT_OCCUPIED"
    http_status = 400

    def _default_message(self) -> str:
        return "This dock slot is already occupied."