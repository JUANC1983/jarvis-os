class EmailIntelligenceEngine:
    def draft_reply(self, sender: str, subject: str, body: str, tone: str = "executive"):
        return {
            "sender": sender,
            "subject": subject,
            "tone": tone,
            "draft_reply": (
                f"Hello,\n\n"
                f"Thank you for your message regarding '{subject}'. "
                f"I reviewed the context and suggest the following next steps.\n\n"
                f"Best regards,\nJuan Camilo Montenegro"
            ),
        }
