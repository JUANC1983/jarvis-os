from fastapi import APIRouter
from core.opportunity_hunter import OpportunityHunter

router = APIRouter(prefix="/opportunities")

hunter = OpportunityHunter()

@router.post("/linkedin")

def linkedin(payload:dict):

    return hunter.search_linkedin(payload["keyword"])


@router.post("/startups")

def startups(payload:dict):

    return hunter.search_startups(payload["keyword"])


@router.post("/internet")

def internet(payload:dict):

    return hunter.search_internet(payload["keyword"])
