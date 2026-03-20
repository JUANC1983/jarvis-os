from fastapi import APIRouter, Request
from interfaces.whatsapp_real_interface import WhatsAppRealInterface
from core.real_agent_council import RealAgentCouncil
from core.owner_digital_twin import OwnerDigitalTwin

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

whatsapp = WhatsAppRealInterface()
council = RealAgentCouncil()
identity = OwnerDigitalTwin()


@router.post("/webhook")
async def whatsapp_webhook(request: Request):

    form = await request.form()

    incoming_msg = form.get("Body")
    phone = form.get("From")

    council_response = council.deliberate(
        topic=incoming_msg,
        domain="general",
        owner_name=identity.owner_summary()["name"]
    )

    consensus = council_response.get("consensus","")

    reply = f"JARVIS:\n\n{consensus}"

    return whatsapp.webhook_response(reply)
