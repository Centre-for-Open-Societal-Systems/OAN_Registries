#!/usr/bin/env python3
"""
Simple mock Fayda OTP API.

Implements the two endpoints used by g2p_ati_consent_mgt:
- POST /requestData
- POST /getDataAuth

Run:
    python3 /opt/odoo17/mock_fayda_otp_api.py

Point Odoo to it:
    export G2P_FAYDA_OTP_BASE_URL=http://127.0.0.1:8787
    export G2P_FAYDA_OTP_CLIENT_ID=demo-client
    export G2P_FAYDA_OTP_CLIENT_SECRET=demo-secret

Optional env vars:
    MOCK_FAYDA_HOST=127.0.0.1
    MOCK_FAYDA_PORT=8787
    MOCK_FAYDA_CLIENT_ID=demo-client
    MOCK_FAYDA_CLIENT_SECRET=demo-secret
    MOCK_FAYDA_ENV=prod
    MOCK_FAYDA_DOMAIN_URI=fayda.et
    MOCK_FAYDA_MASKED_MOBILE=09xxxxxx55

Optional request field:
    preferredPhoneNumber=the farmer primary phone number to mask in the response
"""

from __future__ import annotations

import json
import os
import random
import signal
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from typing import Any


HOST = os.getenv("MOCK_FAYDA_HOST", "127.0.0.1")
PORT = int(os.getenv("MOCK_FAYDA_PORT", "8787"))
CLIENT_ID = os.getenv("MOCK_FAYDA_CLIENT_ID", "demo-client")
CLIENT_SECRET = os.getenv("MOCK_FAYDA_CLIENT_SECRET", "demo-secret")
DEFAULT_ENV = os.getenv("MOCK_FAYDA_ENV", "prod")
DEFAULT_DOMAIN_URI = os.getenv("MOCK_FAYDA_DOMAIN_URI", "fayda.et")
DEFAULT_MASKED_MOBILE = os.getenv("MOCK_FAYDA_MASKED_MOBILE", "09xxxxxx55")


