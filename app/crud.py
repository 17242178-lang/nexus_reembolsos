from datetime import date, datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models import User, ReimbursementRequest, AnalysisHistory, RequestStatus, UserRole
from app.schemas import ReimbursementCreate, ReimbursementUpdate

def create_reimbursement(db: Session, user: User, data: ReimbursementCreate):
    # RN04: Integridade dos valores (Validado pelo Pydantic gt=0)
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="RN04: O valor deve ser maior que zero.")
    
    # RN06: Período da despesa
    if data.date > date.today():
        raise HTTPException(status_code=400, detail="RN06: Despesas com datas futuras não podem ser registradas.")
    
    # RN05: Duplicidade por comprovante
    duplicate = db.query(ReimbursementRequest).filter(
        ReimbursementRequest.user_id == user.id,
        ReimbursementRequest.receipt_ref == data.receipt_ref
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="RN05: Comprovante já cadastrado para este colaborador.")
    
    req = ReimbursementRequest(
        user_id=user.id,
        department_id=user.department_id,
        category=data.category,
        amount=data.amount,
        date=data.date,
        justification=data.justification,
        receipt_ref=data.receipt_ref,
        status=RequestStatus.RASCUNHO
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req

def update_reimbursement(db: Session, req_id: int, user: User, data: ReimbursementUpdate):
    req = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    # RN02: Confidencialidade
    if req.user_id != user.id:
        raise HTTPException(status_code=403, detail="RN02: Acesso não autorizado a esta solicitação.")
    
    # RN07: Alteração restrita a Rascunho
    if req.status != RequestStatus.RASCUNHO:
        raise HTTPException(status_code=400, detail="RN07: A solicitação só pode ser alterada enquanto estiver em rascunho.")
    
    if data.date and data.date > date.today():
        raise HTTPException(status_code=400, detail="RN06: Despesas com datas futuras não são permitidas.")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(req, key, value)
    
    db.commit()
    db.refresh(req)
    return req

def delete_reimbursement(db: Session, req_id: int, user: User):
    req = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    if req.user_id != user.id:
        raise HTTPException(status_code=403, detail="RN02: Acesso negado.")
    
    if req.status != RequestStatus.RASCUNHO:
        raise HTTPException(status_code=400, detail="Apenas solicitações em rascunho podem ser excluídas.")
    
    db.delete(req)
    db.commit()

def submit_reimbursement(db: Session, req_id: int, user: User):
    req = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == req_id).first()
    if not req or req.user_id != user.id:
        raise HTTPException(status_code=403, detail="RN02: Solicitação indisponível ou acesso negado.")
    
    if req.status != RequestStatus.RASCUNHO:
        raise HTTPException(status_code=400, detail="Solicitação já foi enviada ou finalizada.")
    
    req.status = RequestStatus.AGUARDANDO_GESTOR
    db.commit()
    db.refresh(req)
    return req

def manager_approve(db: Session, req_id: int, manager: User, obs: str = None):
    req = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    # RN09: Segregação de responsabilidades
    if req.user_id == manager.id:
        raise HTTPException(status_code=403, detail="RN09: Um usuário não pode aprovar a própria solicitação.")
    
    # RN03: Responsabilidade departamental
    if req.department_id != manager.department_id:
        raise HTTPException(status_code=403, detail="RN03: Gestor não pertence ao departamento da solicitação.")
    
    # Fluxo correto
    if req.status != RequestStatus.AGUARDANDO_GESTOR:
        raise HTTPException(status_code=400, detail="Solicitação não está aguardando aprovação do gestor.")
    
    req.status = RequestStatus.AGUARDANDO_FINANCEIRO
    
    # RN12: Rastreabilidade
    history = AnalysisHistory(
        request_id=req.id,
        user_id=manager.id,
        stage="ANALISE_GESTOR",
        decision="APROVADO",
        observation=obs
    )
    db.add(history)
    db.commit()
    db.refresh(req)
    return req

def finance_approve(db: Session, req_id: int, finance_user: User, obs: str = None):
    req = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    if req.user_id == finance_user.id:
        raise HTTPException(status_code=403, detail="RN09: Usuário não pode aprovar a própria solicitação.")
    
    # RN08: Aprovação sequencial obriga passar pelo gestor primeiro
    if req.status != RequestStatus.AGUARDANDO_FINANCEIRO:
        raise HTTPException(status_code=400, detail="RN08: A solicitação precisa de aprovação do gestor antes do financeiro.")
    
    req.status = RequestStatus.APROVADA
    
    history = AnalysisHistory(
        request_id=req.id,
        user_id=finance_user.id,
        stage="ANALISE_FINANCEIRO",
        decision="APROVADO",
        observation=obs
    )
    db.add(history)
    db.commit()
    db.refresh(req)
    return req

def pay_reimbursement(db: Session, req_id: int, finance_user: User, obs: str = None):
    req = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    # RN10: Pagamento após aprovação financeira
    if req.status != RequestStatus.APROVADA:
        raise HTTPException(status_code=400, detail="RN10: Solicitação deve estar APROVADA para registrar pagamento.")
    
    req.status = RequestStatus.PAGA
    
    history = AnalysisHistory(
        request_id=req.id,
        user_id=finance_user.id,
        stage="PAGAMENTO",
        decision="PAGO",
        observation=obs
    )
    db.add(history)
    db.commit()
    db.refresh(req)
    return req

def reject_reimbursement(db: Session, req_id: int, user: User, obs: str):
    req = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    
    if user.role == UserRole.GESTOR and req.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="RN03: Gestor não pertence ao departamento da solicitação.")
    
    if req.user_id == user.id:
        raise HTTPException(status_code=403, detail="RN09: Usuário não pode recusar a própria solicitação.")
    
    if req.status in [RequestStatus.PAGA, RequestStatus.RECUSADA]:
        raise HTTPException(status_code=400, detail="Processo já encerrado.")
    
    # RN11: Recusa exige justificativa
    if not obs or len(obs.strip()) == 0:
        raise HTTPException(status_code=400, detail="RN11: Toda solicitação recusada deve possuir uma justificativa.")
    
    req.status = RequestStatus.RECUSADA
    
    history = AnalysisHistory(
        request_id=req.id,
        user_id=user.id,
        stage=f"RECUSA_{user.role.value}",
        decision="RECUSADO",
        observation=obs
    )
    db.add(history)
    db.commit()
    db.refresh(req)
    return req