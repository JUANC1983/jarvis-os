from fastapi import APIRouter
from core.medical_supreme_engine import MedicalSupremeEngine
from core.fitness_performance_engine import FitnessPerformanceEngine

router = APIRouter(prefix="/health-performance")

medical = MedicalSupremeEngine()
fitness = FitnessPerformanceEngine()

@router.post("/medical")
def medical_route(payload:dict):

    return medical.symptom_triage(payload.get("symptoms",""))

@router.get("/fitness")

def fitness_route():

    return fitness.microcycle()

