from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TraceMetadata(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "jarvis"
    version: str = "1.0"
    extra: Dict[str, Any] = Field(default_factory=dict)


class MediaRequest(BaseModel):
    file_path: str
    task: str = "analyze"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    domain: str = "general"
    context: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    primary_agent: str
    consulted_agents: List[str]
    risk_escalated: bool
    memory_items_created: int
    trace: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReportRequest(BaseModel):
    title: str
    content: str
    filename: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    decision: str
    outcome: str
    score: int = Field(..., ge=0, le=10)
    notes: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PresentationRequest(BaseModel):
    title: str
    objective: str
    audience: str
    key_points: List[str]
    filename: str = "presentation"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentPersonalityRequest(BaseModel):
    agent_name: str


class AgentKnowledgeRequest(BaseModel):
    domain: str


class OpportunityRadarRequest(BaseModel):
    topic: str
    context: str = ""
    horizon: str = "short"
    risk_tolerance: str = "balanced"


class AlertCreateRequest(BaseModel):
    symbol: str
    condition: str
    threshold: float
    note: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NarrativeRequest(BaseModel):
    topic: str
    context: str = ""


class RegimeRequest(BaseModel):
    topic: str
    context: str = ""


class MemoryStoreRequest(BaseModel):
    category: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemorySearchRequest(BaseModel):
    keyword: str
    top_k: int = 5


class WhatsAppMessageRequest(BaseModel):
    phone: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VoiceTranscribeRequest(BaseModel):
    audio_path: str


class VoiceSynthesizeRequest(BaseModel):
    text: str
    provider: str = "elevenlabs"
    style: str = "natural"


class EmailDraftRequest(BaseModel):
    sender: str
    subject: str
    body: str
    tone: str = "professional"


class CalendarPlanRequest(BaseModel):
    objective: str
    duration_minutes: int
    participants: List[str]


class OwnerProfile(BaseModel):
    name: str
    role: str
    mission: str
    priorities: List[str]
    location: Optional[str] = "Colombia"
    timezone: Optional[str] = "America/Bogota"


class VectorMemoryStoreRequest(BaseModel):
    text: str = Field(..., min_length=1)
    category: str = "general"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VectorMemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = 5


class OrchestratorRequest(BaseModel):
    mission: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentExecutionResult(BaseModel):
    agent_name: str
    display_name: str = ""
    category: str = "general"
    response: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GuardrailRequest(BaseModel):
    text: str = Field(..., min_length=1)


class MedicalTriageRequest(BaseModel):
    symptoms: str = Field(..., min_length=1)
    age: Optional[int] = None
    context: str = ""


class LabInterpretationRequest(BaseModel):
    lab_text: str = Field(..., min_length=1)


class TreatmentSupportRequest(BaseModel):
    context: str = Field(..., min_length=1)


class FitnessMicrocycleRequest(BaseModel):
    goal: str = "strength_golf"
    days: int = 7
    equipment: List[str] = Field(default_factory=lambda: ["dumbbells", "bands", "kettlebell"])
    golf_swings_per_day: int = 50


class FitnessNutritionRequest(BaseModel):
    weight_kg: float = 53.0
    goal: str = "lean_mass"


class FitnessRecoveryRequest(BaseModel):
    context: str = ""


class BrowserTaskRequest(BaseModel):
    url: str
    task: str = "open"
    selectors: List[str] = Field(default_factory=list)
    text: str = ""
    dry_run: bool = True
    allowed_domain: str = ""


class DesktopTaskRequest(BaseModel):
    action: str
    x: Optional[int] = None
    y: Optional[int] = None
    text: str = ""
    image_path: str = ""
    dry_run: bool = True


class AutomationPlanRequest(BaseModel):
    mission: str
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    dry_run: bool = True
