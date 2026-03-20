from core.models import OwnerProfile


class OwnerDigitalTwin:
    """
    Digital twin of the owner.
    This represents the strategic identity that JARVIS serves.
    """

    def __init__(self):

        self.owner = OwnerProfile(
            name="Juan Camilo Montenegro",
            role="Founder / Principal Operator",

            mission=(
                "Build global wealth, protect family, optimize health, "
                "and operate at the highest strategic level with the assistance of JARVIS."
            ),

            priorities=[
                "capital growth",
                "strategic investments",
                "family protection",
                "health optimization",
                "time leverage",
                "global opportunity detection",
                "risk management",
                "tax optimization",
                "network expansion",
                "legacy building"
            ],

            location="Colombia"
        )

    def get_profile(self):
        return {
            "name": self.owner.name,
            "role": self.owner.role,
            "mission": self.owner.mission,
            "priorities": self.owner.priorities,
            "location": self.owner.location
        }

    def strategic_context(self):
        """
        Context used by JARVIS agents when making decisions.
        """

        return {
            "owner_name": self.owner.name,
            "primary_objective": "maximize long-term wealth and strategic positioning",
            "risk_profile": "calculated strategic risk",
            "investment_focus": [
                "global macro opportunities",
                "equities",
                "commodities",
                "real assets",
                "private opportunities"
            ],
            "life_priorities": self.owner.priorities
        }