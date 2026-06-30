import logging
from functools import lru_cache

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from app.config import settings
from app.core.exceptions import InvalidFirebaseTokenError, MissingPhoneNumberError

logger = logging.getLogger(__name__)


def _init_firebase_app() -> firebase_admin.App:
    if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
        return firebase_admin.get_app()
    cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    return firebase_admin.initialize_app(cred)


class FirebaseService:
    """Wraps Firebase Admin Auth.

    phone_number is ALWAYS sourced from the verified Firebase ID token claim.
    It must never be accepted as client-supplied input — the client sends only
    the Firebase ID token; the phone number is extracted here server-side.
    """

    def verify_id_token(self, id_token: str) -> dict:
        """Verify Firebase ID token and return a normalised dict.

        Returns:
            {
                "uid": str,
                "phone_number": str,   # E.164, from Firebase claim
            }

        Raises:
            InvalidFirebaseTokenError — token invalid, expired, or revoked.
            MissingPhoneNumberError   — token valid but has no phone_number claim
                                        (e.g. email/password provider used by mistake).
        """
        try:
            _init_firebase_app()
            decoded = firebase_auth.verify_id_token(id_token, check_revoked=True)
        except firebase_admin.exceptions.FirebaseError as exc:
            logger.warning("Firebase token verification failed: %s", exc)
            raise InvalidFirebaseTokenError() from exc

        phone_number: str | None = decoded.get("phone_number")
        if not phone_number:
            raise MissingPhoneNumberError()

        return {
            "uid": decoded["uid"],
            "phone_number": phone_number,
        }


@lru_cache(maxsize=1)
def get_firebase_service() -> FirebaseService:
    return FirebaseService()
