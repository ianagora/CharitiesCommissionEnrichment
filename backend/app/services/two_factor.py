"""Two-Factor Authentication service."""
import pyotp
import qrcode
import io
import base64
import secrets
import json
from typing import Optional, List, Tuple


class TwoFactorService:
    """Service for handling 2FA operations."""
    
    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret."""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """Generate backup codes for 2FA recovery."""
        return [secrets.token_hex(4).upper() for _ in range(count)]
    
    @staticmethod
    def get_totp_uri(secret: str, email: str, issuer: str = "Charity Commission Data Enrichment") -> str:
        """Get the provisioning URI for QR code generation."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=issuer)
    
    @staticmethod
    def generate_qr_code(uri: str) -> str:
        """Generate QR code as base64 image."""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_base64}"
    
    @staticmethod
    def verify_totp(secret: str, token: str, window: int = 1) -> bool:
        """
        Verify a TOTP token.
        
        Args:
            secret: The user's TOTP secret
            token: The 6-digit code from authenticator app
            window: Number of time steps to check (default 1 = 30 seconds before/after)
        
        Returns:
            True if valid, False otherwise
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=window)
    
    @staticmethod
    def verify_backup_code(stored_codes_json: str, provided_code: str) -> Tuple[bool, Optional[str]]:
        """
        Verify a backup code and remove it from the list.
        
        Args:
            stored_codes_json: JSON string of backup codes
            provided_code: The backup code provided by user
        
        Returns:
            Tuple of (is_valid, updated_codes_json)
        """
        try:
            codes = json.loads(stored_codes_json)
            provided_code_upper = provided_code.upper().strip()
            
            if provided_code_upper in codes:
                codes.remove(provided_code_upper)
                return True, json.dumps(codes)
            
            return False, None
        except (json.JSONDecodeError, ValueError):
            return False, None
    
    @staticmethod
    def setup_2fa(email: str) -> dict:
        """
        Set up 2FA for a user.
        
        Returns:
            Dictionary with secret, qr_code, and backup_codes
        """
        secret = TwoFactorService.generate_secret()
        uri = TwoFactorService.get_totp_uri(secret, email)
        qr_code = TwoFactorService.generate_qr_code(uri)
        backup_codes = TwoFactorService.generate_backup_codes()
        
        return {
            "secret": secret,
            "qr_code": qr_code,
            "backup_codes": backup_codes,
            "backup_codes_json": json.dumps(backup_codes)
        }
