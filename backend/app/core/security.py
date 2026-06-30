import hashlib
import secrets


def generate_raw_token(nbytes: int = 64) -> str:
    """Generate a cryptographically secure URL-safe random token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest.

    Refresh tokens are already high-entropy random strings (64 bytes → 512 bits),
    so SHA-256 is sufficient without key-stretching (bcrypt/argon2). This keeps
    lookup fast — token_hash is queried on every refresh request.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()
