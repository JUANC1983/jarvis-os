from __future__ import annotations

import os
from typing import Any, Dict, Optional

from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse


class TwilioWhatsAppEngine:
    """
    Twilio WhatsApp integration.
    """

    def __init__(self) -> None:
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
        self.public_base_url = os.getenv("PUBLIC_BASE_URL", "")
        self.client = Client(self.account_sid, self.auth_token) if self.account_sid and self.auth_token else None

    def configured(self) -> bool:
        return bool(self.client and self.from_number)

    def send_text(self, to_number: str, body: str) -> Dict[str, Any]:
        if not self.configured():
            return {
                "status": "error",
                "message": "Missing TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_WHATSAPP_NUMBER in .env",
            }

        message = self.client.messages.create(
            from_=self.from_number,
            to=to_number,
            body=body,
        )

        return {
            "status": "ok",
            "sid": message.sid,
            "to": to_number,
            "body": body,
        }

    def send_media(self, to_number: str, body: str, media_url: str) -> Dict[str, Any]:
        if not self.configured():
            return {
                "status": "error",
                "message": "Missing TWILIO credentials in .env",
            }

        message = self.client.messages.create(
            from_=self.from_number,
            to=to_number,
            body=body,
            media_url=[media_url],
        )

        return {
            "status": "ok",
            "sid": message.sid,
            "to": to_number,
            "body": body,
            "media_url": media_url,
        }

    def inbound_payload(self, form: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "from": form.get("From", ""),
            "to": form.get("To", ""),
            "body": form.get("Body", ""),
            "message_sid": form.get("MessageSid", ""),
            "profile_name": form.get("ProfileName", ""),
            "num_media": form.get("NumMedia", "0"),
        }

    def twiml_reply(self, body: str) -> str:
        resp = MessagingResponse()
        resp.message(body)
        return str(resp)
