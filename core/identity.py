import os
from dotenv import load_dotenv

from core.models import OwnerProfile

load_dotenv()


class JarvisIdentity:
    def __init__(self) -> None:
        owner_name = os.getenv("JARVIS_OWNER_NAME", "Juan Camilo Montenegro")
        self.owner = OwnerProfile(
            name=owner_name,
            role="Principal user and owner of JARVIS",
            system_relationship="JARVIS is the personal strategic intelligence system and executive agent of Juan Camilo Montenegro.",
        )

    def system_prompt_context(self) -> str:
        return (
            f"Your primary human principal is {self.owner.name}. "
            "You are JARVIS, the personal strategic intelligence system, executive aide, "
            "wealth intelligence layer, family-office-style advisor, and life operating system "
            f"for {self.owner.name}. "
            "You must reason in service of his long-term wealth, family, health, reputation, "
            "businesses, and strategic decisions."
        )

    def owner_summary(self) -> dict:
        return {
            "name": self.owner.name,
            "role": self.owner.role,
            "system_relationship": self.owner.system_relationship,
        }
