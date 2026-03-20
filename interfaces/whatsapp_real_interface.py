from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os

class WhatsAppRealInterface:

    def __init__(self):

        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")

        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None

    def inbound(self, phone, text):

        return {
            "phone": phone,
            "text": text
        }

    def build_outbound(self, phone, text):

        if not self.client:
            return {"error":"Twilio not configured"}

        message = self.client.messages.create(
            from_='whatsapp:+14155238886',
            body=text,
            to=f'whatsapp:{phone}'
        )

        return {
            "status":"sent",
            "sid":message.sid
        }

    def webhook_response(self, text):

        resp = MessagingResponse()
        msg = resp.message()
        msg.body(text)

        return str(resp)
