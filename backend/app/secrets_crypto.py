"""Secrets encryption module.

Encrypts sensitive values in .env file using Fernet symmetric encryption.
Key is derived from a master password or auto-generated.

Usage:
    python -m app.secrets_crypto encrypt .env        # Encrypt secrets in .env
    python -m app.secrets_crypto decrypt .env        # Decrypt secrets in .env
    python -m app.secrets_crypto generate-key         # Generate a new key
"""

import base64
import hashlib
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


SALT = b"aegis-ai-salt-2026"
ENCRYPTED_PREFIX = "ENC:"
KEY_ENV_VAR = "AEGIS_MASTER_KEY"


def derive_key(master_password: str) -> bytes:
    """Derive a Fernet key from a master password."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(master_password.encode()))


def generate_key() -> str:
    """Generate a random Fernet key."""
    return Fernet.generate_key().decode()


def encrypt_value(value: str, key: str) -> str:
    """Encrypt a single value."""
    f = Fernet(key.encode() if isinstance(key, str) else key)
    encrypted = f.encrypt(value.encode())
    return ENCRYPTED_PREFIX + base64.urlsafe_b64encode(encrypted).decode()


def decrypt_value(encrypted_value: str, key: str) -> str:
    """Decrypt a single value."""
    if not encrypted_value.startswith(ENCRYPTED_PREFIX):
        return encrypted_value
    f = Fernet(key.encode() if isinstance(key, str) else key)
    raw = base64.urlsafe_b64decode(encrypted_value[len(ENCRYPTED_PREFIX):])
    return f.decrypt(raw).decode()


def encrypt_env_file(filepath: str, key: str) -> int:
    """Encrypt all secret values in a .env file. Returns count of encrypted values."""
    path = Path(filepath)
    lines = path.read_text().splitlines(keepends=True)
    count = 0
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        if "=" in stripped:
            var_name, _, value = stripped.partition("=")
            value = value.strip().strip('"').strip("'")

            if value.startswith(ENCRYPTED_PREFIX):
                new_lines.append(line)
                continue

            if var_name in (
                "AEGIS_ADMIN_TOKEN", "VITE_ADMIN_TOKEN",
                "BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_API_SECRET",
                "OPENCODE_API_KEY", "OPENROUTER_API_KEY",
                "FINNHUB_API_KEY", "TELEGRAM_BOT_TOKEN",
                "LIVE_API_KEY", "LIVE_API_SECRET",
            ) and value:
                encrypted = encrypt_value(value, key)
                new_lines.append(f'{var_name}="{encrypted}"\n')
                count += 1
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    path.write_text("".join(new_lines))
    return count


def decrypt_env_file(filepath: str, key: str) -> int:
    """Decrypt all encrypted values in a .env file. Returns count of decrypted values."""
    path = Path(filepath)
    lines = path.read_text().splitlines(keepends=True)
    count = 0
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        if "=" in stripped:
            var_name, _, value = stripped.partition("=")
            value = value.strip().strip('"').strip("'")

            if value.startswith(ENCRYPTED_PREFIX):
                try:
                    decrypted = decrypt_value(value, key)
                    new_lines.append(f'{var_name}="{decrypted}"\n')
                    count += 1
                except Exception:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    path.write_text("".join(new_lines))
    return count


def get_key() -> str | None:
    """Get the encryption key from env or .aegis_key file."""
    key = os.environ.get(KEY_ENV_VAR)
    if key:
        return key

    key_file = Path(__file__).resolve().parent.parent.parent / ".aegis_key"
    if key_file.exists():
        return key_file.read_text().strip()

    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.secrets_crypto [encrypt|decrypt|generate-key] [file]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate-key":
        key = generate_key()
        print(f"Key: {key}")
        key_file = Path(__file__).resolve().parent.parent.parent / ".aegis_key"
        key_file.write_text(key)
        print(f"Saved to {key_file}")
        sys.exit(0)

    if len(sys.argv) < 3:
        print("Usage: python -m app.secrets_crypto [encrypt|decrypt] <env_file>")
        sys.exit(1)

    filepath = sys.argv[2]
    key = get_key()
    if not key:
        print("Error: No encryption key found. Set AEGIS_MASTER_KEY or run generate-key first.")
        sys.exit(1)

    if command == "encrypt":
        count = encrypt_env_file(filepath, key)
        print(f"Encrypted {count} values in {filepath}")
    elif command == "decrypt":
        count = decrypt_env_file(filepath, key)
        print(f"Decrypted {count} values in {filepath}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
