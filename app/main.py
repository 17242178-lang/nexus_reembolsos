from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import User, ReimbursementRequest, AnalysisHistory, UserRole, RequestStatus
from app.schemas import (
    LoginRequest, Token, ReimbursementCreate, ReimbursementUpdate,
    ReimbursementResponse, AnalysisHistoryResponse, AnalysisDecision, RejectDecision
)
from app.security import verify_password, create_access_token, get_current_user
import app.crud as crud

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Plataforma de Gestão de Reembolsos Corporativos",
    version="1.0.0",
    description="API REST para controle rigoroso de reembolsos corporativos NexusCorp."
)

# --- Autenticação (RN01, RN13, RN14) ---
@app.post("/auth/login", response_model=Token, tags=["Autenticação"])
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    # RN13: Proteção de credenciais (mensagem genérica sem revelar o campo incorreto)
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos."
        )
    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}

# --- Colaborador: Operações de Reembolso ---
@app.post("/reimbursements", response_model=ReimbursementResponse, tags=["Reembolsos"])
def create_request(data: ReimbursementCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.create_reimbursement(db, current_user, data)

@app.get("/reimbursements", response_model=List[ReimbursementResponse], tags=["Reembolsos"])
def list_requests(
    department_id: Optional[int] = None,
    status_filter: Optional[RequestStatus] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ReimbursementRequest)
    
    # RN02 & RN03: Filtragem restrita por Perfil
    if current_user.role == UserRole.COLABORADOR:
        query = query.filter(ReimbursementRequest.user_id == current_user.id)
    elif current_user.role == UserRole.GESTOR:
        query = query.filter(ReimbursementRequest.department_id == current_user.department_id)
    elif current_user.role == UserRole.FINANCEIRO:
        if department_id:
            query = query.filter(ReimbursementRequest.department_id == department_id)
    
    if status_filter:
        query = query.filter(ReimbursementRequest.status == status_filter)
    if category:
        query = query.filter(ReimbursementRequest.category == category)
        
    return query.all()

@app.get("/reimbursements/{req_id}", response_model=ReimbursementResponse, tags=["Reembolsos"])
def get_request(req_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    # RN02 & RN03
    if current_user.role == UserRole.COLABORADOR and req.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="RN02: Acesso não autorizado.")
    if current_user.role == UserRole.GESTOR and req.department_id != current_user.department_id:
        raise HTTPException(status_code=403, detail="RN03: Acesso não autorizado ao departamento.")
        
    return req

@app.put("/reimbursements/{req_id}", response_model=ReimbursementResponse, tags=["Reembolsos"])
def update_request(req_id: int, data: ReimbursementUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.update_reimbursement(db, req_id, current_user, data)

@app.delete("/reimbursements/{req_id}", tags=["Reembolsos"])
def delete_request(req_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    crud.delete_reimbursement(db, req_id, current_user)
    return {"message": "Solicitação excluída com sucesso."}

@app.post("/reimbursements/{req_id}/submit", response_model=ReimbursementResponse, tags=["Fluxo de Aprovação"])
def submit_request(req_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.submit_reimbursement(db, req_id, current_user)

# --- Gestor & Financeiro: Aprovações ---
@app.post("/reimbursements/{req_id}/approve-manager", response_model=ReimbursementResponse, tags=["Fluxo de Aprovação"])
def approve_by_manager(req_id: int, decision: AnalysisDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.GESTOR:
        raise HTTPException(status_code=403, detail="Apenas gestores podem realizar esta operação.")
    return crud.manager_approve(db, req_id, current_user, decision.observation)

@app.post("/reimbursements/{req_id}/approve-finance", response_model=ReimbursementResponse, tags=["Fluxo de Aprovação"])
def approve_by_finance(req_id: int, decision: AnalysisDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.FINANCEIRO:
        raise HTTPException(status_code=403, detail="Apenas membros do financeiro podem realizar esta operação.")
    return crud.finance_approve(db, req_id, current_user, decision.observation)

@app.post("/reimbursements/{req_id}/pay", response_model=ReimbursementResponse, tags=["Fluxo de Aprovação"])
def pay_request(req_id: int, decision: AnalysisDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.FINANCEIRO:
        raise HTTPException(status_code=403, detail="Apenas membros do financeiro podem realizar esta operação.")
    return crud.pay_reimbursement(db, req_id, current_user, decision.observation)

@app.post("/reimbursements/{req_id}/reject", response_model=ReimbursementResponse, tags=["Fluxo de Aprovação"])
def reject_request(req_id: int, decision: RejectDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.GESTOR, UserRole.FINANCEIRO]:
        raise HTTPException(status_code=403, detail="Sem permissão para recusar solicitações.")
    return crud.reject_reimbursement(db, req_id, current_user, decision.observation)

# --- Histórico e Rastreabilidade (RN12) ---
@app.get("/reimbursements/{req_id}/history", response_model=List[AnalysisHistoryResponse], tags=["Rastreabilidade"])
def get_request_history(req_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    if current_user.role == UserRole.COLABORADOR and req.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado ao histórico.")
    if current_user.role == UserRole.GESTOR and req.department_id != current_user.department_id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado ao departamento.")
        
    return req.history