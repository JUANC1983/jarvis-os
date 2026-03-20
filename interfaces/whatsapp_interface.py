class WhatsAppInterface:
    def __init__(self):
        self.provider = "twilio"

    def receive_message(self, phone: str, message: str):
        return {
            "phone": phone,
            "message": message,
            "status": "received",
            "provider": self.provider,
        }

    def send_message(self, phone: str, text: str):
        return {
            "phone": phone,
            "message": text,
            "status": "sent",
            "provider": self.provider,
        }
