"""Bedrock WS encryption: P-384 ECDH, SHA256(salt || X), continuous AES-CFB8.

Protocol reference: https://github.com/sandertv/mcwss (MIT), encryption.go and
protocol/command/enable_encryption.go. Uses cryptography's primitives, not custom ciphers.
"""
import base64
import hashlib
import secrets
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.decrepit.ciphers.modes import CFB8


class GameEncryption:
    def __init__(self):
        self.private = ec.generate_private_key(ec.SECP384R1())
        self.salt = secrets.token_bytes(16)
        self.encoder = self.decoder = None

    def command(self):
        public = self.private.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        encode = lambda data: base64.b64encode(data).decode().rstrip('=')
        return f'enableencryption "{encode(public)}" "{encode(self.salt)}"'

    def accept(self, public_key):
        public = serialization.load_der_public_key(base64.b64decode(public_key + '=' * (-len(public_key) % 4)))
        if not isinstance(public, ec.EllipticCurvePublicKey) or not isinstance(public.curve, ec.SECP384R1):
            raise ValueError('Chave ECDH do jogo inválida')
        shared = self.private.exchange(ec.ECDH(), public).lstrip(b'\x00')
        key = hashlib.sha256(self.salt + shared).digest()
        cipher = Cipher(algorithms.AES(key), CFB8(key[:16]))
        self.encoder, self.decoder = cipher.encryptor(), cipher.decryptor()

    def encode(self, data):
        return self.encoder.update(data) if self.encoder else data

    def decode(self, data):
        return self.decoder.update(data) if self.decoder else data
