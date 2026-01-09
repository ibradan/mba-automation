import os
from cryptography.fernet import Fernet
import logging

KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'secret.key')
logger = logging.getLogger(__name__)

def load_key():
    """Load the existing key or generate a new one if missing/invalid."""
    def generate_and_save():
        k = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as f:
            f.write(k)
        logger.info(f"Generated new encryption key at {KEY_FILE}")
        return k

    if not os.path.exists(KEY_FILE):
        return generate_and_save()
    
    try:
        with open(KEY_FILE, 'rb') as key_file:
            key = key_file.read()
            if not key or len(key) < 10: # Basic validation
                logger.warning("Key file is empty or too short. Regenerating.")
                return generate_and_save()
            # Validate key format
            Fernet(key)
            return key
    except Exception as e:
        logger.error(f"Invalid key file ({e}). Regenerating.")
        return generate_and_save()

# Initialize Cipher
cipher = Fernet(load_key())

def encrypt_password(password: str) -> str:
    """Encrypt a plaintext password."""
    if not password:
        return ""
    try:
        # If it's already encrypted (starts with gAAAA), return as is (idempotency check rough)
        # However, re-encrypting is safer unless we are sure. 
        # Fernet tokens start with gAAAA. 
        # But a user password *could* start with that technically.
        # We will assume caller handles this or we just double encrypt (which isn't ideal but safe).
        # Better approach: The backend handles the state.
        return cipher.encrypt(password.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return password

def decrypt_password(token: str) -> str:
    """Decrypt a token. Returns original text if decryption fails (graceful migration)."""
    if not token:
        return ""
    try:
        return cipher.decrypt(token.encode()).decode()
    except Exception:
        # This handles the case where the password in JSON is still plain text
        # or the key changed. We return the raw token to allow potential migration
        # or manual recovery.
        return token
