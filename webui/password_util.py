"""Web 登录密码哈希（全模块复用，避免 dal / api 各写一套）。"""
from __future__ import annotations

import hashlib
import secrets


def hash_password(plain: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt.encode("utf-8"), 120_000
    )
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, salt, hexdigest = stored.split("$", 2)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), salt.encode("utf-8"), 120_000
        )
        return digest.hex() == hexdigest
    # 迁移期：库内仍是明文时允许登录并在成功路径上升级为哈希
    return plain == stored


def needs_rehash(stored: str) -> bool:
    return not stored.startswith("pbkdf2_sha256$")
