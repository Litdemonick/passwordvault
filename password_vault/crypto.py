import base64
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.fernet import Fernet

def derive_key(master_password: str, salt: bytes) -> bytes:
    """Devuelve una clave de 32 bytes base64-url (necesaria para Fernet)."""
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    key = kdf.derive(master_password.encode("utf-8"))
    return base64.urlsafe_b64encode(key)

def make_verifier(derived_key: bytes) -> bytes:
    h = hmac.HMAC(base64.urlsafe_b64decode(derived_key), hashes.SHA256())
    h.update(b"verify")
    return h.finalize()

def verify_master(derived_key: bytes, verifier: bytes) -> bool:
    try:
        h = hmac.HMAC(base64.urlsafe_b64decode(derived_key), hashes.SHA256())
        h.update(b"verify")
        h.verify(verifier)
        return True
    except Exception:
        return False

def encrypt_text(derived_key: bytes, plaintext: str) -> bytes:
    f = Fernet(derived_key)
    return f.encrypt(plaintext.encode("utf-8"))

def decrypt_text(derived_key: bytes, ciphertext: bytes) -> str:
    f = Fernet(derived_key)
    return f.decrypt(ciphertext).decode("utf-8")
