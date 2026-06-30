import base64
import hashlib
import hmac
import json
import logging
import os
import random
from datetime import datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

import requests

from odoo import fields, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager

_logger = logging.getLogger(__name__)


class G2PATIConsentController(http.Controller):
    _MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB
    _REQUESTS_PAGE_SIZE = 10
    _TABLE_FETCH_SIZE = 10
    _FAYDA_OTP_SESSION_KEY = "g2p_consent_fayda_otp"
    _FAYDA_OTP_LOCAL_DEFAULTS = {
        "base_url": "http://127.0.0.1:8787",
        "client_id": "demo-client",
        "client_secret": "demo-secret",
        "env": "prod",
        "domain_uri": "fayda.et",
        "channel": "phone",
        "identifier_type": "FIN",
        "mock_host": "127.0.0.1",
        "mock_port": "8787",
        "use_primary_phone": False,
    }
    _LIVENESS_SESSION_KEY = "g2p_consent_liveness"
    _LIVENESS_LOCAL_DEFAULTS = {
        "ttl_seconds": 90,
        "prompt_count": 3,
        "verify_timeout": 20.0,
        "verify_url": "",
        "signing_secret": "change-me-liveness-signing-secret",
        "allow_local_provider": True,
        "prompt_library": [
            "blink_twice",
            "turn_left",
            "turn_right",
            "nod",
            "smile",
            "open_mouth",
        ],
    }

    def _error(self, message, code=400):
        return {"success": False, "code": code, "message": message}

    def _success(self, data=None, message="OK"):
        return {"success": True, "message": message, "data": data or {}}

    def _approved_farmer_domain(self):
        """Eligible farmers for consent flows."""
        return [("is_registrant", "=", True), ("is_group", "=", False), ("state", "=", "approved")]

    def _get_consent_partner(self):
        """Return the consent parent partner for the current portal user, or None."""
        user = request.env.user
        if not user.consent_parent_partner_id:
            return None
        return user.consent_parent_partner_id

    def _can_manage_consent_portal_hierarchy(self):
        user = request.env.user.sudo()
        return bool(user.consent_parent_partner_id and user.consent_portal_can_manage_hierarchy)

    def _get_portal_consent_request_domain(self, partner=None):
        partner = partner or self._get_consent_partner()
        if not partner:
            return []
        visible_user_ids = request.env.user.sudo()._get_consent_portal_visible_user_ids()
        domain = [("partner_record_id", "=", partner.id)]
        if visible_user_ids:
            domain.append(("requester_user_id", "in", visible_user_ids))
        else:
            domain.append(("requester_user_id", "=", request.env.user.id))
        return domain

    def _get_portal_management_context(self, partner):
        empty_user_model = request.env["res.users"].browse()
        empty_role_model = request.env["g2p.consent.portal.role"].browse()
        if not partner or not self._can_manage_consent_portal_hierarchy():
            return {
                "portal_management_enabled": False,
                "current_portal_user": request.env.user.sudo(),
                "portal_role_records": empty_role_model,
                "portal_role_options": empty_role_model,
                "portal_user_records": empty_user_model,
                "portal_user_options": empty_user_model,
            }

        portal_group = request.env.ref("base.group_portal")
        portal_user_model = request.env["res.users"].sudo().with_context(active_test=False)
        portal_role_model = request.env["g2p.consent.portal.role"].sudo().with_context(active_test=False)
        portal_users = portal_user_model.search(
            [
                ("consent_parent_partner_id", "=", partner.id),
                ("groups_id", "in", [portal_group.id]),
            ],
            order="consent_portal_manager_user_id asc, active desc, name asc",
        )
        portal_roles = portal_role_model.search(
            [("consent_parent_partner_id", "=", partner.id)],
            order="parent_id asc, active desc, name asc",
        )
        return {
            "portal_management_enabled": True,
            "current_portal_user": request.env.user.sudo(),
            "portal_role_records": portal_roles,
            "portal_role_options": portal_roles,
            "portal_user_records": portal_users,
            "portal_user_options": portal_users,
        }

    def _management_redirect(self, success=None, error=None, message=None):
        params = {}
        if success:
            params["mgmt_success"] = success
        if error:
            params["mgmt_error"] = error
        if message:
            params["mgmt_message"] = str(message)[:240]
        query = urlencode(params)
        return request.redirect(
            "/consent/management%s#portal_roles_pane" % (("?%s" % query) if query else "")
        )

    def _parse_portal_role_ids(self, raw_values, partner):
        role_ids = []
        for role_id in raw_values or []:
            try:
                role_ids.append(int(role_id))
            except (TypeError, ValueError):
                continue
        if not role_ids:
            return []
        role_model = request.env["g2p.consent.portal.role"].sudo()
        roles = role_model.search(
            [
                ("id", "in", role_ids),
                ("consent_parent_partner_id", "=", partner.id),
            ]
        )
        return roles.ids

    def _guess_image_content_type(self, image_data):
        if image_data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if image_data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_data.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if image_data.startswith(b"RIFF") and image_data[8:12] == b"WEBP":
            return "image/webp"
        return "image/png"

    def _build_farmer_profile_image_url(self, farmer):
        if not farmer or not farmer.image_1920:
            return ""
        return "/consent/farmer/%s/profile_image" % farmer.id

    def _env_flag_enabled(self, value, default=False):
        if value in (None, ""):
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def _get_farmer_primary_phone(self, farmer):
        if not farmer:
            return ""

        for phone in farmer.phone_number_ids:
            phone_no = (phone.phone_no or "").strip()
            if phone.phone_type == "primary" and phone_no:
                return phone_no

        return (farmer.mobile or farmer.phone or "").strip()

    
    
    def _get_fayda_otp_config(self):
        mock_host = (os.getenv("MOCK_FAYDA_HOST") or self._FAYDA_OTP_LOCAL_DEFAULTS["mock_host"]).strip()
        mock_port = (os.getenv("MOCK_FAYDA_PORT") or self._FAYDA_OTP_LOCAL_DEFAULTS["mock_port"]).strip()
        mock_base_url = "http://%s:%s" % (mock_host or self._FAYDA_OTP_LOCAL_DEFAULTS["mock_host"], mock_port or self._FAYDA_OTP_LOCAL_DEFAULTS["mock_port"])

        client_id = (
            os.getenv("G2P_FAYDA_OTP_CLIENT_ID")
            or os.getenv("MOCK_FAYDA_CLIENT_ID")
            or self._FAYDA_OTP_LOCAL_DEFAULTS["client_id"]
        ).strip()
        client_secret = (
            os.getenv("G2P_FAYDA_OTP_CLIENT_SECRET")
            or os.getenv("MOCK_FAYDA_CLIENT_SECRET")
            or self._FAYDA_OTP_LOCAL_DEFAULTS["client_secret"]
        ).strip()

        try:
            timeout = float((os.getenv("G2P_FAYDA_OTP_TIMEOUT") or "20").strip())
        except (TypeError, ValueError):
            timeout = 20.0

        return {
            "base_url": (os.getenv("G2P_FAYDA_OTP_BASE_URL") or mock_base_url).strip().rstrip("/"),
            "client_id": client_id,
            "client_secret": client_secret,
            "version": (os.getenv("G2P_FAYDA_OTP_VERSION") or "1.0").strip() or "1.0",
            "env": (os.getenv("G2P_FAYDA_OTP_ENV") or os.getenv("MOCK_FAYDA_ENV") or self._FAYDA_OTP_LOCAL_DEFAULTS["env"]).strip() or self._FAYDA_OTP_LOCAL_DEFAULTS["env"],
            "domain_uri": (os.getenv("G2P_FAYDA_OTP_DOMAIN_URI") or os.getenv("MOCK_FAYDA_DOMAIN_URI") or self._FAYDA_OTP_LOCAL_DEFAULTS["domain_uri"]).strip() or self._FAYDA_OTP_LOCAL_DEFAULTS["domain_uri"],
            "channel": (os.getenv("G2P_FAYDA_OTP_CHANNEL") or self._FAYDA_OTP_LOCAL_DEFAULTS["channel"]).strip() or self._FAYDA_OTP_LOCAL_DEFAULTS["channel"],
            "identifier_type": (os.getenv("G2P_FAYDA_OTP_ID_TYPE") or self._FAYDA_OTP_LOCAL_DEFAULTS["identifier_type"]).strip().upper() or self._FAYDA_OTP_LOCAL_DEFAULTS["identifier_type"],
            "preferred_reg_id_type": self._get_fayda_otp_reg_id_type_name(),
            "thumbprint": (os.getenv("G2P_FAYDA_OTP_THUMBPRINT") or "").strip(),
            "request_session_key": (os.getenv("G2P_FAYDA_OTP_REQUEST_SESSION_KEY") or "").strip(),
            "request_hmac": (os.getenv("G2P_FAYDA_OTP_REQUEST_HMAC") or "").strip(),
            "use_primary_phone": self._env_flag_enabled(
                os.getenv("G2P_FAYDA_OTP_USE_PRIMARY"),
                default=self._FAYDA_OTP_LOCAL_DEFAULTS["use_primary_phone"],
            ),
            "timeout": max(timeout, 1.0),
        }

    def _get_fayda_otp_reg_id_type_name(self):
        explicit_reg_id_type = (os.getenv("G2P_FAYDA_OTP_REG_ID_TYPE") or "").strip()
        if explicit_reg_id_type:
            return explicit_reg_id_type

        identifier_type = (
            os.getenv("G2P_FAYDA_OTP_ID_TYPE")
            or self._FAYDA_OTP_LOCAL_DEFAULTS["identifier_type"]
        ).strip().upper() or self._FAYDA_OTP_LOCAL_DEFAULTS["identifier_type"]
        identifier_map = {
            "FIN": "UID",
            "RID": "RID",
        }
        return identifier_map.get(identifier_type, identifier_type)

    def _get_fayda_otp_session_store(self):
        store = request.session.get(self._FAYDA_OTP_SESSION_KEY)
        if not isinstance(store, dict):
            store = {}
            request.session[self._FAYDA_OTP_SESSION_KEY] = store
        return store

    def _get_liveness_config(self):
        try:
            ttl_seconds = int((os.getenv("G2P_LIVENESS_TTL_SECONDS") or "").strip() or self._LIVENESS_LOCAL_DEFAULTS["ttl_seconds"])
        except (TypeError, ValueError):
            ttl_seconds = self._LIVENESS_LOCAL_DEFAULTS["ttl_seconds"]
        ttl_seconds = max(20, min(ttl_seconds, 300))

        try:
            prompt_count = int((os.getenv("G2P_LIVENESS_PROMPT_COUNT") or "").strip() or self._LIVENESS_LOCAL_DEFAULTS["prompt_count"])
        except (TypeError, ValueError):
            prompt_count = self._LIVENESS_LOCAL_DEFAULTS["prompt_count"]
        prompt_count = max(1, min(prompt_count, 3))

        try:
            verify_timeout = float(
                (os.getenv("G2P_LIVENESS_VERIFY_TIMEOUT") or "").strip()
                or self._LIVENESS_LOCAL_DEFAULTS["verify_timeout"]
            )
        except (TypeError, ValueError):
            verify_timeout = self._LIVENESS_LOCAL_DEFAULTS["verify_timeout"]
        verify_timeout = max(2.0, verify_timeout)

        prompt_library_raw = (os.getenv("G2P_LIVENESS_PROMPTS") or "").strip()
        prompt_library = []
        if prompt_library_raw:
            prompt_library = [
                item.strip()
                for item in prompt_library_raw.split(",")
                if item and item.strip()
            ]
        if not prompt_library:
            prompt_library = list(self._LIVENESS_LOCAL_DEFAULTS["prompt_library"])

        return {
            "ttl_seconds": ttl_seconds,
            "prompt_count": prompt_count,
            "verify_timeout": verify_timeout,
            "verify_url": (os.getenv("G2P_LIVENESS_VERIFY_URL") or self._LIVENESS_LOCAL_DEFAULTS["verify_url"]).strip(),
            "signing_secret": (
                os.getenv("G2P_LIVENESS_SIGNING_SECRET")
                or self._LIVENESS_LOCAL_DEFAULTS["signing_secret"]
            ).strip(),
            "allow_local_provider": self._env_flag_enabled(
                os.getenv("G2P_LIVENESS_ALLOW_LOCAL_PROVIDER"),
                default=self._LIVENESS_LOCAL_DEFAULTS["allow_local_provider"],
            ),
            "prompt_library": prompt_library,
        }

    def _get_liveness_session_store(self):
        store = request.session.get(self._LIVENESS_SESSION_KEY)
        if not isinstance(store, dict):
            store = {}
            request.session[self._LIVENESS_SESSION_KEY] = store
        return store

    def _parse_session_datetime(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        parsed = fields.Datetime.to_datetime(value)
        return parsed

    def _prune_liveness_session_store(self):
        store = self._get_liveness_session_store()
        now_dt = fields.Datetime.now()
        modified = False
        for challenge_id, entry in list(store.items()):
            if not isinstance(entry, dict):
                store.pop(challenge_id, None)
                modified = True
                continue

            expires_at = self._parse_session_datetime(entry.get("expires_at"))
            if expires_at and expires_at < now_dt:
                store.pop(challenge_id, None)
                modified = True
                continue

            consumed_at = self._parse_session_datetime(entry.get("consumed_at"))
            if consumed_at and consumed_at < now_dt - timedelta(minutes=15):
                store.pop(challenge_id, None)
                modified = True

        if modified:
            self._mark_session_modified()
        return store

    def _mark_session_modified(self):
        if not getattr(request, "session", None):
            return
        if hasattr(request.session, "is_dirty"):
            request.session.is_dirty = True
        elif hasattr(request.session, "modified"):
            request.session.modified = True

    def _now_iso_millis(self):
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

    def _make_liveness_challenge_id(self):
        return uuid4().hex

    def _make_liveness_nonce(self):
        return uuid4().hex

    def _random_liveness_prompt_sequence(self):
        config = self._get_liveness_config()
        prompt_library = list(config["prompt_library"] or [])
        if not prompt_library:
            prompt_library = list(self._LIVENESS_LOCAL_DEFAULTS["prompt_library"])
        prompt_count = min(config["prompt_count"], len(prompt_library))
        if prompt_count <= 0:
            prompt_count = 1
        return random.sample(prompt_library, prompt_count)

    def _canonical_json_bytes(self, payload):
        return json.dumps(
            payload or {},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def _verify_hmac_sha256_signature(self, payload, provided_signature, signing_secret):
        if not provided_signature or not signing_secret:
            return False
        expected = hmac.new(
            signing_secret.encode("utf-8"),
            self._canonical_json_bytes(payload),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, str(provided_signature).strip())

    def _decode_jws_segment(self, value):
        value = (value or "").strip()
        if not value:
            raise ValueError("Empty JWS segment.")
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(value + padding)
        return decoded.decode("utf-8")

    def _verify_jws_hs256(self, token, signing_secret):
        token = (token or "").strip()
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWS format.")
        if not signing_secret:
            raise ValueError("Missing signing secret for JWS verification.")

        header_json = self._decode_jws_segment(parts[0])
        payload_json = self._decode_jws_segment(parts[1])
        try:
            header = json.loads(header_json)
            payload = json.loads(payload_json)
        except ValueError as exc:
            raise ValueError("Invalid JWS JSON payload.") from exc

        algorithm = str(header.get("alg") or "").upper()
        if algorithm != "HS256":
            raise ValueError("Unsupported JWS algorithm: %s" % (algorithm or "unknown"))

        signing_input = ("%s.%s" % (parts[0], parts[1])).encode("utf-8")
        expected_signature = hmac.new(
            signing_secret.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        provided_signature = base64.urlsafe_b64decode(parts[2] + ("=" * (-len(parts[2]) % 4)))
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise ValueError("JWS signature mismatch.")
        if not isinstance(payload, dict):
            raise ValueError("Invalid JWS payload content.")
        return payload

    def _verify_provider_signed_payload(self, provider_response, signing_secret):
        if not isinstance(provider_response, dict):
            raise ValueError("Liveness provider returned an invalid response format.")

        if provider_response.get("jws"):
            payload = self._verify_jws_hs256(provider_response.get("jws"), signing_secret)
            if not isinstance(payload, dict):
                raise ValueError("Invalid JWS verification payload.")
            return payload

        verification_payload = provider_response.get("verification")
        if not isinstance(verification_payload, dict):
            raise ValueError("Liveness provider did not return verification payload.")

        signature_algorithm = str(
            provider_response.get("signature_algorithm")
            or provider_response.get("algorithm")
            or "hmac_sha256"
        ).strip().lower()
        signature = str(provider_response.get("signature") or "").strip()
        if signature_algorithm != "hmac_sha256":
            raise ValueError("Unsupported liveness signature algorithm: %s" % signature_algorithm)
        if not self._verify_hmac_sha256_signature(verification_payload, signature, signing_secret):
            raise ValueError("Liveness provider signature verification failed.")
        return verification_payload

    def _mock_liveness_provider_response(self, verify_payload, signing_secret):
        challenge_id = (verify_payload.get("challenge_id") or "").strip()
        nonce = (verify_payload.get("nonce") or "").strip()
        prompts = verify_payload.get("prompt_sequence") or []
        capture_image = (verify_payload.get("capture_image") or "").strip()
        face_match_passed = bool(verify_payload.get("face_match_passed"))
        try:
            face_match_distance = float(verify_payload.get("face_match_distance"))
        except (TypeError, ValueError):
            face_match_distance = None
        try:
            face_match_threshold = float(verify_payload.get("face_match_threshold"))
        except (TypeError, ValueError):
            face_match_threshold = 0.45
        if face_match_threshold <= 0:
            face_match_threshold = 0.45

        # Dev fallback only: external provider can be wired with G2P_LIVENESS_VERIFY_URL.
        passed = bool(challenge_id and nonce and prompts and capture_image and face_match_passed)
        message = (
            "Face match + liveness challenge verified."
            if passed
            else "Face match or liveness verification failed. Capture a new photo and try again."
        )
        verification_payload = {
            "challenge_id": challenge_id,
            "nonce": nonce,
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "face_match_passed": bool(face_match_passed),
            "face_match_distance": face_match_distance,
            "face_match_threshold": face_match_threshold,
            "checked_at": fields.Datetime.to_string(fields.Datetime.now()),
            "provider_reference": "local-mock-%s" % uuid4().hex[:12],
            "message": message,
        }
        signature = hmac.new(
            signing_secret.encode("utf-8"),
            self._canonical_json_bytes(verification_payload),
            hashlib.sha256,
        ).hexdigest()
        return {
            "verification": verification_payload,
            "signature_algorithm": "hmac_sha256",
            "signature": signature,
        }

    def _call_liveness_provider_verify(self, verify_payload):
        config = self._get_liveness_config()
        signing_secret = config["signing_secret"]
        verify_url = config["verify_url"]
        allow_local_provider = bool(config["allow_local_provider"])

        if not signing_secret:
            raise ValueError("Liveness signing secret is not configured.")

        if verify_url:
            try:
                response = requests.post(
                    verify_url,
                    json=verify_payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    timeout=config["verify_timeout"],
                )
            except requests.RequestException as exc:
                raise ValueError("Liveness provider request failed: %s" % exc) from exc

            try:
                provider_response = response.json()
            except ValueError as exc:
                raise ValueError("Liveness provider returned a non-JSON response.") from exc

            if not response.ok:
                provider_message = ""
                if isinstance(provider_response, dict):
                    provider_message = (
                        provider_response.get("message")
                        or provider_response.get("error")
                        or ""
                    )
                provider_message = (provider_message or "").strip()
                if not provider_message:
                    provider_message = "Liveness provider returned HTTP %s." % response.status_code
                raise ValueError(provider_message)
        elif allow_local_provider:
            provider_response = self._mock_liveness_provider_response(verify_payload, signing_secret)
        else:
            raise ValueError("Liveness provider URL is not configured.")

        return self._verify_provider_signed_payload(provider_response, signing_secret)


    def _make_fayda_transaction_id(self):
        return uuid4().hex.upper()

    def _normalize_fayda_error_message(self, errors, fallback_message):
        if not errors:
            return fallback_message
        if isinstance(errors, str):
            return errors.strip() or fallback_message
        if isinstance(errors, dict):
            parts = []
            for key, value in errors.items():
                if value in (None, "", []):
                    continue
                parts.append("%s: %s" % (key, value))
            return "; ".join(parts) or fallback_message
        if isinstance(errors, (list, tuple)):
            parts = [str(item).strip() for item in errors if str(item).strip()]
            return "; ".join(parts) or fallback_message
        return str(errors).strip() or fallback_message

    def _call_fayda_otp_api(self, endpoint, payload):
        config = self._get_fayda_otp_config()
        url = "%s%s" % (config["base_url"], endpoint)
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=config["timeout"],
            )
        except requests.RequestException as exc:
            raise ValueError("Fayda OTP API request failed: %s" % exc) from exc

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise ValueError("Fayda OTP API returned a non-JSON response.") from exc

        if not response.ok:
            message = self._normalize_fayda_error_message(
                response_payload.get("errors") if isinstance(response_payload, dict) else None,
                "Fayda OTP API returned HTTP %s." % response.status_code,
            )
            raise ValueError(message)

        if not isinstance(response_payload, dict):
            raise ValueError("Fayda OTP API returned an unexpected response format.")

        return response_payload

    def _get_farmer_fayda_identifier(self, farmer):
        identifier = ""
        source = ""
        preferred_reg_id_type = (self._get_fayda_otp_reg_id_type_name() or "").strip().lower()

        if farmer and preferred_reg_id_type:
            for reg_id in farmer.reg_ids:
                reg_name = (reg_id.id_type.name or "").strip().lower()
                reg_value = (reg_id.value or "").strip()
                if reg_name == preferred_reg_id_type and reg_value:
                    identifier = reg_value
                    source = reg_id.id_type.name or "reg_id"
                    break

        return {
            "identifier": identifier,
            "identifier_type": (os.getenv("G2P_FAYDA_OTP_ID_TYPE") or self._FAYDA_OTP_LOCAL_DEFAULTS["identifier_type"]).strip().upper() or self._FAYDA_OTP_LOCAL_DEFAULTS["identifier_type"],
            "identifier_source": source,
            "available": bool(identifier),
        }

    def _extract_fayda_otp_values(self, post, farmer, partner):
        transaction_id = (post.get("fayda_otp_transaction_id") or "").strip()
        if not transaction_id:
            return {"fayda_otp_status": "not_requested"}, False, None

        store = self._get_fayda_otp_session_store()
        session_entry = store.get(transaction_id)
        if not isinstance(session_entry, dict):
            return (
                {
                    "fayda_otp_status": "error",
                    "fayda_otp_transaction_id": transaction_id,
                    "fayda_otp_message": "Fayda OTP verification session was not found.",
                },
                False,
                transaction_id,
            )

        if session_entry.get("partner_id") != partner.id or session_entry.get("farmer_id") != farmer.id:
            return (
                {
                    "fayda_otp_status": "error",
                    "fayda_otp_transaction_id": transaction_id,
                    "fayda_otp_message": "Fayda OTP verification does not match the selected farmer.",
                },
                False,
                transaction_id,
            )

        status = (session_entry.get("status") or "requested").strip().lower()
        if status not in {"requested", "verified", "failed", "error"}:
            status = "error"

        values = {
            "fayda_otp_status": status,
            "fayda_otp_transaction_id": transaction_id,
            "fayda_otp_identifier": session_entry.get("identifier") or False,
            "fayda_otp_identifier_type": session_entry.get("identifier_type") or False,
            "fayda_otp_masked_mobile": session_entry.get("masked_mobile") or False,
            "fayda_otp_message": (session_entry.get("message") or "")[:1024] or False,
        }
        verified_at = session_entry.get("verified_at")
        if verified_at:
            values["fayda_otp_verified_at"] = verified_at

        return values, status == "verified", transaction_id



    def _extract_liveness_values(self, post, farmer, partner, has_camera_capture):
        challenge_id = (post.get("liveness_challenge_id") or "").strip()
        verification_token = (post.get("liveness_verification_token") or "").strip()
        values = {"face_match_status": "not_attempted"}

        if not has_camera_capture:
            values["face_match_message"] = "No camera capture found for face + liveness verification."
            return values, False, None

        if not challenge_id or not verification_token:
            values["face_match_status"] = "not_attempted"
            values["face_match_message"] = "Liveness verification token missing."
            return values, False, challenge_id or None

        session_store = self._prune_liveness_session_store()
        session_entry = session_store.get(challenge_id)
        if not isinstance(session_entry, dict):
            values["face_match_status"] = "error"
            values["face_match_message"] = "Liveness challenge was not found or expired."
            return values, False, challenge_id

        if (
            session_entry.get("partner_id") != partner.id
            or session_entry.get("farmer_id") != farmer.id
        ):
            values["face_match_status"] = "error"
            values["face_match_message"] = "Liveness verification does not match the selected farmer."
            return values, False, challenge_id

        expires_at = self._parse_session_datetime(session_entry.get("expires_at"))
        if expires_at and expires_at < fields.Datetime.now():
            values["face_match_status"] = "error"
            values["face_match_message"] = "Liveness challenge expired. Capture a new challenge."
            return values, False, challenge_id

        if session_entry.get("verification_token") != verification_token:
            values["face_match_status"] = "error"
            values["face_match_message"] = "Invalid liveness verification token."
            return values, False, challenge_id

        if session_entry.get("status") != "verified":
            values["face_match_status"] = "error"
            values["face_match_message"] = "Liveness verification is not complete."
            return values, False, challenge_id

        if not session_entry.get("face_match_passed"):
            values["face_match_status"] = "error"
            values["face_match_message"] = "Face match is required together with liveness verification."
            return values, False, challenge_id

        if session_entry.get("consumed"):
            values["face_match_status"] = "error"
            values["face_match_message"] = "Liveness verification token has already been used."
            return values, False, challenge_id

        checked_at = fields.Datetime.now()
        session_entry["consumed"] = True
        session_entry["consumed_at"] = fields.Datetime.to_string(checked_at)
        self._mark_session_modified()

        provider_reference = (session_entry.get("provider_reference") or "").strip()
        message = "Face match + liveness challenge verified."
        if provider_reference:
            message = "%s Provider ref: %s." % (message, provider_reference)
        try:
            face_match_distance = float(session_entry.get("face_match_distance"))
        except (TypeError, ValueError):
            face_match_distance = None
        try:
            face_match_threshold = float(session_entry.get("face_match_threshold"))
        except (TypeError, ValueError):
            face_match_threshold = 0.45
        if face_match_threshold <= 0:
            face_match_threshold = 0.45
        if face_match_distance is None:
            face_match_distance = 0.0

        values.update(
            {
                "face_match_status": "matched",
                "face_match_distance": face_match_distance,
                "face_match_threshold": face_match_threshold,
                "face_match_checked_at": fields.Datetime.to_string(checked_at),
                "face_match_message": message[:1024],
            }
        )
        return values, True, challenge_id

    def _serialize_consent_request(self, req):
        created_at = req.created_at
        if created_at:
            created_at = fields.Datetime.to_string(created_at)
        return {
            "id": req.id,
            "request_id": req.consent_creation_request_id or "",
            "farmer_name": req.farmer_id.display_name or "",
            "consent_type": req.consent_type or "",
            "status": req.status or "",
            "created_at": created_at or "",
            "review_url": "/consent/management/review/%s?view=table" % req.id,
        }

    def _find_farmer(self, payload):
        """Find farmer by farmer_db_id, farmer_id, or national_id/UID.

        Uses multiple search strategies similar to SQL approach:
        - Partner ID (farmer_db_id)
        - farmer_id field
        - unique_id field
        - reg_ids.value (any ID type for national_id, UID type for UID)

        Returns only approved farmers.
        """
        partner_obj = request.env["res.partner"].sudo()
        reg_id_obj = request.env["g2p.reg.id"].sudo()

        base_domain = self._approved_farmer_domain()

        farmer_db_id = payload.get("farmer_db_id")
        farmer_id = payload.get("farmer_id")
        national_id = payload.get("national_id")

        if farmer_db_id:
            return partner_obj.search(
                base_domain + [("id", "=", int(farmer_db_id))],
                limit=1,
            )
        if farmer_id:
            return partner_obj.search(
                base_domain + [("farmer_id", "=", farmer_id)],
                limit=1,
            )
        if national_id:
            search_value = str(national_id).strip()
            partner_ids = set()
            
            # Search by unique_id
            farmers = partner_obj.search(base_domain + [("unique_id", "=", search_value)], limit=1)
            if farmers:
                return farmers[0]
            
            # Search by reg_ids.value (any ID type)
            reg_ids = reg_id_obj.search([("value", "=", search_value)], limit=100)
            if reg_ids:
                partner_ids.update(reg_ids.mapped("partner_id").ids)
                farmers = partner_obj.search(
                    base_domain + [("id", "in", list(partner_ids))], limit=1
                )
                if farmers:
                    return farmers[0]

        return partner_obj.browse()
    # -------------------------------------------------------------------------
    # Portal: consent management page and farmer search
    # -------------------------------------------------------------------------

    @http.route(
        ["/consent/management", "/consent/management/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def consent_management_page(self, page=1, **kw):
        partner = self._get_consent_partner()
        if not partner:
            return request.redirect("/portal/home")
        try:
            page = int(page or 1)
        except (TypeError, ValueError):
            page = 1
        page = max(page, 1)

        view_mode = (kw.get("view") or request.params.get("view") or "card").strip().lower()
        if view_mode not in {"card", "table"}:
            view_mode = "card"

        ConsentRequest = request.env["g2p.consent.request"].sudo()
        requests_domain = self._get_portal_consent_request_domain(partner)
        total_requests = ConsentRequest.search_count(requests_domain)
        pager = portal_pager(
            url="/consent/management",
            total=total_requests,
            page=page,
            step=self._REQUESTS_PAGE_SIZE,
            url_args={"view": view_mode},
        )
        request_limit = self._REQUESTS_PAGE_SIZE
        request_offset = pager.get("offset", 0)
        consent_requests = ConsentRequest.search(
            requests_domain,
            order="create_date desc",
            limit=request_limit,
            offset=request_offset,
        )
        data_fields = partner.allowed_data_field_ids
        consent_reasons = request.env["g2p.consent.reason"].sudo().search(
            [("active", "=", True)],
            order="name asc",
        )
        review_request = request.env["g2p.consent.request"].browse()
        review_id = kw.get("review_id") or request.params.get("review_id")
        if review_id:
            try:
                review_id = int(review_id)
            except (TypeError, ValueError):
                review_id = 0
            if review_id:
                review_request = ConsentRequest.search(
                    requests_domain + [("id", "=", review_id)],
                    limit=1,
                )
        view_base_url = "/consent/management/page/%s" % page if page > 1 else "/consent/management"
        review_close_url = "%s?view=%s" % (view_base_url, view_mode)
        management_context = self._get_portal_management_context(partner)
        return request.render(
            "g2p_ati_consent_mgt.portal_consent_management",
            {
                "consent_partner": partner,
                "consent_requests": consent_requests,
                "data_fields": data_fields,
                "consent_reasons": consent_reasons,
                "review_request": review_request,
                "pager": pager,
                "view_mode": view_mode,
                "view_base_url": view_base_url,
                "requests_page_size": self._REQUESTS_PAGE_SIZE,
                "table_fetch_size": self._TABLE_FETCH_SIZE,
                "total_requests": total_requests,
                "current_page": page,
                "review_close_url": review_close_url,
                **management_context,
            },
        )

    @http.route("/consent/management/table_fetch", type="json", auth="user")
    def consent_management_table_fetch(self, offset=0, limit=10, **kw):
        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)

        try:
            offset = int(offset or 0)
        except (TypeError, ValueError):
            offset = 0
        try:
            limit = int(limit or self._TABLE_FETCH_SIZE)
        except (TypeError, ValueError):
            limit = self._TABLE_FETCH_SIZE

        offset = max(offset, 0)
        if limit <= 0:
            limit = self._TABLE_FETCH_SIZE
        limit = min(limit, 50)

        ConsentRequest = request.env["g2p.consent.request"].sudo()
        domain = self._get_portal_consent_request_domain(partner)
        total = ConsentRequest.search_count(domain)
        rows = ConsentRequest.search(domain, order="create_date desc", offset=offset, limit=limit)
        return self._success(
            data={
                "total": total,
                "offset": offset,
                "limit": limit,
                "rows": [self._serialize_consent_request(rec) for rec in rows],
            }
        )

    @http.route("/consent/management/review/<int:review_id>", type="http", auth="user", website=True)
    def consent_management_page_review(self, review_id, **kw):
        kw["review_id"] = review_id
        kw["page"] = kw.get("page") or request.params.get("page") or 1
        return self.consent_management_page(**kw)

    @http.route("/consent/request/<int:consent_id>/capture_image", type="http", auth="user")
    def consent_request_capture_image(self, consent_id, **kw):
        partner = self._get_consent_partner()
        if not partner:
            return request.not_found()

        consent = request.env["g2p.consent.request"].sudo().search(
            self._get_portal_consent_request_domain(partner) + [("id", "=", consent_id)],
            limit=1,
        )
        if not consent or not consent.portal_capture_image:
            return request.not_found()

        try:
            image_data = base64.b64decode(consent.portal_capture_image)
        except Exception:
            return request.not_found()

        headers = [
            ("Content-Type", "image/jpeg"),
            ("Content-Length", str(len(image_data))),
        ]
        return request.make_response(image_data, headers=headers)

    @http.route("/consent/management/role/create", type="http", auth="user", methods=["POST"], csrf=True)
    def consent_management_role_create(self, **post):
        partner = self._get_consent_partner()
        if not partner or not self._can_manage_consent_portal_hierarchy():
            return self._management_redirect(error="access_denied")

        name = (post.get("name") or "").strip()
        if not name:
            return self._management_redirect(error="missing_role_name")

        parent_role = request.env["g2p.consent.portal.role"].sudo().browse()
        parent_id = post.get("parent_id")
        if parent_id:
            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError):
                return self._management_redirect(error="invalid_role_parent")
            parent_role = request.env["g2p.consent.portal.role"].sudo().search(
                [
                    ("id", "=", parent_id),
                    ("consent_parent_partner_id", "=", partner.id),
                ],
                limit=1,
            )
            if not parent_role:
                return self._management_redirect(error="invalid_role_parent")

        values = {
            "name": name,
            "consent_parent_partner_id": partner.id,
            "parent_id": parent_role.id or False,
            "description": (post.get("description") or "").strip() or False,
        }
        try:
            request.env["g2p.consent.portal.role"].sudo().create(values)
        except Exception as exc:
            _logger.exception("Failed to create consent portal role for partner %s", partner.id)
            return self._management_redirect(error="role_create_failed", message=exc)
        return self._management_redirect(success="role_created")

    @http.route("/consent/management/role/update", type="http", auth="user", methods=["POST"], csrf=True)
    def consent_management_role_update(self, **post):
        partner = self._get_consent_partner()
        if not partner or not self._can_manage_consent_portal_hierarchy():
            return self._management_redirect(error="access_denied")

        try:
            role_id = int(post.get("role_id") or 0)
        except (TypeError, ValueError):
            role_id = 0
        if not role_id:
            return self._management_redirect(error="invalid_role")

        role = request.env["g2p.consent.portal.role"].sudo().search(
            [
                ("id", "=", role_id),
                ("consent_parent_partner_id", "=", partner.id),
            ],
            limit=1,
        )
        if not role:
            return self._management_redirect(error="invalid_role")

        name = (post.get("name") or "").strip()
        if not name:
            return self._management_redirect(error="missing_role_name")

        parent_role = request.env["g2p.consent.portal.role"].sudo().browse()
        parent_id = post.get("parent_id")
        if parent_id:
            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError):
                return self._management_redirect(error="invalid_role_parent")
            parent_role = request.env["g2p.consent.portal.role"].sudo().search(
                [
                    ("id", "=", parent_id),
                    ("consent_parent_partner_id", "=", partner.id),
                ],
                limit=1,
            )
            if not parent_role:
                return self._management_redirect(error="invalid_role_parent")

        values = {
            "name": name,
            "parent_id": parent_role.id or False,
            "description": (post.get("description") or "").strip() or False,
            "active": bool(post.get("active")),
        }
        try:
            role.write(values)
        except Exception as exc:
            _logger.exception("Failed to update consent portal role %s", role.id)
            return self._management_redirect(error="role_update_failed", message=exc)
        return self._management_redirect(success="role_updated")

    @http.route("/consent/management/user/create", type="http", auth="user", methods=["POST"], csrf=True)
    def consent_management_user_create(self, **post):
        partner = self._get_consent_partner()
        if not partner or not self._can_manage_consent_portal_hierarchy():
            return self._management_redirect(error="access_denied")

        name = (post.get("name") or "").strip()
        login = (post.get("login") or "").strip()
        email = login or False
        phone = (post.get("phone") or "").strip()
        password = post.get("password") or ""
        if not name or not login or not password:
            return self._management_redirect(error="missing_user_fields")

        manager = request.env["res.users"].sudo().browse()
        manager_id = post.get("manager_user_id")
        if manager_id:
            try:
                manager_id = int(manager_id)
            except (TypeError, ValueError):
                return self._management_redirect(error="invalid_user_manager")
            manager = request.env["res.users"].sudo().search(
                [
                    ("id", "=", manager_id),
                    ("consent_parent_partner_id", "=", partner.id),
                ],
                limit=1,
            )
            if not manager:
                return self._management_redirect(error="invalid_user_manager")

        role_ids = self._parse_portal_role_ids(
            request.httprequest.form.getlist("role_ids"),
            partner,
        )

        if request.env["res.users"].sudo().with_context(active_test=False).search_count([("login", "=", login)]):
            return self._management_redirect(error="duplicate_login")

        child_partner = request.env["res.partner"].sudo().create(
            {
                "name": name,
                "email": email or False,
                "phone": phone or False,
                "type": "contact",
                "parent_id": partner.id,
            }
        )
        portal_group = request.env.ref("base.group_portal")
        user_values = {
            "name": name,
            "login": login,
            "email": email or False,
            "partner_id": child_partner.id,
            "consent_parent_partner_id": partner.id,
            "consent_portal_manager_user_id": manager.id or False,
            "consent_portal_role_ids": [(6, 0, role_ids)],
            "consent_portal_can_manage_hierarchy": bool(post.get("can_manage_hierarchy")),
            "groups_id": [(6, 0, [portal_group.id])],
            "password": password,
        }
        try:
            request.env["res.users"].sudo().with_context(no_reset_password=True).create(user_values)
        except Exception as exc:
            _logger.exception("Failed to create consent portal user for partner %s", partner.id)
            if child_partner.exists():
                child_partner.unlink()
            return self._management_redirect(error="user_create_failed", message=exc)
        return self._management_redirect(success="user_created")

    @http.route("/consent/management/user/update", type="http", auth="user", methods=["POST"], csrf=True)
    def consent_management_user_update(self, **post):
        partner = self._get_consent_partner()
        if not partner or not self._can_manage_consent_portal_hierarchy():
            return self._management_redirect(error="access_denied")

        try:
            user_id = int(post.get("user_id") or 0)
        except (TypeError, ValueError):
            user_id = 0
        if not user_id:
            return self._management_redirect(error="invalid_user")

        portal_group = request.env.ref("base.group_portal")
        target_user = request.env["res.users"].sudo().with_context(active_test=False).search(
            [
                ("id", "=", user_id),
                ("consent_parent_partner_id", "=", partner.id),
                ("groups_id", "in", [portal_group.id]),
            ],
            limit=1,
        )
        if not target_user:
            return self._management_redirect(error="invalid_user")

        name = (post.get("name") or "").strip()
        login = (post.get("login") or "").strip()
        email = login or False
        phone = (post.get("phone") or "").strip()
        if not name or not login:
            return self._management_redirect(error="missing_user_fields")

        manager = request.env["res.users"].sudo().browse()
        manager_id = post.get("manager_user_id")
        if manager_id:
            try:
                manager_id = int(manager_id)
            except (TypeError, ValueError):
                return self._management_redirect(error="invalid_user_manager")
            manager = request.env["res.users"].sudo().search(
                [
                    ("id", "=", manager_id),
                    ("consent_parent_partner_id", "=", partner.id),
                ],
                limit=1,
            )
            if not manager:
                return self._management_redirect(error="invalid_user_manager")

        duplicate_domain = [("login", "=", login), ("id", "!=", target_user.id)]
        if request.env["res.users"].sudo().with_context(active_test=False).search_count(duplicate_domain):
            return self._management_redirect(error="duplicate_login")

        role_ids = self._parse_portal_role_ids(
            request.httprequest.form.getlist("role_ids"),
            partner,
        )
        user_values = {
            "name": name,
            "login": login,
            "email": email or False,
            "consent_portal_manager_user_id": manager.id or False,
            "consent_portal_role_ids": [(6, 0, role_ids)],
            "consent_portal_can_manage_hierarchy": bool(post.get("can_manage_hierarchy")),
            "active": bool(post.get("active")),
        }
        password = post.get("password") or ""
        if password:
            user_values["password"] = password
        partner_values = {
            "name": name,
            "email": email or False,
            "phone": phone or False,
        }
        try:
            target_user.write(user_values)
            if target_user.partner_id:
                target_user.partner_id.sudo().write(partner_values)
        except Exception as exc:
            _logger.exception("Failed to update consent portal user %s", target_user.id)
            return self._management_redirect(error="user_update_failed", message=exc)
        return self._management_redirect(success="user_updated")

    @http.route("/consent/farmer/<int:farmer_id>/profile_image", type="http", auth="user")
    def consent_farmer_profile_image(self, farmer_id, **kw):
        if not self._get_consent_partner():
            return request.not_found()

        farmer = request.env["res.partner"].sudo().search(
            self._approved_farmer_domain() + [("id", "=", farmer_id)],
            limit=1,
        )
        if not farmer or not farmer.image_1920:
            return request.not_found()

        try:
            image_data = base64.b64decode(farmer.image_1920)
        except Exception:
            return request.not_found()

        headers = [
            ("Content-Type", self._guess_image_content_type(image_data)),
            ("Content-Length", str(len(image_data))),
        ]
        return request.make_response(image_data, headers=headers)

    @http.route("/consent/search_farmer", type="json", auth="user")
    def consent_search_farmer(self, farmer_id=None, national_id=None, uid=None, query=None, **kw):
        """Search farmers by Farmer ID/UID and return only approved farmer records."""
        if not self._get_consent_partner():
            return self._error("Access denied", code=403)

        search_value = None
        if query and str(query).strip():
            search_value = str(query).strip()
        elif farmer_id and str(farmer_id).strip():
            search_value = str(farmer_id).strip()
        elif national_id and str(national_id).strip():
            search_value = str(national_id).strip()
        elif uid and str(uid).strip():
            search_value = str(uid).strip()
        if not search_value:
            return self._error("Provide farmer_id, national_id, uid, or query")

        partner_obj = request.env["res.partner"].sudo()
        reg_id_obj = request.env["g2p.reg.id"].sudo()
        base_domain = self._approved_farmer_domain()
        partner_ids = set()

        # 1) By farmer_id
        for p in partner_obj.search(base_domain + [("farmer_id", "=", search_value)], limit=10):
            partner_ids.add(p.id)
        # 2) By unique_id
        for p in partner_obj.search(base_domain + [("unique_id", "=", search_value)], limit=10):
            partner_ids.add(p.id)
        # 3) By reg_ids.value (IDs tab – UID / ID Number)
        for reg in reg_id_obj.search([("value", "=", search_value)], limit=100):
            if reg.partner_id:
                partner_ids.add(reg.partner_id.id)

        if not partner_ids:
            return self._success(data={"farmers": []})

        farmers = partner_obj.search(base_domain + [("id", "in", list(partner_ids))], limit=10)
        def _serialize_farmer(partner):
            otp_identity = self._get_farmer_fayda_identifier(partner)
            return {
                "id": partner.id,
                "name": partner.name,
                "farmer_id": partner.farmer_id or "",
                "phone": self._get_farmer_primary_phone(partner),
                "reg_ids": [r.value for r in (partner.reg_ids or [])],
                "profile_image_url": self._build_farmer_profile_image_url(partner),
                "otp_identifier": otp_identity.get("identifier") or "",
                "otp_identifier_type": otp_identity.get("identifier_type") or "",
                "otp_identifier_source": otp_identity.get("identifier_source") or "",
                "otp_available": otp_identity.get("available") or False,
            }
        return self._success(
            data={
                "farmers": [_serialize_farmer(p) for p in farmers]
            }
        )

    @http.route("/consent/fayda/request_otp", type="json", auth="user")
    def consent_fayda_request_otp(self, farmer_id=None, **kw):
        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)

        try:
            farmer_id = int(farmer_id or 0)
        except (TypeError, ValueError):
            farmer_id = 0
        if not farmer_id:
            return self._error("Select a farmer before requesting OTP.")

        farmer = (
            request.env["res.partner"]
            .sudo()
            .search(self._approved_farmer_domain() + [("id", "=", farmer_id)], limit=1)
        )
        if not farmer:
            return self._error("Approved farmer not found.")

        identifier_info = self._get_farmer_fayda_identifier(farmer)
        if not identifier_info["available"]:
            return self._error("Selected farmer has no Fayda OTP identifier configured.")

        try:
            config = self._get_fayda_otp_config()
            transaction_id = self._make_fayda_transaction_id()
            preferred_phone = self._get_farmer_primary_phone(farmer) if config["use_primary_phone"] else ""
            payload = {
                "id": config["client_id"],
                "clientSecret": config["client_secret"],
                "version": config["version"],
                "requestTime": self._now_iso_millis(),
                "env": config["env"],
                "domainUri": config["domain_uri"],
                "transactionID": transaction_id,
                "individualId": identifier_info["identifier"],
                "individualIdType": identifier_info["identifier_type"],
                "otpChannel": [config["channel"]],
            }
            if preferred_phone:
                payload["preferredPhoneNumber"] = preferred_phone
            response_payload = self._call_fayda_otp_api("/requestData", payload)
        except ValueError as exc:
            return self._error(str(exc), code=500)

        errors = response_payload.get("errors")
        if errors:
            return self._error(
                self._normalize_fayda_error_message(errors, "Fayda OTP request failed."),
                code=400,
            )

        response_data = response_payload.get("response") or {}
        returned_transaction_id = (response_payload.get("transactionID") or transaction_id or "").strip()
        if not returned_transaction_id:
            returned_transaction_id = transaction_id

        masked_mobile = (response_data.get("maskedMobile") or "").strip()
        masked_email = (response_data.get("maskedEmail") or "").strip()
        session_store = self._get_fayda_otp_session_store()
        session_store[returned_transaction_id] = {
            "status": "requested",
            "partner_id": partner.id,
            "farmer_id": farmer.id,
            "identifier": identifier_info["identifier"],
            "identifier_type": identifier_info["identifier_type"],
            "identifier_source": identifier_info["identifier_source"],
            "masked_mobile": masked_mobile,
            "masked_email": masked_email,
            "preferred_phone": preferred_phone,
            "message": "OTP requested successfully.",
            "requested_at": fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._mark_session_modified()

        message = "OTP sent successfully."
        if masked_mobile:
            message = "OTP sent to %s." % masked_mobile

        return self._success(
            data={
                "transaction_id": returned_transaction_id,
                "masked_mobile": masked_mobile,
                "masked_email": masked_email,
                "identifier_type": identifier_info["identifier_type"],
                "identifier_source": identifier_info["identifier_source"],
            },
            message=message,
        )

    @http.route("/consent/fayda/verify_otp", type="json", auth="user")
    def consent_fayda_verify_otp(self, farmer_id=None, transaction_id=None, otp_code=None, otp=None, **kw):
        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)

        try:
            farmer_id = int(farmer_id or 0)
        except (TypeError, ValueError):
            farmer_id = 0
        if not farmer_id:
            return self._error("Select a farmer before verifying OTP.")

        farmer = (
            request.env["res.partner"]
            .sudo()
            .search(self._approved_farmer_domain() + [("id", "=", farmer_id)], limit=1)
        )
        if not farmer:
            return self._error("Approved farmer not found.")

        transaction_id = (transaction_id or "").strip()
        otp_code = (otp_code or otp or "").strip()
        if not transaction_id:
            return self._error("Request OTP first.")
        if not otp_code:
            return self._error("Enter the OTP code.")

        session_store = self._get_fayda_otp_session_store()
        session_entry = session_store.get(transaction_id)
        if not isinstance(session_entry, dict):
            return self._error("OTP session expired or was not found.")
        if session_entry.get("partner_id") != partner.id or session_entry.get("farmer_id") != farmer.id:
            return self._error("OTP session does not match the selected farmer.", code=403)
        if session_entry.get("status") == "verified":
            return self._success(
                data={
                    "transaction_id": transaction_id,
                    "masked_mobile": session_entry.get("masked_mobile") or "",
                    "verified_at": session_entry.get("verified_at") or "",
                },
                message="OTP already verified.",
            )

        try:
            config = self._get_fayda_otp_config()
            verify_time = self._now_iso_millis()
            payload = {
                "id": config["client_id"],
                "clientSecret": config["client_secret"],
                "version": config["version"],
                "requestTime": verify_time,
                "env": config["env"],
                "domainUri": config["domain_uri"],
                "transactionID": transaction_id,
                "requestedAuth": {
                    "otp": True,
                    "demo": False,
                    "bio": False,
                },
                "consentObtained": True,
                "individualId": session_entry.get("identifier") or "",
                "individualIdType": session_entry.get("identifier_type") or config["identifier_type"],
                "thumbprint": config["thumbprint"],
                "requestSessionKey": config["request_session_key"],
                "requestHMAC": config["request_hmac"],
                "request": {
                    "timestamp": verify_time,
                    "otp": otp_code,
                },
            }
            response_payload = self._call_fayda_otp_api("/getDataAuth", payload)
        except ValueError as exc:
            session_entry["status"] = "error"
            session_entry["message"] = str(exc)[:1024]
            self._mark_session_modified()
            return self._error(str(exc), code=500)

        errors = response_payload.get("errors")
        response_data = response_payload.get("response") or {}
        auth_status = bool(response_data.get("authStatus"))
        if errors or not auth_status:
            message = self._normalize_fayda_error_message(
                errors,
                "OTP verification failed.",
            )
            session_entry["status"] = "failed"
            session_entry["message"] = message[:1024]
            self._mark_session_modified()
            return self._error(message, code=400)

        verified_at = fields.Datetime.to_string(fields.Datetime.now())
        session_entry["status"] = "verified"
        session_entry["message"] = "OTP verified successfully."
        session_entry["verified_at"] = verified_at
        self._mark_session_modified()
        return self._success(
            data={
                "transaction_id": transaction_id,
                "masked_mobile": session_entry.get("masked_mobile") or "",
                "verified_at": verified_at,
            },
            message="OTP verified successfully.",
        )

    @http.route("/consent/liveness/request_challenge", type="json", auth="user")
    def consent_liveness_request_challenge(self, farmer_id=None, **kw):
        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)

        try:
            farmer_id = int(farmer_id or 0)
        except (TypeError, ValueError):
            farmer_id = 0
        if not farmer_id:
            return self._error("Select a farmer before requesting liveness challenge.")

        farmer = (
            request.env["res.partner"]
            .sudo()
            .search(self._approved_farmer_domain() + [("id", "=", farmer_id)], limit=1)
        )
        if not farmer:
            return self._error("Approved farmer not found.")

        config = self._get_liveness_config()
        challenge_id = self._make_liveness_challenge_id()
        nonce = self._make_liveness_nonce()
        prompt_sequence = self._random_liveness_prompt_sequence()
        issued_at = fields.Datetime.now()
        expires_at = issued_at + timedelta(seconds=config["ttl_seconds"])

        session_store = self._prune_liveness_session_store()
        session_store[challenge_id] = {
            "status": "issued",
            "partner_id": partner.id,
            "farmer_id": farmer.id,
            "nonce": nonce,
            "prompt_sequence": prompt_sequence,
            "issued_at": fields.Datetime.to_string(issued_at),
            "expires_at": fields.Datetime.to_string(expires_at),
            "verification_token": "",
            "verified_at": False,
            "consumed": False,
            "consumed_at": False,
            "provider_reference": False,
            "face_match_passed": False,
            "face_match_distance": False,
            "face_match_threshold": 0.45,
            "message": "Liveness challenge issued.",
        }
        self._mark_session_modified()

        return self._success(
            data={
                "challenge_id": challenge_id,
                "nonce": nonce,
                "prompt_sequence": prompt_sequence,
                "issued_at": fields.Datetime.to_string(issued_at),
                "expires_at": fields.Datetime.to_string(expires_at),
                "ttl_seconds": config["ttl_seconds"],
            },
            message="Liveness challenge issued. Complete the prompt and capture your photo.",
        )

    @http.route("/consent/liveness/verify_challenge", type="json", auth="user")
    def consent_liveness_verify_challenge(
        self,
        farmer_id=None,
        challenge_id=None,
        capture_image=None,
        captured_at=None,
        face_match_passed=None,
        face_match_distance=None,
        face_match_threshold=None,
        **kw
    ):
        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)

        try:
            farmer_id = int(farmer_id or 0)
        except (TypeError, ValueError):
            farmer_id = 0
        if not farmer_id:
            return self._error("Select a farmer before verifying liveness.")

        farmer = (
            request.env["res.partner"]
            .sudo()
            .search(self._approved_farmer_domain() + [("id", "=", farmer_id)], limit=1)
        )
        if not farmer:
            return self._error("Approved farmer not found.")

        challenge_id = (challenge_id or "").strip()
        if not challenge_id:
            return self._error("Liveness challenge ID is required.")

        image_payload = (capture_image or "").strip()
        if not image_payload:
            return self._error("Capture a photo before verifying liveness.")

        raw_base64 = image_payload.split(",", 1)[1] if "," in image_payload else image_payload
        approx_bytes = int((len(raw_base64) * 3) / 4) if raw_base64 else 0
        if approx_bytes > self._MAX_ATTACHMENT_SIZE:
            return self._error("Captured image exceeds the allowed size.")

        session_store = self._prune_liveness_session_store()
        session_entry = session_store.get(challenge_id)
        if not isinstance(session_entry, dict):
            return self._error("Liveness challenge was not found or expired.")

        if (
            session_entry.get("partner_id") != partner.id
            or session_entry.get("farmer_id") != farmer.id
        ):
            return self._error("Liveness challenge does not match the selected farmer.", code=403)

        expires_at = self._parse_session_datetime(session_entry.get("expires_at"))
        if expires_at and expires_at < fields.Datetime.now():
            session_entry["status"] = "expired"
            session_entry["message"] = "Liveness challenge expired."
            self._mark_session_modified()
            return self._error("Liveness challenge expired. Request a new challenge.")

        if session_entry.get("consumed"):
            return self._error("Liveness challenge already used. Request a new challenge.")

        existing_token = (session_entry.get("verification_token") or "").strip()
        if (
            session_entry.get("status") == "verified"
            and existing_token
            and session_entry.get("face_match_passed")
        ):
            return self._success(
                data={
                    "challenge_id": challenge_id,
                    "verification_token": existing_token,
                    "verified_at": session_entry.get("verified_at") or "",
                    "provider_reference": session_entry.get("provider_reference") or "",
                    "prompt_sequence": session_entry.get("prompt_sequence") or [],
                    "face_match_distance": session_entry.get("face_match_distance"),
                    "face_match_threshold": session_entry.get("face_match_threshold"),
                },
                message="Face match + liveness challenge already verified.",
            )

        def _as_bool(raw_value):
            if isinstance(raw_value, bool):
                return raw_value
            text = str(raw_value or "").strip().lower()
            return text in {"1", "true", "t", "yes", "y", "on"}

        def _as_float(raw_value, default=None):
            try:
                return float(raw_value)
            except (TypeError, ValueError):
                return default

        client_face_match_passed = _as_bool(face_match_passed)
        client_face_match_distance = _as_float(face_match_distance, None)
        client_face_match_threshold = _as_float(face_match_threshold, 0.45)
        if not client_face_match_threshold or client_face_match_threshold <= 0:
            client_face_match_threshold = 0.45

        verify_payload = {
            "challenge_id": challenge_id,
            "nonce": session_entry.get("nonce") or "",
            "partner_id": partner.id,
            "farmer_id": farmer.id,
            "prompt_sequence": session_entry.get("prompt_sequence") or [],
            "capture_image": image_payload,
            "captured_at": (captured_at or "").strip() or fields.Datetime.to_string(fields.Datetime.now()),
            "face_match_passed": client_face_match_passed,
            "face_match_distance": client_face_match_distance,
            "face_match_threshold": client_face_match_threshold,
        }

        try:
            verification_payload = self._call_liveness_provider_verify(verify_payload)
        except ValueError as exc:
            session_entry["status"] = "error"
            session_entry["message"] = str(exc)[:1024]
            self._mark_session_modified()
            return self._error(str(exc), code=500)

        provider_challenge_id = (verification_payload.get("challenge_id") or "").strip()
        if provider_challenge_id and provider_challenge_id != challenge_id:
            session_entry["status"] = "error"
            session_entry["message"] = "Provider challenge mismatch."
            self._mark_session_modified()
            return self._error("Provider challenge mismatch.", code=400)

        provider_nonce = (verification_payload.get("nonce") or "").strip()
        expected_nonce = (session_entry.get("nonce") or "").strip()
        if provider_nonce and provider_nonce != expected_nonce:
            session_entry["status"] = "error"
            session_entry["message"] = "Provider nonce mismatch."
            self._mark_session_modified()
            return self._error("Provider nonce mismatch.", code=400)

        provider_liveness_passed = bool(verification_payload.get("passed"))
        provider_face_match_passed = verification_payload.get("face_match_passed")
        if provider_face_match_passed in (None, ""):
            provider_face_match_passed = client_face_match_passed
        else:
            provider_face_match_passed = _as_bool(provider_face_match_passed)

        provider_face_match_distance = _as_float(
            verification_payload.get("face_match_distance"),
            client_face_match_distance,
        )
        provider_face_match_threshold = _as_float(
            verification_payload.get("face_match_threshold"),
            client_face_match_threshold,
        )
        if not provider_face_match_threshold or provider_face_match_threshold <= 0:
            provider_face_match_threshold = 0.45
        if provider_face_match_distance is not None and provider_face_match_distance < 0:
            provider_face_match_distance = None
        if (
            provider_face_match_passed
            and provider_face_match_distance is not None
            and provider_face_match_distance > provider_face_match_threshold
        ):
            provider_face_match_passed = False

        passed = bool(provider_liveness_passed and provider_face_match_passed)

        provider_message = str(verification_payload.get("message") or "").strip()
        if not provider_message:
            if not provider_liveness_passed:
                provider_message = "Liveness verification failed. Capture a new image and try again."
            elif not provider_face_match_passed:
                provider_message = "Face match failed. Retake and align to the selected farmer."
            else:
                provider_message = "Face match + liveness challenge verified."
        checked_at = fields.Datetime.to_datetime(verification_payload.get("checked_at")) or fields.Datetime.now()

        if not passed:
            session_entry["status"] = "failed"
            session_entry["message"] = provider_message[:1024]
            session_entry["verified_at"] = False
            session_entry["verification_token"] = ""
            session_entry["face_match_passed"] = bool(provider_face_match_passed)
            session_entry["face_match_distance"] = provider_face_match_distance
            session_entry["face_match_threshold"] = provider_face_match_threshold
            self._mark_session_modified()
            return self._error(provider_message, code=400)

        verification_token = uuid4().hex
        provider_reference = str(verification_payload.get("provider_reference") or "").strip()
        session_entry["status"] = "verified"
        session_entry["message"] = provider_message[:1024]
        session_entry["verified_at"] = fields.Datetime.to_string(checked_at)
        session_entry["verification_token"] = verification_token
        session_entry["provider_reference"] = provider_reference
        session_entry["score"] = verification_payload.get("score")
        session_entry["face_match_passed"] = True
        session_entry["face_match_distance"] = provider_face_match_distance
        session_entry["face_match_threshold"] = provider_face_match_threshold
        session_entry["consumed"] = False
        session_entry["consumed_at"] = False
        self._mark_session_modified()

        return self._success(
            data={
                "challenge_id": challenge_id,
                "verification_token": verification_token,
                "verified_at": fields.Datetime.to_string(checked_at),
                "score": verification_payload.get("score"),
                "provider_reference": provider_reference,
                "prompt_sequence": session_entry.get("prompt_sequence") or [],
                "face_match_distance": provider_face_match_distance,
                "face_match_threshold": provider_face_match_threshold,
            },
            message=provider_message,
        )

    @http.route("/consent/request/submit", type="http", auth="user", methods=["POST"], csrf=True)
    def consent_request_submit(self, **post):
        """Create a consent request from portal form (with optional attachment)."""
        try:
            partner = self._get_consent_partner()
            user_id = request.env.user.id
            posted_farmer = post.get("farmer_id")

            def _reject(error_code):
                _logger.warning(
                    "Consent portal submit rejected: %s user_id=%s partner_id=%s farmer_input=%s",
                    error_code,
                    user_id,
                    partner.id if partner else None,
                    posted_farmer,
                )
                return request.redirect(f"/consent/management?error={error_code}")

            _logger.info(
                "Consent portal submit attempt user_id=%s partner_id=%s farmer_input=%s",
                user_id,
                partner.id if partner else None,
                posted_farmer,
            )
            if not partner:
                return _reject("access_denied")

            farmer_id = post.get("farmer_id")
            if not farmer_id:
                return _reject("missing_farmer")

            try:
                farmer_id = int(farmer_id)
            except (TypeError, ValueError):
                return _reject("invalid_farmer")

            farmer = (
                request.env["res.partner"]
                .sudo()
                .search(self._approved_farmer_domain() + [("id", "=", farmer_id)], limit=1)
            )
            if not farmer:
                return _reject("farmer_not_found")

            consent_type = post.get("consent_type", "specific") or "specific"
            consent_reason = request.env["g2p.consent.reason"].sudo().browse()
            consent_reason_id = post.get("consent_reason_id")
            if consent_reason_id:
                try:
                    consent_reason_id = int(consent_reason_id)
                except (TypeError, ValueError):
                    return _reject("invalid_consent_reason")
                consent_reason = request.env["g2p.consent.reason"].sudo().search(
                    [
                        ("id", "=", consent_reason_id),
                        ("active", "=", True),
                    ],
                    limit=1,
                )
                if not consent_reason:
                    return _reject("invalid_consent_reason")
            legacy_purpose = (post.get("purpose") or "").strip()
            if not consent_reason and not legacy_purpose:
                return _reject("missing_consent_reason")
            purpose = consent_reason.name if consent_reason else legacy_purpose
            validity_months = post.get("validity_months")
            try:
                validity_months = int(validity_months) if validity_months else 12
            except (TypeError, ValueError):
                validity_months = 12
            
            form_data = request.httprequest.form or {}
            allowed_data_field_ids = form_data.getlist("allowed_data_field_ids") if hasattr(form_data, "getlist") else []
            if not allowed_data_field_ids and post.get("allowed_data_field_ids"):
                # Fallback for edge cases where only kwargs are populated.
                allowed_data_field_ids = [post.get("allowed_data_field_ids")]
            allowed_ids = []
            for fid in allowed_data_field_ids:
                try:
                    allowed_ids.append(int(fid))
                except (TypeError, ValueError):
                    pass
            
            allowed_ids = [i for i in allowed_ids if i in partner.allowed_data_field_ids.ids]
            if not allowed_ids:
                _logger.warning(
                    "Consent portal submit blocked by allowed_data_field_ids user_id=%s partner_id=%s partner_allowed_count=%s posted_field_count=%s",
                    user_id,
                    partner.id,
                    len(partner.allowed_data_field_ids.ids),
                    len(allowed_data_field_ids),
                )
                return _reject("missing_data_fields")
            
            now = fields.Datetime.now()
            validity_from = now
            validity_to = now + timedelta(days=validity_months * 30)
            
            vals = {
                "partner_record_id": partner.id,
                "farmer_id": farmer_id,
                "consent_type": consent_type,
                "purpose": purpose,
                "consent_reason_id": consent_reason.id or False,
                "validity_from": validity_from,
                "validity_to": validity_to,
                "originated_from": "partner",
                "status": "pending",
                "requester_user_id": request.env.user.id,
            }
            
            if allowed_ids:
                vals["allowed_data_field_ids"] = [(6, 0, allowed_ids)]
            
            attachment_ids = []
            auto_approve_requested = False
            auto_approve_method = ""
            otp_transaction_id = None
            liveness_challenge_id = None
            try:
                files = request.httprequest.files or {}
                upload = files.get("attachment")
                if not upload or not getattr(upload, "filename", None):
                    return _reject("missing_attachment")

                upload_data = upload.read()
                if not upload_data:
                    return _reject("missing_attachment")
                if len(upload_data) > self._MAX_ATTACHMENT_SIZE:
                    return _reject("attachment_too_large")

                Attachment = request.env["ir.attachment"].sudo()
                att = Attachment.create(
                    {
                        "name": upload.filename or "consent_form.pdf",
                        "datas": base64.b64encode(upload_data),
                        "res_model": "g2p.consent.request",
                        "res_id": 0,
                    }
                )
                attachment_ids.append(att.id)
                vals["attachment_ids"] = [(6, 0, attachment_ids)]

                camera_data_b64 = (post.get("camera_capture_data") or "").strip()
                if camera_data_b64:
                    if "," in camera_data_b64:
                        camera_data_b64 = camera_data_b64.split(",", 1)[1]
                    try:
                        camera_data = base64.b64decode(camera_data_b64, validate=True)
                    except Exception:
                        return _reject("invalid_camera_data")
                    if len(camera_data) > self._MAX_ATTACHMENT_SIZE:
                        return _reject("camera_too_large")
                    vals["portal_capture_image"] = base64.b64encode(camera_data)
                    vals["portal_capture_image_filename"] = "camera_capture.jpg"
                    capture_ts_raw = (post.get("camera_capture_taken_at") or "").strip()
                    if capture_ts_raw:
                        capture_dt = fields.Datetime.to_datetime(capture_ts_raw)
                        if not capture_dt:
                            return _reject("invalid_camera_timestamp")
                        vals["portal_capture_taken_at"] = fields.Datetime.to_string(capture_dt)

                liveness_vals, liveness_auto_approve, liveness_challenge_id = self._extract_liveness_values(
                    post,
                    farmer,
                    partner,
                    has_camera_capture=bool(camera_data_b64),
                )
                vals.update(liveness_vals)

                fayda_otp_vals, otp_auto_approve, otp_transaction_id = self._extract_fayda_otp_values(
                    post,
                    farmer,
                    partner,
                )
                vals.update(fayda_otp_vals)
                if otp_auto_approve:
                    auto_approve_requested = True
                    auto_approve_method = "otp"
                elif liveness_auto_approve:
                    auto_approve_requested = True
                    auto_approve_method = "liveness"

                lat_raw = (post.get("camera_capture_latitude") or "").strip()
                lon_raw = (post.get("camera_capture_longitude") or "").strip()
                acc_raw = (post.get("camera_capture_accuracy") or "").strip()
                if lat_raw or lon_raw:
                    if not lat_raw or not lon_raw:
                        return _reject("invalid_camera_location")
                    try:
                        latitude = float(lat_raw)
                        longitude = float(lon_raw)
                    except (TypeError, ValueError):
                        return _reject("invalid_camera_location")
                    if latitude < -90 or latitude > 90 or longitude < -180 or longitude > 180:
                        return _reject("invalid_camera_location")
                    vals["portal_capture_latitude"] = latitude
                    vals["portal_capture_longitude"] = longitude
                if acc_raw:
                    try:
                        accuracy = float(acc_raw)
                    except (TypeError, ValueError):
                        return _reject("invalid_camera_location")
                    if accuracy < 0:
                        return _reject("invalid_camera_location")
                    vals["portal_capture_accuracy_m"] = accuracy
            except Exception as e:
                _logger.error("Error processing attachments/camera capture: %s", e, exc_info=True)
                return _reject("server_error")
            
            ConsentRequest = request.env["g2p.consent.request"].sudo()
            consent = ConsentRequest.create(vals)

            for att_id in attachment_ids:
                request.env["ir.attachment"].sudo().browse(att_id).write({"res_id": consent.id})

            auto_approved = False
            auto_approval_failed = False
            if auto_approve_requested:
                try:
                    consent.action_approve()
                    approval_flag_field = (
                        "auto_approved_via_otp"
                        if auto_approve_method == "otp"
                        else "auto_approved_via_face_match"
                    )
                    consent.sudo().write({approval_flag_field: True})
                    auto_approved = consent.status == "approved"
                except Exception as approval_error:
                    auto_approval_failed = True
                    _logger.exception(
                        "Consent portal automatic approval failed for consent id=%s method=%s",
                        consent.id,
                        auto_approve_method,
                    )
                    if auto_approve_method == "otp":
                        failure_note = "Fayda OTP passed, but automatic approval failed: %s" % approval_error
                        message_field = "fayda_otp_message"
                    else:
                        failure_note = "Face + liveness verification passed, but automatic approval failed: %s" % approval_error
                        message_field = "face_match_message"
                    existing_message = (getattr(consent, message_field) or "").strip()
                    combined_message = failure_note if not existing_message else "%s\n%s" % (existing_message, failure_note)
                    consent.sudo().write({message_field: combined_message[:1024]})

            if otp_transaction_id:
                session_store = self._get_fayda_otp_session_store()
                if session_store.pop(otp_transaction_id, None) is not None:
                    self._mark_session_modified()
            if liveness_challenge_id:
                liveness_store = self._get_liveness_session_store()
                if liveness_store.pop(liveness_challenge_id, None) is not None:
                    self._mark_session_modified()
            
            _logger.info(
                "Consent request created via portal: id=%s farmer_id=%s partner_id=%s user_id=%s allowed_field_count=%s face_match_status=%s fayda_otp_status=%s auto_approved=%s auto_approve_method=%s",
                consent.id,
                consent.farmer_id.id,
                consent.partner_record_id.id,
                user_id,
                len(allowed_ids),
                consent.face_match_status,
                consent.fayda_otp_status,
                auto_approved,
                auto_approve_method or "none",
            )
            redirect_url = "/consent/management?success=1"
            if auto_approved:
                redirect_url += "&auto_approved=1&auto_approved_method=%s" % (auto_approve_method or "manual")
            elif auto_approval_failed:
                redirect_url += "&auto_approval_failed=1&auto_approval_failed_method=%s" % (
                    auto_approve_method or "manual"
                )
            return request.redirect(redirect_url)
        except Exception as e:
            _logger.error("Error creating consent request: %s", e, exc_info=True)
            return request.redirect("/consent/management?error=server_error")

    @http.route("/api/consent/request/create", type="json", auth="user", methods=["POST"], csrf=False)
    def create_consent_request(self, **kwargs):
        payload = request.jsonrequest or {}
        partner_record_id = payload.get("partner_record_id") or payload.get("partner_id")
        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)
        if not partner_record_id:
            return self._error("partner_id is required")
        try:
            requested_partner_id = int(partner_record_id)
        except (TypeError, ValueError):
            return self._error("Invalid partner_id")
        if requested_partner_id != partner.id:
            return self._error("Access denied", code=403)

        farmer = self._find_farmer(payload)
        if not farmer:
            return self._error("Farmer not found. Provide farmer_db_id, farmer_id or national_id")

        partner_record = request.env["res.partner"].sudo().browse(requested_partner_id)
        if not partner_record.exists() or not partner_record.is_consent_parent:
            return self._error("Consent partner not found")
        if not partner_record.active:
            return self._error("Consent partner is inactive")

        consent_reason = request.env["g2p.consent.reason"].sudo().browse()
        consent_reason_id = payload.get("consent_reason_id")
        if consent_reason_id:
            try:
                consent_reason_id = int(consent_reason_id)
            except (TypeError, ValueError):
                return self._error("Invalid consent_reason_id")
            consent_reason = request.env["g2p.consent.reason"].sudo().search(
                [("id", "=", consent_reason_id)],
                limit=1,
            )
            if not consent_reason:
                return self._error("Consent reason not found")

        purpose = (payload.get("purpose") or "").strip()
        if consent_reason:
            purpose = consent_reason.name
        if not purpose:
            return self._error("consent_reason_id is required")

        vals = {
            "partner_record_id": partner_record.id,
            "farmer_id": farmer.id,
            "consent_type": payload.get("consent_type", "specific"),
            "consent_provider_register": payload.get("consent_provider_register"),
            "consent_provider_person_id": payload.get("consent_provider_person_id"),
            "consent_target_object_ids": payload.get("consent_target_object_ids"),
            "attribute_lists": payload.get("attribute_lists"),
            "purpose": purpose,
            "consent_reason_id": consent_reason.id or False,
            "originated_from": payload.get("originated_from"),
            "validity_from": payload.get("validity_from"),
            "validity_to": payload.get("validity_to"),
            "rejection_reason": payload.get("rejection_reason"),
            "requester_user_id": request.env.user.id,
        }

        if payload.get("consent_creation_request_id"):
            vals["consent_creation_request_id"] = payload.get("consent_creation_request_id")

        allowed_data_field_ids = payload.get("allowed_data_field_ids") or []
        allowed_by_partner = set(partner_record.allowed_data_field_ids.ids)
        normalized_allowed_ids = []
        for field_id in allowed_data_field_ids:
            try:
                normalized_allowed_ids.append(int(field_id))
            except (TypeError, ValueError):
                continue
        filtered_allowed_ids = [field_id for field_id in normalized_allowed_ids if field_id in allowed_by_partner]
        if not filtered_allowed_ids:
            return self._error(
                "No valid allowed_data_field_ids for this partner. Configure partner allowed data fields first."
            )
        vals["allowed_data_field_ids"] = [(6, 0, filtered_allowed_ids)]

        consent = request.env["g2p.consent.request"].sudo().create(vals)

        _logger.info(
            "Consent request created via API: id=%s request_id=%s farmer_id=%s partner_id=%s",
            consent.id,
            consent.consent_creation_request_id,
            consent.farmer_id.id,
            consent.partner_record_id.id,
        )

        return self._success(
            {
                "id": consent.id,
                "consent_creation_request_id": consent.consent_creation_request_id,
                "status": consent.status,
            },
            message="Consent request created",
        )

    @http.route("/api/consent/request/approve", type="json", auth="user", methods=["POST"], csrf=False)
    def approve_consent_request(self, **kwargs):
        payload = request.jsonrequest or {}
        consent_id = payload.get("consent_id")
        consent_request_id = payload.get("consent_creation_request_id")

        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)

        domain = self._get_portal_consent_request_domain(partner)
        if consent_id:
            domain.append(("id", "=", int(consent_id)))
        elif consent_request_id:
            domain.append(("consent_creation_request_id", "=", consent_request_id))
        else:
            return self._error("Provide consent_id or consent_creation_request_id")

        consent = request.env["g2p.consent.request"].sudo().search(domain, limit=1)
        if not consent:
            return self._error("Consent request not found", code=404)

        consent.action_approve()
        return self._success(
            {
                "id": consent.id,
                "consent_creation_request_id": consent.consent_creation_request_id,
                "status": consent.status,
            },
            message="Consent request approved",
        )

    @http.route("/api/consent/request/reject", type="json", auth="user", methods=["POST"], csrf=False)
    def reject_consent_request(self, **kwargs):
        payload = request.jsonrequest or {}
        consent_id = payload.get("consent_id")
        consent_request_id = payload.get("consent_creation_request_id")

        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)

        domain = self._get_portal_consent_request_domain(partner)
        if consent_id:
            domain.append(("id", "=", int(consent_id)))
        elif consent_request_id:
            domain.append(("consent_creation_request_id", "=", consent_request_id))
        else:
            return self._error("Provide consent_id or consent_creation_request_id")

        consent = request.env["g2p.consent.request"].sudo().search(domain, limit=1)
        if not consent:
            return self._error("Consent request not found", code=404)

        rejection_reason = payload.get("rejection_reason")
        if rejection_reason:
            consent.write({"rejection_reason": rejection_reason})

        consent.action_reject()
        return self._success(
            {
                "id": consent.id,
                "consent_creation_request_id": consent.consent_creation_request_id,
                "status": consent.status,
            },
            message="Consent request rejected",
        )

    @http.route("/api/consent/request/revoke", type="json", auth="user", methods=["POST"], csrf=False)
    def revoke_consent_request(self, **kwargs):
        payload = request.jsonrequest or {}
        consent_id = payload.get("consent_id")
        consent_request_id = payload.get("consent_creation_request_id")

        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)

        domain = self._get_portal_consent_request_domain(partner)
        if consent_id:
            domain.append(("id", "=", int(consent_id)))
        elif consent_request_id:
            domain.append(("consent_creation_request_id", "=", consent_request_id))
        else:
            return self._error("Provide consent_id or consent_creation_request_id")

        consent = request.env["g2p.consent.request"].sudo().search(domain, limit=1)
        if not consent:
            return self._error("Consent request not found", code=404)

        consent.action_revoke()
        return self._success(
            {
                "id": consent.id,
                "consent_creation_request_id": consent.consent_creation_request_id,
                "status": consent.status,
            },
            message="Consent request revoked",
        )

    @http.route("/api/consent/request/pending", type="json", auth="user", methods=["POST"], csrf=False)
    def list_pending_consent_requests(self, **kwargs):
        payload = request.jsonrequest or {}
        limit = int(payload.get("limit", 80))
        partner = self._get_consent_partner()
        if not partner:
            return self._error("Access denied", code=403)

        consents = request.env["g2p.consent.request"].sudo().search(
            self._get_portal_consent_request_domain(partner) + [("status", "=", "pending")],
            limit=limit,
        )
        return self._success(
            {
                "count": len(consents),
                "items": [
                    {
                        "id": consent.id,
                        "consent_creation_request_id": consent.consent_creation_request_id,
                        "farmer_id": consent.farmer_id.id,
                        "farmer_name": consent.farmer_id.display_name,
                        "partner_id": consent.partner_record_id.id,
                        "partner_name": consent.partner_record_id.name,
                        "status": consent.status,
                    }
                    for consent in consents
                ],
            }
        )
