import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database import Base

class UserRole(str, enum.Enum):
    COLABORADOR = "COLABORADOR"
    GESTOR = "GESTOR"
    FINANCEIRO = "FINANCEIRO"

class RequestStatus(str, enum.Enum):
    RASCUNHO = "RASCUNHO"
    AGUARDANDO_GESTOR = "AGUARDANDO_GESTOR"
    AGUARDANDO_FINANCEIRO = "AGUARDANDO_FINANCEIRO"
    APROVADA = "APROVADA"
    PAGA = "PAGA"
    RECUSADA = "RECUSADA"

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)

    users = relationship("User", back_populates="department")
    requests = relationship("ReimbursementRequest", back_populates="department")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.COLABORADOR)

    department = relationship("Department", back_populates="users")
    requests = relationship("ReimbursementRequest", back_populates="user")
    analyses = relationship("AnalysisHistory", back_populates="analyst")

class ReimbursementRequest(Base):
    __tablename__ = "reimbursement_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    category = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    justification = Column(String(255), nullable=False)
    receipt_ref = Column(String(100), nullable=False)
    status = Column(SQLEnum(RequestStatus), nullable=False, default=RequestStatus.RASCUNHO)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="requests")
    department = relationship("Department", back_populates="requests")
    history = relationship("AnalysisHistory", back_populates="request", cascade="all, delete-orphan")

class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("reimbursement_requests.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stage = Column(String(50), nullable=False)
    decision = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    observation = Column(String(255), nullable=True)

    request = relationship("ReimbursementRequest", back_populates="history")
    analyst = relationship("User", back_populates="analyses")