from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import date, datetime
from typing import Optional, List
from app.models import UserRole, RequestStatus

# Autenticação
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[UserRole] = None
    department_id: Optional[int] = None

# Usuários
class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    department_id: int
    role: UserRole

    model_config = ConfigDict(from_attributes=True)

# Solicitação de Reembolso
class ReimbursementCreate(BaseModel):
    category: str
    amount: float = Field(..., gt=0, description="O valor deve ser maior que zero")
    date: date
    justification: str
    receipt_ref: str

class ReimbursementUpdate(BaseModel):
    category: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    date: Optional[date] = None
    justification: Optional[str] = None
    receipt_ref: Optional[str] = None

class AnalysisDecision(BaseModel):
    observation: Optional[str] = None

class RejectDecision(BaseModel):
    observation: str = Field(..., min_length=3, description="Justificativa obrigatória para recusa")

class AnalysisHistoryResponse(BaseModel):
    id: int
    request_id: int
    user_id: int
    stage: str
    decision: str
    timestamp: datetime
    observation: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ReimbursementResponse(BaseModel):
    id: int
    user_id: int
    department_id: int
    category: str
    amount: float
    date: date
    justification: str
    receipt_ref: str
    status: RequestStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)