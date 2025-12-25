import os
import socket
import datetime
import json
import base64
import io
import hashlib
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import qrcode

CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"

def get_local_ip():
    """Attempts to determine the local IP address of the machine."""
    try:
        # We use a UDP socket to determine the interface IP used for outgoing connections.
        # connecting to a public DNS server (Google's 8.8.8.8) doesn't actually send a packet
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def generate_self_signed_cert(ip_address, cert_path=CERT_FILE, key_path=KEY_FILE):
    """Generates a self-signed certificate with the given IP in the SAN field."""
    print(f"Generating new self-signed certificate for {ip_address}...")

    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Generate public key
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Rachel Module Creator"),
        x509.NameAttribute(NameOID.COMMON_NAME, str(ip_address)),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        # Valid for 10 years
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650)
    ).add_extension(
        x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip_address))]),
        critical=False,
    ).sign(key, hashes.SHA256(), default_backend())

    # Write key to file
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Write cert to file
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    return cert

def get_cert_fingerprint(cert_path=CERT_FILE):
    """Calculates the SHA-256 fingerprint of the certificate."""
    with open(cert_path, "rb") as f:
        cert_data = f.read()
        cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        # The app likely expects the hex digest of the DER encoding, or the PEM bytes?
        # Standard fingerprint is usually hash of DER.
        # User said: "Extract Fingerprint: Calculate the SHA-256 hash of your certificate."
        # Usually this means SHA256(DER).

        digest = cert.fingerprint(hashes.SHA256())
        # Convert to colon-separated hex string
        return ":".join(f"{b:02X}" for b in digest)

def check_and_renew_cert(ip_address, cert_path=CERT_FILE, key_path=KEY_FILE):
    """
    Checks if the certificate exists and if the SAN matches the current IP.
    If not, regenerates it.
    """
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        generate_self_signed_cert(ip_address, cert_path, key_path)
        return

    # Check if existing cert matches IP
    with open(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Check SAN
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        ips = san.value.get_values_for_type(x509.IPAddress)
        # Check if our current IP is in the list
        # socket.inet_aton returns bytes, x509.IPAddress returns IPv4Address object
        current_ip_obj = ipaddress.ip_address(ip_address)

        if current_ip_obj not in ips:
            print(f"Certificate IP mismatch ({ips} vs {ip_address}). Regenerating...")
            generate_self_signed_cert(ip_address, cert_path, key_path)
    except x509.ExtensionNotFound:
        print("Certificate missing SAN. Regenerating...")
        generate_self_signed_cert(ip_address, cert_path, key_path)

def generate_qr_code_image(ip, port, fingerprint):
    """Generates a base64 encoded PNG image of the QR code."""
    data = {
        "ip": ip,
        "port": port,
        "hash": fingerprint
    }
    json_payload = json.dumps(data)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json_payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")
