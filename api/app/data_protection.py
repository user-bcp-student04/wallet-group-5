import base64
import hashlib
import hmac
import os
from pathlib import Path

from cryptography.fernet import Fernet


DATA_KEY_ENV = "ONBOARDING_DATA_KEY"
KEY_FILE_NAME = "onboarding.key"
HASH_PURPOSE = b"onboarding-document-hash"


class DocumentProtector:
    """Cifra el documento en reposo y deriva un valor con clave para la restricción de unicidad."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)
        self._hash_key = hmac.new(base64.urlsafe_b64decode(key), HASH_PURPOSE, hashlib.sha256).digest()

    @classmethod
    def from_environment(cls, data_directory: Path) -> "DocumentProtector":
        configured = os.getenv(DATA_KEY_ENV, "").strip()
        if configured:
            return cls(configured.encode("ascii"))
        return cls(_load_or_create_key(data_directory / KEY_FILE_NAME))

    def encrypt(self, document: str) -> str:
        return self._fernet.encrypt(document.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")

    def fingerprint(self, document_type: str, document: str) -> str:
        message = f"{document_type}:{document}".encode("utf-8")
        return hmac.new(self._hash_key, message, hashlib.sha256).hexdigest()

    def digest(self, purpose: str, value: str) -> str:
        message = f"{purpose}:{value}".encode("utf-8")
        return hmac.new(self._hash_key, message, hashlib.sha256).hexdigest()


# Sin clave configurada se genera una local junto a la base (fuera de Git) para no guardar un valor fijo en el código.
def _load_or_create_key(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(key)
    return key
