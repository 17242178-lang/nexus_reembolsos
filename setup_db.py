from app.database import Base, engine, SessionLocal
from app.models import Department, User, UserRole
from app.security import get_password_hash

def seed_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # 1. Departamentos
    comercial = Department(name="Comercial")
    ti = Department(name="Tecnologia")
    financeiro_dept = Department(name="Financeiro")
    db.add_all([comercial, ti, financeiro_dept])
    db.commit()
    
    # 2. Usuários de teste (Cenários 01 a 08)
    ana = User(name="Ana", email="ana@nexus.com", password_hash=get_password_hash("senha123"), department_id=comercial.id, role=UserRole.COLABORADOR)
    bruno = User(name="Bruno", email="bruno@nexus.com", password_hash=get_password_hash("senha123"), department_id=ti.id, role=UserRole.COLABORADOR)
    patricia = User(name="Patrícia", email="patricia@nexus.com", password_hash=get_password_hash("senha123"), department_id=comercial.id, role=UserRole.GESTOR)
    carlos = User(name="Carlos", email="carlos@nexus.com", password_hash=get_password_hash("senha123"), department_id=ti.id, role=UserRole.GESTOR)
    fernanda = User(name="Fernanda", email="fernanda@nexus.com", password_hash=get_password_hash("senha123"), department_id=financeiro_dept.id, role=UserRole.FINANCEIRO)
    
    db.add_all([ana, bruno, patricia, carlos, fernanda])
    db.commit()
    db.close()
    print("Banco de dados inicializado com sucesso!")

if __name__ == "__main__":
    seed_database()