class AppException(Exception):
    """Base for all application exceptions.

    Every subclass must define `code` (the API error code string)
    and `http_status`. The auth router maps these to the standard
    error envelope automatically.
    """

    code: str = "INTERNAL_ERROR"
    http_status: int = 500

    def __init__(self, message: str | None = None):
        self.message = message or self._default_message()
        super().__init__(self.message)

    def _default_message(self) -> str:
        return "An unexpected error occurred."


# ── Auth exceptions ──────────────────────────────────────────────────────────

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
    """Presented a previously revoked refresh token — possible replay attack."""

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


# ── Ride exceptions ──────────────────────────────────────────────────────────

class RideTokenGenerationError(AppException):
    """Redis unavailable or jti collision could not be resolved."""

    code = "RIDE_TOKEN_UNAVAILABLE"
    http_status = 503

    def _default_message(self) -> str:
        return "Could not generate ride token. Try again."


class RideTokenInvalidError(AppException):
    code = "RIDE_TOKEN_INVALID"
    http_status = 401

    def _default_message(self) -> str:
        return "Ride token is invalid or malformed."


class RideTokenExpiredError(AppException):
    code = "RIDE_TOKEN_EXPIRED"
    http_status = 401

    def _default_message(self) -> str:
        return "Ride token has expired."


class RideTokenReusedError(AppException):
    code = "RIDE_TOKEN_REUSED"
    http_status = 409

    def _default_message(self) -> str:
        return "Ride token has already been used."


class RideAlreadyActiveError(AppException):
    code = "RIDE_ALREADY_ACTIVE"
    http_status = 409

    def _default_message(self) -> str:
        return "You already have an active ride."


class RideNotFoundError(AppException):
    code = "RIDE_NOT_FOUND"
    http_status = 404

    def _default_message(self) -> str:
        return "Ride not found."


class RideInvalidStateError(AppException):
    code = "RIDE_INVALID_STATE"
    http_status = 409

    def _default_message(self) -> str:
        return "Ride is not in a valid state for this operation."


class RideForbiddenError(AppException):
    code = "RIDE_FORBIDDEN"
    http_status = 403

    def _default_message(self) -> str:
        return "You do not own this ride."


class DockMismatchError(AppException):
    code = "RIDE_DOCK_MISMATCH"
    http_status = 409

    def _default_message(self) -> str:
        return "This ride token was not issued for this dock."


class VehicleUnavailableError(AppException):
    code = "VEHICLE_UNAVAILABLE"
    http_status = 409

    def _default_message(self) -> str:
        return "No vehicle is currently available for assignment."


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


class InvalidTransactionAmountError(AppException):
    code = "WALLET_INVALID_AMOUNT"
    http_status = 400

    def _default_message(self) -> str:
        return "Transaction amount must be greater than zero."


class DuplicateReferenceError(AppException):
    code = "WALLET_DUPLICATE_REFERENCE"
    http_status = 409

    def _default_message(self) -> str:
        return "A transaction with this reference_id already exists."


# ── Dock exceptions (Track B) ────────────────────────────────────────────────

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


class SlotNotFoundError(AppException):
    code = "DOCK_SLOT_NOT_FOUND"
    http_status = 404

    def _default_message(self) -> str:
        return "Dock slot not found."
