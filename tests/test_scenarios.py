import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app
from setup_db import seed_database

client = TestClient(app)

@pytest.fixture(autouse=True)
def prepare_db():
    seed_database()

def get_token(email, password="senha123"):
    res = client.post("/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]

# Cenário 01 — Acesso indevido
def test_scenario_01_unauthorized_access():
    token_bruno = get_token("bruno@nexus.com") # TI
    token_ana = get_token("ana@nexus.com")     # Comercial
    
    # Bruno cria uma solicitação
    headers_bruno = {"Authorization": f"Bearer {token_bruno}"}
    req_res = client.post("/reimbursements", headers=headers_bruno, json={
        "category": "Transporte", "amount": 100.0, "date": str(date.today()),
        "justification": "Táxi reunião", "receipt_ref": "REC-001"
    })
    req_id = req_res.json()["id"]
    
    # Ana tenta consultar o ID do Bruno
    headers_ana = {"Authorization": f"Bearer {token_ana}"}
    res = client.get(f"/reimbursements/{req_id}", headers=headers_ana)
    assert res.status_code == 403
    assert "RN02" in res.json()["detail"]

# Cenário 02 — Gestor de outro departamento
def test_scenario_02_wrong_department_manager():
    token_bruno = get_token("bruno@nexus.com") # TI
    token_patricia = get_token("patricia@nexus.com") # Gestora Comercial
    
    headers_bruno = {"Authorization": f"Bearer {token_bruno}"}
    req_res = client.post("/reimbursements", headers=headers_bruno, json={
        "category": "Alimentação", "amount": 50.0, "date": str(date.today()),
        "justification": "Almoço", "receipt_ref": "REC-002"
    })
    req_id = req_res.json()["id"]
    client.post(f"/reimbursements/{req_id}/submit", headers=headers_bruno)
    
    # Patrícia tenta aprovar despesa da TI
    headers_patricia = {"Authorization": f"Bearer {token_patricia}"}
    res = client.post(f"/reimbursements/{req_id}/approve-manager", headers=headers_patricia, json={"observation": "OK"})
    assert res.status_code == 403
    assert "RN03" in res.json()["detail"]

# Cenário 03 — Credenciais incorretas
def test_scenario_03_wrong_credentials():
    res = client.post("/auth/login", json={"email": "ana@nexus.com", "password": "senha_errada"})
    assert res.status_code == 401
    assert "E-mail ou senha incorretos" in res.json()["detail"]

# Cenário 04 — Tentativa de alteração de permissões
def test_scenario_04_privilege_escalation():
    # O endpoint PUT /reimbursements/{id} não expõe role ou department_id no schema ReimbursementUpdate
    token_ana = get_token("ana@nexus.com")
    headers = {"Authorization": f"Bearer {token_ana}"}
    res = client.post("/reimbursements", headers=headers, json={
        "category": "Alimentação", "amount": 40.0, "date": str(date.today()),
        "justification": "Lanche", "receipt_ref": "REC-004", "role": "FINANCEIRO"
    })
    # O Pydantic ignora campos não mapeados
    assert res.status_code == 200
    user_res = client.get(f"/reimbursements/{res.json()['id']}", headers=headers)
    # Garante que o status permanece normal
    assert user_res.json()["status"] == "RASCUNHO"

# Cenário 05 — Aprovação fora da sequência
def test_scenario_05_out_of_sequence_approval():
    token_bruno = get_token("bruno@nexus.com")
    token_fernanda = get_token("fernanda@nexus.com") # Financeiro
    
    headers_bruno = {"Authorization": f"Bearer {token_bruno}"}
    req_res = client.post("/reimbursements", headers=headers_bruno, json={
        "category": "Hospedagem", "amount": 300.0, "date": str(date.today()),
        "justification": "Hotel", "receipt_ref": "REC-005"
    })
    req_id = req_res.json()["id"]
    client.post(f"/reimbursements/{req_id}/submit", headers=headers_bruno)
    
    # Financeiro tenta aprovar direto sem o gestor
    headers_fernanda = {"Authorization": f"Bearer {token_fernanda}"}
    res = client.post(f"/reimbursements/{req_id}/approve-finance", headers=headers_fernanda, json={"observation": "OK"})
    assert res.status_code == 400
    assert "RN08" in res.json()["detail"]

# Cenário 06 — Manipulação de solicitação enviada
def test_scenario_06_tamper_submitted_request():
    token_bruno = get_token("bruno@nexus.com")
    headers = {"Authorization": f"Bearer {token_bruno}"}
    req_res = client.post("/reimbursements", headers=headers, json={
        "category": "Transporte", "amount": 180.0, "date": str(date.today()),
        "justification": "Táxi", "receipt_ref": "REC-006"
    })
    req_id = req_res.json()["id"]
    client.post(f"/reimbursements/{req_id}/submit", headers=headers)
    
    # Tenta alterar de 180 para 1800
    res = client.put(f"/reimbursements/{req_id}", headers=headers, json={"amount": 1800.0})
    assert res.status_code == 400
    assert "RN07" in res.json()["detail"]

# Cenário 07 — Consulta com filtros por departamento
def test_scenario_07_department_filtered_query():
    token_carlos = get_token("carlos@nexus.com") # Gestor TI
    headers = {"Authorization": f"Bearer {token_carlos}"}
    res = client.get("/reimbursements", headers=headers)
    assert res.status_code == 200
    # Todos os itens retornados devem obrigatoriamente pertencer ao departamento do gestor
    for req in res.json():
        assert req["department_id"] == 2

# Cenário 08 — Demonstração do Fluxo Completo de Aprovação e Rastreabilidade
def test_scenario_08_full_approval_workflow_and_history():
    token_bruno = get_token("bruno@nexus.com")
    token_carlos = get_token("carlos@nexus.com") # Gestor TI
    token_fernanda = get_token("fernanda@nexus.com") # Financeiro
    
    h_bruno = {"Authorization": f"Bearer {token_bruno}"}
    h_carlos = {"Authorization": f"Bearer {token_carlos}"}
    h_fernanda = {"Authorization": f"Bearer {token_fernanda}"}
    
    # 1. Colaborador cria e envia
    r = client.post("/reimbursements", headers=h_bruno, json={
        "category": "Alimentação", "amount": 120.0, "date": str(date.today()),
        "justification": "Jantar de negócios", "receipt_ref": "REC-FULL-FLOW"
    }).json()
    req_id = r["id"]
    client.post(f"/reimbursements/{req_id}/submit", headers=h_bruno)
    
    # 2. Gestor Aprova
    client.post(f"/reimbursements/{req_id}/approve-manager", headers=h_carlos, json={"observation": "Aprovado pelo gestor"})
    
    # 3. Financeiro Aprova
    client.post(f"/reimbursements/{req_id}/approve-finance", headers=h_fernanda, json={"observation": "Aprovado no financeiro"})
    
    # 4. Financeiro Paga
    pay_res = client.post(f"/reimbursements/{req_id}/pay", headers=h_fernanda, json={"observation": "Pago via transferência"})
    assert pay_res.json()["status"] == "PAGA"
    
    # 5. Validação da Rastreabilidade (Histórico)
    hist_res = client.get(f"/reimbursements/{req_id}/history", headers=h_bruno)
    history = hist_res.json()
    assert len(history) == 3
    assert history[0]["stage"] == "ANALISE_GESTOR"
    assert history[1]["stage"] == "ANALISE_FINANCEIRO"
    assert history[2]["stage"] == "PAGAMENTO"