class MockState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._transactions: dict[str, dict[str, Any]] = {}

    def put(self, transaction_id: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._transactions[transaction_id] = value

    def get(self, transaction_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._transactions.get(transaction_id)
            return dict(row) if row else None

    def update(self, transaction_id: str, **kwargs: Any) -> dict[str, Any] | None:
        with self._lock:
            row = self._transactions.get(transaction_id)
            if not row:
                return None
            row.update(kwargs)
            return dict(row)


STATE = MockState()


def now_iso_millis() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def json_response(
    *,
    client_id: str,
    transaction_id: str,
    response: dict[str, Any] | None,
    errors: Any,
) -> dict[str, Any]:
    return {
        "id": client_id,
        "version": "1.0",
        "responseTime": now_iso_millis(),
        "transactionID": transaction_id,
        "response": response,
        "errors": errors,
    }


def normalize_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def require_fields(payload: dict[str, Any], names: list[str]) -> list[str]:
    missing = []
    for name in names:
        value = payload.get(name)
        if value in (None, "", []):
            missing.append(name)
    return missing


def mask_phone_number(phone_number: str) -> str:
    digits = "".join(ch for ch in str(phone_number or "") if ch.isdigit())
    if len(digits) < 4:
        return DEFAULT_MASKED_MOBILE
    visible_prefix = digits[:2]
    visible_suffix = digits[-2:]
    hidden_length = max(len(digits) - 4, 2)
    return "%s%s%s" % (visible_prefix, "x" * hidden_length, visible_suffix)


class Handler(BaseHTTPRequestHandler):
    server_version = "MockFaydaOTP/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))
        sys.stdout.flush()

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""
        return normalize_body(body)

    def _auth_error(self, payload: dict[str, Any], message: str) -> None:
        transaction_id = str(payload.get("transactionID") or "")
        self._send_json(
            401,
            json_response(
                client_id=str(payload.get("id") or ""),
                transaction_id=transaction_id,
                response=None,
                errors=message,
            ),
        )

    def _validate_client(self, payload: dict[str, Any]) -> bool:
        if payload.get("id") != CLIENT_ID or payload.get("clientSecret") != CLIENT_SECRET:
            self._auth_error(payload, "Invalid client credentials")
            return False
        return True

    def do_POST(self) -> None:
        try:
            if self.path == "/requestData":
                self.handle_request_data()
                return
            if self.path == "/getDataAuth":
                self.handle_get_data_auth()
                return
            self._send_json(404, {"message": "Unknown endpoint"})
        except json.JSONDecodeError:
            self._send_json(400, {"message": "Invalid JSON body"})
        except Exception as exc:  # pragma: no cover
            self._send_json(500, {"message": "Mock server error", "detail": str(exc)})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "host": HOST,
                    "port": PORT,
                    "client_id": CLIENT_ID,
                    "env": DEFAULT_ENV,
                    "domainUri": DEFAULT_DOMAIN_URI,
                },
            )
            return
        self._send_json(404, {"message": "Unknown endpoint"})

    def handle_request_data(self) -> None:
        payload = self._read_json()
        if not self._validate_client(payload):
            return

        missing = require_fields(
            payload,
            [
                "id",
                "clientSecret",
                "version",
                "requestTime",
                "env",
                "domainUri",
                "transactionID",
                "individualId",
                "individualIdType",
                "otpChannel",
            ],
        )
        transaction_id = str(payload.get("transactionID") or "")
        client_id = str(payload.get("id") or "")
        if missing:
            self._send_json(
                400,
                json_response(
                    client_id=client_id,
                    transaction_id=transaction_id,
                    response=None,
                    errors="Missing required fields: %s" % ", ".join(missing),
                ),
            )
            return

        if payload.get("env") != DEFAULT_ENV:
            self._send_json(
                400,
                json_response(
                    client_id=client_id,
                    transaction_id=transaction_id,
                    response=None,
                    errors="Unsupported env: %s" % payload.get("env"),
                ),
            )
            return

        if payload.get("domainUri") != DEFAULT_DOMAIN_URI:
            self._send_json(
                400,
                json_response(
                    client_id=client_id,
                    transaction_id=transaction_id,
                    response=None,
                    errors="Unsupported domainUri: %s" % payload.get("domainUri"),
                ),
            )
            return

        otp_code = "%06d" % random.randint(0, 999999)
        preferred_phone = str(payload.get("preferredPhoneNumber") or "").strip()
        masked_mobile = (
            mask_phone_number(preferred_phone) if preferred_phone else DEFAULT_MASKED_MOBILE
        )
        STATE.put(
            transaction_id,
            {
                "status": "requested",
                "otp": otp_code,
                "individualId": str(payload.get("individualId") or ""),
                "individualIdType": str(payload.get("individualIdType") or ""),
                "otpChannel": list(payload.get("otpChannel") or []),
                "preferredPhoneNumber": preferred_phone,
                "maskedMobile": masked_mobile,
                "requestedAt": now_iso_millis(),
            },
        )

        print("")
        print("=== MOCK FAYDA OTP GENERATED ===")
        print("transactionID :", transaction_id)
        print("individualId  :", payload.get("individualId"))
        print("idType        :", payload.get("individualIdType"))
        if preferred_phone:
            print("phone         :", preferred_phone)
        print("otp           :", otp_code)
        print("===============================")
        print("")
        sys.stdout.flush()

        self._send_json(
            200,
            json_response(
                client_id=client_id,
                transaction_id=transaction_id,
                response={
                    "maskedMobile": masked_mobile,
                    "maskedEmail": "",
                },
                errors=None,
            ),
        )

    def handle_get_data_auth(self) -> None:
        payload = self._read_json()
        if not self._validate_client(payload):
            return

        missing = require_fields(
            payload,
            [
                "id",
                "clientSecret",
                "version",
                "requestTime",
                "env",
                "domainUri",
                "transactionID",
                "requestedAuth",
                "consentObtained",
                "individualId",
                "individualIdType",
                "request",
            ],
        )
        transaction_id = str(payload.get("transactionID") or "")
        client_id = str(payload.get("id") or "")
        if missing:
            self._send_json(
                400,
                json_response(
                    client_id=client_id,
                    transaction_id=transaction_id,
                    response=None,
                    errors="Missing required fields: %s" % ", ".join(missing),
                ),
            )
            return

        request_payload = payload.get("request") or {}
        otp_code = str(request_payload.get("otp") or "")
        if not otp_code:
            self._send_json(
                400,
                json_response(
                    client_id=client_id,
                    transaction_id=transaction_id,
                    response={"authStatus": False, "authResponseToken": ""},
                    errors="Missing OTP value",
                ),
            )
            return

        row = STATE.get(transaction_id)
        if not row:
            self._send_json(
                404,
                json_response(
                    client_id=client_id,
                    transaction_id=transaction_id,
                    response={"authStatus": False, "authResponseToken": otp_code},
                    errors="Unknown transactionID",
                ),
            )
            return

        if row["individualId"] != str(payload.get("individualId") or ""):
            self._send_json(
                400,
                json_response(
                    client_id=client_id,
                    transaction_id=transaction_id,
                    response={"authStatus": False, "authResponseToken": otp_code},
                    errors="individualId does not match the original request",
                ),
            )
            return

        auth_status = row["otp"] == otp_code
        if auth_status:
            STATE.update(transaction_id, status="verified", verifiedAt=now_iso_millis())
            self._send_json(
                200,
                json_response(
                    client_id=client_id,
                    transaction_id=transaction_id,
                    response={"authStatus": True, "authResponseToken": otp_code},
                    errors=None,
                ),
            )
            return

        STATE.update(transaction_id, status="failed")
        self._send_json(
            400,
            json_response(
                client_id=client_id,
                transaction_id=transaction_id,
                response={"authStatus": False, "authResponseToken": otp_code},
                errors="Invalid OTP",
            ),
        )


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)

    def shutdown_handler(signum: int, frame: Any) -> None:
        print("\nShutting down mock Fayda OTP server...")
        Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print("Mock Fayda OTP server listening on http://%s:%s" % (HOST, PORT))
    print("Expected client id     :", CLIENT_ID)
    print("Expected client secret :", CLIENT_SECRET)
    print("Health endpoint        : http://%s:%s/health" % (HOST, PORT))
    print("")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down mock Fayda OTP server...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
