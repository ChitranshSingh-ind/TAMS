"""
Official Meta WhatsApp Business Cloud API Provider for TAMS.
Handles environment separation (Development test sender vs Production),
secure credential storage, phone number E.164 normalization, template mapping,
transient vs permanent error classification, and diagnostic logging without secrets.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.database.connection import DATA_DIR

logger = logging.getLogger("TAMS.WhatsAppProvider")

# Default Meta Graph API version
DEFAULT_GRAPH_API_VERSION = "v21.0"
META_GRAPH_BASE_URL = "https://graph.facebook.com"

# Secure credential storage file with 0600 permissions
CREDENTIALS_FILE = DATA_DIR / ".whatsapp_credentials"


# ─────────────────────────────────────────────────────────────────────────────
# 1. SECURE TOKEN STORAGE (Zero external dependency with strict permissions)
# ─────────────────────────────────────────────────────────────────────────────

def _obfuscate(text: str) -> str:
    """Lightweight host/user-bound obfuscation for local credential persistence."""
    user = os.getenv("USERNAME", os.getenv("USER", "tams"))
    salt = f"TAMS_{user}_{socket.gethostname()}"
    salt_bytes = salt.encode("utf-8")
    text_bytes = text.encode("utf-8")
    masked = bytes([b ^ salt_bytes[i % len(salt_bytes)] for i, b in enumerate(text_bytes)])
    return base64.b64encode(masked).decode("ascii")


def _deobfuscate(encoded: str) -> str:
    try:
        user = os.getenv("USERNAME", os.getenv("USER", "tams"))
        salt = f"TAMS_{user}_{socket.gethostname()}"
        salt_bytes = salt.encode("utf-8")
        raw = base64.b64decode(encoded.encode("ascii"))
        original = bytes([b ^ salt_bytes[i % len(salt_bytes)] for i, b in enumerate(raw)])
        return original.decode("utf-8")
    except Exception:
        return ""


def save_access_token(token: str) -> bool:
    """Saves access token to restricted local credentials store (0600 permissions)."""
    clean = token.strip()
    if not clean:
        remove_access_token()
        return True
    try:
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        encoded = _obfuscate(clean)
        # Write with restrictive permissions
        fd = os.open(CREDENTIALS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(encoded)
        return True
    except Exception as e:
        logger.error("Failed to safely save WhatsApp access token: %s", type(e).__name__)
        return False


def get_access_token() -> str | None:
    """Retrieves access token from credentials store, returning None if missing."""
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        with open(CREDENTIALS_FILE, "r") as f:
            encoded = f.read().strip()
        val = _deobfuscate(encoded)
        return val if val else None
    except Exception as e:
        logger.error("Failed to read WhatsApp access token: %s", type(e).__name__)
        return None


def remove_access_token() -> bool:
    """Removes stored access token securely."""
    try:
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()
        return True
    except Exception:
        return False


def mask_token(token: str | None) -> str:
    """
    Returns masked representation of a token (e.g. 'EAAB...wxyz' or '••••••••').
    Never reveals the token body in logs, UI, or exports.
    """
    if not token or len(token) < 8:
        return "Not Configured"
    return f"{token[:4]}...{token[-4:]} ({len(token)} chars)"


# ─────────────────────────────────────────────────────────────────────────────
# 2. PHONE NUMBER NORMALIZATION & VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def normalize_phone_number(raw_phone: str | None, default_country_code: str = "91") -> tuple[bool, str, str]:
    """
    Normalizes contact phone number to E.164 standard without spaces, dashes, or leading zeros.
    Returns: (is_valid: bool, e164_number: str, error_reason: str)
    """
    if not raw_phone:
        return False, "", "Phone number is empty or missing"

    # Strip formatting characters: spaces, dashes, parentheses, dots
    cleaned = re.sub(r"[\s\-\(\)\.]", "", str(raw_phone).strip())

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    else:
        digits = cleaned

    if not digits.isdigit():
        return False, "", "Phone number contains non-numeric characters"

    # Handle Indian mobile numbers (10 digits)
    if default_country_code == "91":
        if len(digits) == 10:
            digits = f"91{digits}"
        elif len(digits) == 11 and digits.startswith("0"):
            digits = f"91{digits[1:]}"
        elif len(digits) == 12 and digits.startswith("91"):
            pass  # Already formatted
        elif len(digits) < 10:
            return False, "", f"Phone number has only {len(digits)} digits (requires minimum 10)"
    else:
        if len(digits) < 10 or len(digits) > 15:
            return False, "", f"Invalid phone number length ({len(digits)} digits; E.164 requires 10-15)"

    if len(digits) < 10 or len(digits) > 15:
        return False, "", f"Invalid E.164 phone number length ({len(digits)} digits)"

    e164 = f"+{digits}"
    return True, e164, ""


def mask_phone_number(phone: str | None) -> str:
    """Masks phone number for safe privacy display: e.g. '+91 98*** **321'."""
    if not phone:
        return "—"
    clean = phone.strip()
    if len(clean) >= 10:
        return f"{clean[:5]}*** **{clean[-3:]}"
    return f"{clean[:2]}***{clean[-2:]}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. STRUCTURED DATA MODELS & ERROR CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WhatsAppConfig:
    environment: str = "DEVELOPMENT"  # "DEVELOPMENT" or "PRODUCTION"
    phone_number_id: str = ""
    waba_id: str = ""
    api_version: str = DEFAULT_GRAPH_API_VERSION
    access_token: str = ""


@dataclass
class WhatsAppSendResult:
    success: bool
    status: str  # ACCEPTED, FAILED, RETRYABLE_FAILURE
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    is_retryable: bool = False
    is_ambiguous: bool = False  # True when network timeout occurred after POST (outcome uncertain)
    http_status: int = 0
    raw_response: dict | None = None


# Classification of Meta Graph API errors
PERMANENT_ERROR_CODES = {
    100,     # Invalid parameter / Bad Request
    190,     # Access token expired / invalid
    131000,  # Message failed to send
    131005,  # Access denied
    131008,  # Required parameter missing
    131009,  # Parameter value is not valid
    131026,  # Message undeliverable (e.g. recipient not on WhatsApp)
    131047,  # Re-engagement message required (24hr window expired)
    132000,  # Template does not exist
    132001,  # Template parameter count mismatch
    132005,  # Template hydrations failed
    132015,  # Template paused / disabled
}

RETRYABLE_ERROR_CODES = {
    -1,      # Network timeout / connection dropped
    500,     # Internal server error
    502,     # Bad gateway
    503,     # Service unavailable
    504,     # Gateway timeout
    80007,   # Rate limit reached
    130429,  # WhatsApp Cloud API rate limit
    131016,  # Service temporarily unavailable
    131051,  # Unsupported message type (temporary provider sync)
    131052,  # Media download error (temporary)
}


def is_retryable_whatsapp_error(http_status: int, meta_code: int | None) -> bool:
    """Determines whether a failure is transient and eligible for bounded backoff retry."""
    if http_status in (408, 429, 500, 502, 503, 504):
        return True
    if meta_code in RETRYABLE_ERROR_CODES:
        return True
    if meta_code in PERMANENT_ERROR_CODES:
        return False
    # If HTTP 400 with unknown code, default to permanent to prevent message storm
    if http_status in (400, 401, 403, 404):
        return False
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 4. OFFICIAL META WHATSAPP CLOUD API CLIENT
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppCloudProvider:
    """
    Communicates with Meta WhatsApp Business Platform Cloud API over HTTPS.
    Uses standard library urllib (no external dependency), handles timeouts,
    sanitizes logs, and safely classifies outcomes.
    """

    def __init__(self, config: WhatsAppConfig | None = None):
        self.config = config or WhatsAppConfig()

    def _get_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "TAMS-Desktop/2.0 WhatsAppProvider",
        }

    def test_connection(self) -> dict[str, Any]:
        """
        Validates token, Phone Number ID, and business account with Meta Graph API
        without sending a message. Returns verified name, display phone, and quality rating.
        """
        token = self.config.access_token or get_access_token()
        if not token:
            return {
                "success": False,
                "status_code": 0,
                "error": "Access token is missing. Please enter your Meta WhatsApp access token.",
                "quality_rating": "UNKNOWN",
            }

        phone_number_id = self.config.phone_number_id.strip()
        if not phone_number_id:
            return {
                "success": False,
                "status_code": 0,
                "error": "Phone Number ID is missing. Please enter your Meta Phone Number ID.",
                "quality_rating": "UNKNOWN",
            }

        version = self.config.api_version or DEFAULT_GRAPH_API_VERSION
        url = f"{META_GRAPH_BASE_URL}/{version}/{phone_number_id}?fields=id,verified_name,display_phone_number,quality_rating,code_verification_status"

        req = urllib.request.Request(url, headers=self._get_headers(token), method="GET")

        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=12, context=ctx) as response:
                status = response.status
                body = response.read().decode("utf-8")
                data = json.loads(body)

                return {
                    "success": True,
                    "status_code": status,
                    "phone_number_id": data.get("id", phone_number_id),
                    "verified_name": data.get("verified_name", "Meta Test Account"),
                    "display_phone_number": data.get("display_phone_number", "—"),
                    "quality_rating": data.get("quality_rating", "GREEN"),
                    "environment": self.config.environment,
                    "tested_at": datetime.now(timezone.utc).strftime("%d %b %Y %H:%M:%S UTC"),
                    "error": None,
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            meta_err_msg = ""
            try:
                err_json = json.loads(err_body)
                meta_err = err_json.get("error", {})
                meta_err_msg = meta_err.get("message", "")
                err_code = meta_err.get("code", e.code)
            except Exception:
                err_code = e.code
                meta_err_msg = err_body

            if e.code == 401 or err_code == 190:
                msg = f"Authentication failed (HTTP {e.code}): Access token is invalid or expired. Please generate a new token in Meta Developer Portal."
            elif e.code == 404:
                msg = f"Phone Number ID not found (HTTP 404): Check Phone Number ID '{phone_number_id}'."
            else:
                msg = f"Meta API Error (HTTP {e.code}, Code {err_code}): {meta_err_msg}"

            return {
                "success": False,
                "status_code": e.code,
                "error": msg,
                "quality_rating": "UNKNOWN",
            }
        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            return {
                "success": False,
                "status_code": 0,
                "error": f"Network unavailable or connection timed out: {e.reason if hasattr(e, 'reason') else str(e)}",
                "quality_rating": "UNKNOWN",
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": 0,
                "error": f"Unexpected error during connection test: {type(e).__name__} - {e}",
                "quality_rating": "UNKNOWN",
            }

    def send_template_message(
        self,
        *,
        recipient_phone: str,
        template_name: str,
        language_code: str = "en",
        parameters: list[str] | None = None,
    ) -> WhatsAppSendResult:
        """
        Sends an approved Meta WhatsApp template message (e.g. 'hello_world' or parameterized template).
        """
        token = self.config.access_token or get_access_token()
        if not token:
            return WhatsAppSendResult(
                success=False,
                status="FAILED",
                error_code="MISSING_TOKEN",
                error_message="Meta access token is not configured.",
                is_retryable=False,
            )

        phone_number_id = self.config.phone_number_id.strip()
        if not phone_number_id:
            return WhatsAppSendResult(
                success=False,
                status="FAILED",
                error_code="MISSING_PHONE_ID",
                error_message="WhatsApp Phone Number ID is not configured.",
                is_retryable=False,
            )

        # Normalize phone number
        is_valid, e164_phone, reason = normalize_phone_number(recipient_phone)
        if not is_valid:
            return WhatsAppSendResult(
                success=False,
                status="FAILED",
                error_code="INVALID_PHONE",
                error_message=f"Recipient phone number invalid: {reason}",
                is_retryable=False,
            )

        # Meta expects recipient without '+' prefix: e.g. "919876543210"
        recipient_to = e164_phone.lstrip("+")

        # Assemble template components
        template_obj: dict[str, Any] = {
            "name": template_name.strip(),
            "language": {"code": language_code.strip() or "en"},
        }

        if parameters:
            param_components = [
                {"type": "text", "text": str(p)}
                for p in parameters
            ]
            template_obj["components"] = [
                {
                    "type": "body",
                    "parameters": param_components,
                }
            ]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_to,
            "type": "template",
            "template": template_obj,
        }

        return self._post_message(payload, token, phone_number_id)

    def send_text_message(
        self,
        *,
        recipient_phone: str,
        message_body: str,
    ) -> WhatsAppSendResult:
        """
        Sends free-form text message (applicable within 24hr customer service window).
        """
        token = self.config.access_token or get_access_token()
        if not token:
            return WhatsAppSendResult(
                success=False,
                status="FAILED",
                error_code="MISSING_TOKEN",
                error_message="Meta access token is not configured.",
                is_retryable=False,
            )

        phone_number_id = self.config.phone_number_id.strip()
        if not phone_number_id:
            return WhatsAppSendResult(
                success=False,
                status="FAILED",
                error_code="MISSING_PHONE_ID",
                error_message="WhatsApp Phone Number ID is not configured.",
                is_retryable=False,
            )

        is_valid, e164_phone, reason = normalize_phone_number(recipient_phone)
        if not is_valid:
            return WhatsAppSendResult(
                success=False,
                status="FAILED",
                error_code="INVALID_PHONE",
                error_message=f"Recipient phone number invalid: {reason}",
                is_retryable=False,
            )

        recipient_to = e164_phone.lstrip("+")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message_body.strip(),
            },
        }

        return self._post_message(payload, token, phone_number_id)

    def _post_message(self, payload: dict, token: str, phone_number_id: str) -> WhatsAppSendResult:
        version = self.config.api_version or DEFAULT_GRAPH_API_VERSION
        url = f"{META_GRAPH_BASE_URL}/{version}/{phone_number_id}/messages"

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers=self._get_headers(token),
            method="POST",
        )

        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
                status_code = response.status
                body = response.read().decode("utf-8")
                res_json = json.loads(body)

                messages = res_json.get("messages", [])
                provider_msg_id = messages[0].get("id") if messages else None

                return WhatsAppSendResult(
                    success=True,
                    status="ACCEPTED",  # Accepted by Meta HTTP API (delivery depends on webhook confirmation)
                    provider_message_id=provider_msg_id,
                    http_status=status_code,
                    raw_response=res_json,
                )

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            meta_code = None
            meta_err_msg = ""
            try:
                res_err = json.loads(err_body)
                error_obj = res_err.get("error", {})
                meta_code = error_obj.get("code")
                meta_err_msg = error_obj.get("message", "")
                err_title = error_obj.get("error_data", {}).get("details", "")
                if err_title:
                    meta_err_msg = f"{meta_err_msg} ({err_title})"
            except Exception:
                meta_err_msg = err_body

            retryable = is_retryable_whatsapp_error(e.code, meta_code)

            return WhatsAppSendResult(
                success=False,
                status="RETRYABLE_FAILURE" if retryable else "FAILED",
                error_code=str(meta_code or e.code),
                error_message=f"HTTP {e.code} Meta Error {meta_code}: {meta_err_msg}",
                is_retryable=retryable,
                http_status=e.code,
            )

        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            reason = e.reason if hasattr(e, "reason") else str(e)
            return WhatsAppSendResult(
                success=False,
                status="RETRYABLE_FAILURE",
                error_code="NETWORK_ERROR",
                error_message=f"Network connection failed or timed out: {reason}",
                is_retryable=True,
                is_ambiguous=True,
                http_status=0,
            )
        except Exception as e:
            return WhatsAppSendResult(
                success=False,
                status="FAILED",
                error_code="SYSTEM_EXCEPTION",
                error_message=f"Unexpected client exception: {type(e).__name__} - {e}",
                is_retryable=False,
                http_status=0,
            )


# ─────────────────────────────────────────────────────────────────────────────
# 5. WEBHOOK VERIFICATION & EVENT PARSER (Clean Integration Points)
# ─────────────────────────────────────────────────────────────────────────────

def verify_meta_webhook(
    mode: str | None,
    verify_token: str | None,
    challenge: str | None,
    expected_verify_token: str,
) -> str | None:
    """
    Validates Meta webhook verification request during endpoint subscription.
    Returns challenge string if valid, otherwise None.
    """
    if mode == "subscribe" and verify_token == expected_verify_token and challenge:
        return challenge
    return None


def parse_whatsapp_webhook_payload(payload: dict) -> list[dict[str, Any]]:
    """
    Parses WhatsApp Cloud API webhook status events (sent, delivered, read, failed).
    Returns list of parsed status dictionaries:
    [{'provider_message_id': wamid, 'status': 'DELIVERED', 'timestamp': ts, 'error': ...}]
    """
    results: list[dict[str, Any]] = []
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                statuses = value.get("statuses", [])
                for st in statuses:
                    wamid = st.get("id")
                    status_name = st.get("status", "").upper()  # SENT, DELIVERED, READ, FAILED
                    timestamp_str = st.get("timestamp")
                    errors = st.get("errors", [])
                    err_msg = errors[0].get("title", "") if errors else None

                    # Map Meta webhook status to TAMS message lifecycle
                    mapped_status = {
                        "SENT": "SENT",
                        "DELIVERED": "DELIVERED",
                        "READ": "READ",
                        "FAILED": "FAILED",
                    }.get(status_name, status_name)

                    results.append({
                        "provider_message_id": wamid,
                        "status": mapped_status,
                        "timestamp": timestamp_str,
                        "error_message": err_msg,
                        "recipient_id": st.get("recipient_id"),
                    })
    except Exception as e:
        logger.warning("Error parsing webhook payload: %s", e)

    return results
