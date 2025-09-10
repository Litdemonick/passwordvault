import os
from password_vault.crypto import (
    derive_key, make_verifier, verify_master,
    encrypt_text, decrypt_text
)

def test_kdf_and_verify_and_roundtrip():
    salt = b"\x00" * 16
    key = derive_key("Secret@123", salt)
    assert isinstance(key, bytes)

    ver = make_verifier(key)
    assert verify_master(key, ver) is True

    ct = encrypt_text(key, "hola-mundo")
    pt = decrypt_text(key, ct)
    assert pt == "hola-mundo"
