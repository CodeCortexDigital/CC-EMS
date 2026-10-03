"""Make a VAPID key pair for web push and print the three environment lines to set on the server."""
import base64

from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand
from py_vapid import Vapid


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


class Command(BaseCommand):
    help = 'Create a VAPID key pair for web push notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--contact', default='mailto:admin@example.com', help='Address push services can reach (mailto:...).')

    def handle(self, *args, **options):
        vapid = Vapid()
        vapid.generate_keys()
        private = b64(vapid.private_key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        public = b64(vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
        self.stdout.write('Set these on the server (keep the private key secret; never put it in the frontend):\n')
        self.stdout.write(f'VAPID_PUBLIC_KEY={public}')
        self.stdout.write(f'VAPID_PRIVATE_KEY={private}')
        self.stdout.write(f'VAPID_CONTACT={options["contact"]}')
