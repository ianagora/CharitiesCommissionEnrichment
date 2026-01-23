# Security Enhancements - User Guide

## Overview
This application now includes enterprise-grade security features:
- ✅ **Two-Factor Authentication (2FA)** using TOTP
- ✅ **Rate Limiting** with visible headers
- ✅ **CAPTCHA Protection** (integrated with rate limiting)

---

## 1. Two-Factor Authentication (2FA)

### Setup 2FA (Users)
1. **Login** to your account
2. Navigate to **Account Settings** or call API:
   ```bash
   POST /api/v1/auth/2fa/setup
   Authorization: Bearer YOUR_ACCESS_TOKEN
   ```
3. **Response** will include:
   - QR code (scan with Google Authenticator, Authy, or similar)
   - 10 backup codes (save these securely!)

4. **Verify** and enable 2FA:
   ```bash
   POST /api/v1/auth/2fa/verify
   {
     "token": "123456"  # 6-digit code from authenticator app
   }
   ```

### Login with 2FA
```bash
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "YourPassword123!",
  "totp_code": "123456"  # Add this field if 2FA is enabled
}
```

### Disable 2FA
```bash
POST /api/v1/auth/2fa/disable
{
  "password": "YourPassword123!",
  "token": "123456"  # TOTP code or backup code
}
```

### Backup Codes
- You receive 10 backup codes during setup
- Each code can only be used once
- Use them if you lose access to your authenticator app
- Store them securely (password manager, encrypted file)

---

## 2. Rate Limiting

### Visible Rate Limit Headers
All API responses include rate limit information:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1706019600
```

### Rate Limits by Endpoint

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/auth/login` | 5 requests | per minute |
| `/auth/register` | 5 requests | per minute |
| `/api/*` (general) | 60 requests | per minute |
| `/batches/upload` | 10 requests | per minute |
| Global default | 100 requests | per minute |

### Account Lockout
- **5 failed login attempts** → Account locked for 15 minutes
- Lockout applies per IP address + email combination
- Prevents brute force attacks

---

## 3. User Management

### Add New Users (Admin)

**Option 1: Using the management script**
```bash
cd backend
python scripts/manage_users.py add-user \
  --email newuser@example.com \
  --password "SecurePass123!" \
  --name "John Doe"
```

**Option 2: Make existing user a superuser**
```bash
python scripts/manage_users.py make-superuser \
  --email user@example.com
```

**Option 3: List all users**
```bash
python scripts/manage_users.py list-users
```

**Option 4: Disable/Enable users**
```bash
python scripts/manage_users.py disable-user --email user@example.com
python scripts/manage_users.py enable-user --email user@example.com
```

### User Registration (Self-Service)
Users can register themselves via:
```bash
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe",
  "organization": "Acme Corp"
}
```

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character (!@#$%^&*...)

---

## 4. Security Best Practices

### For Administrators
1. ✅ **Enable 2FA** on all admin accounts
2. ✅ **Use strong passwords** (12+ characters)
3. ✅ **Monitor rate limit violations** in logs
4. ✅ **Regularly review user accounts** (disable inactive users)
5. ✅ **Keep backup codes secure** (encrypted storage)

### For End Users
1. ✅ **Enable 2FA** for your account
2. ✅ **Store backup codes** in a password manager
3. ✅ **Don't share credentials**
4. ✅ **Use unique passwords** (not reused elsewhere)
5. ✅ **Log out** from shared devices

---

## 5. API Security Headers

All responses include CREST-compliant security headers:

```
Content-Security-Policy: default-src 'self'; script-src 'self' ...
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()...
Cross-Origin-Opener-Policy: same-origin-allow-popups
Cross-Origin-Resource-Policy: cross-origin
```

---

## 6. Migration Guide

### Applying 2FA Database Changes
```bash
cd backend
alembic upgrade head
```

This will:
- Add `two_factor_enabled` column
- Add `two_factor_secret` column
- Add `backup_codes` column

### Rolling Back (if needed)
```bash
alembic downgrade -1
```

---

## 7. Troubleshooting

### "2FA code required" Error
- Ensure you're sending `totp_code` in login request
- Check that the code is current (TOTP codes expire every 30 seconds)
- Try a backup code if authenticator app is unavailable

### "Account temporarily locked" Error
- Wait 15 minutes or contact administrator
- This happens after 5 failed login attempts
- Prevents brute force attacks

### "Invalid 2FA code" Error
- Ensure your device clock is accurate (TOTP is time-based)
- Try the next code from your authenticator
- Use a backup code as fallback

### Rate Limit Exceeded
- Check `X-RateLimit-Reset` header for reset time
- Wait until the window resets
- Contact admin if you need higher limits

---

## 8. Example Workflows

### Complete User Onboarding
```bash
# 1. Register
curl -X POST https://your-api.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "full_name": "Jane Doe"
  }'

# 2. Login (get access token)
curl -X POST https://your-api.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'

# 3. Setup 2FA
curl -X POST https://your-api.com/api/v1/auth/2fa/setup \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 4. Verify 2FA (enable it)
curl -X POST https://your-api.com/api/v1/auth/2fa/verify \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token": "123456"}'

# 5. Future logins require 2FA code
curl -X POST https://your-api.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "totp_code": "123456"
  }'
```

---

## 9. Security Audit Checklist

- [x] 2FA implementation (TOTP with backup codes)
- [x] Rate limiting on all endpoints
- [x] Visible rate limit headers
- [x] Account lockout after failed attempts
- [x] Strong password requirements
- [x] JWT token rotation
- [x] CREST-compliant security headers
- [x] HTTPS enforcement (HSTS)
- [x] CVE remediation (0 HIGH vulnerabilities)
- [x] Input validation
- [x] SQL injection protection (ORM)
- [x] XSS protection (CSP)
- [x] Clickjacking protection (X-Frame-Options)

---

## Contact & Support
For security issues or questions, contact the development team.

**Version:** 2.0.0 (Security Enhanced)  
**Last Updated:** 2026-01-23
