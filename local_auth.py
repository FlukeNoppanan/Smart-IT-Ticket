"""Local credential handling, separate from ticket authorization."""
import hashlib
import hmac
import re
import secrets

class AuthError(ValueError):
    pass

def validate_username(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,31}', value):
        raise AuthError('Username ต้องยาว 3–32 ตัว และใช้ a-z, 0-9, _, ., -')
    return value

def validate_email(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value) or len(value) > 254:
        raise AuthError('รูปแบบ email ไม่ถูกต้อง')
    return value

def validate_password(value):
    if len(value) < 12 or len(value) > 1024:
        raise AuthError('Password ต้องยาวอย่างน้อย 12 ตัวอักษร')

def hash_password(password):
    validate_password(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f'scrypt$16384$8$1${salt.hex()}${digest.hex()}'

def verify_password(password, encoded):
    try:
        algorithm, n, r, p, salt, digest = encoded.split('$')
        if algorithm != 'scrypt' or (n, r, p) != ('16384', '8', '1'):
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, AttributeError, TypeError):
        return False
