# Plataforma de Gestão de Reembolsos Corporativos — NexusCorp

API REST desenvolvida em Python para centralizar, auditar e automatizar o processo de solicitação e aprovação de reembolsos corporativos da empresa NexusCorp, com controle rigoroso de acesso e rastreabilidade total.

---

## 1. Descrição da Solução

A solução resolve os problemas de falta de controle e vazamento de informações da NexusCorp através de:
- **Autenticação Stateless via Token JWT:** Identificação única de cada colaborador.
- **Controle de Acesso Baseado em Papéis (RBAC):** Restrição de funcionalidades entre Colaborador, Gestor e Financeiro.
- **Isolamento de Dados por Departamento:** Gestores só visualizam despesas do seu próprio departamento.
- **Ciclo de Vida de Aprovação Sequencial:** Bloqueio de transições inválidas e modificações após envio.
- **Trilha de Auditoria Imutável:** Registro completo no banco de dados de todas as aprovações, recusas e pagamentos com data, hora e responsável.

---

## 2. Modelo de Dados (Entidades e Relacionamentos)

O banco de dados relacional (SQLite via SQLAlchemy) é composto por 4 tabelas conectadas:

1. **`departments`**: Armazena os departamentos (`id`, `name`).
2. **`users`**: Registra os colaboradores (`id`, `name`, `email`, `password_hash`, `department_id`, `role`).
3. **`reimbursement_requests`**: Armazena as despesas (`id`, `user_id`, `department_id`, `category`, `amount`, `date`, `justification`, `receipt_ref`, `status`, `created_at`).
4. **`analysis_history`**: Registra o histórico das análises (`id`, `request_id`, `user_id`, `stage`, `decision`, `timestamp`, `observation`).

### Relacionamentos:
- 1 **Departamento** possui N **Usuários** e N **Solicitações**.
- 1 **Usuário** possui N **Solicitações** e N **Históricos de Análise**.
- 1 **Solicitação** possui N **Históricos de Análise**.

---

## 3. Matriz de Permissões (RBAC)

| Operação / Endpoint | Colaborador | Gestor | Financeiro | Regras de Negócio Aplicadas |
| :--- | :---: | :---: | :---: | :--- |
| **Autenticação (`POST /auth/login`)** | Permitido | Permitido | Permitido | RN01, RN13, RN14 |
| **Criar Solicitação (`POST /reimbursements`)** | Própria | Própria | Própria | RN04, RN05, RN06 |
| **Consultar Lista (`GET /reimbursements`)** | Apenas Próprias | Do Departamento | Todas | RN02, RN03 |
| **Editar Rascunho (`PUT /reimbursements/{id}`)** | Próprio | Próprio | Próprio | RN07 (Apenas status RASCUNHO) |
| **Excluir Rascunho (`DELETE /reimbursements/{id}`)** | Próprio | Próprio | Próprio | RN07 (Apenas status RASCUNHO) |
| **Enviar para Aprovação (`POST .../submit`)** | Próprio | Próprio | Próprio | RN07 |
| **Aprovação do Gestor (`POST .../approve-manager`)** | Negado | Do Depto* | Negado | RN03, RN08, RN09 (*Bloqueia autoria) |
| **Aprovação Financeira (`POST .../approve-finance`)** | Negado | Negado | Todas* | RN08, RN09 (*Bloqueia autoria) |
| **Registrar Pagamento (`POST .../pay`)** | Negado | Negado | Todas | RN10 |
| **Recusar Solicitação (`POST .../reject`)** | Negado | Do Depto | Todas | RN11 (Exige justificativa) |
| **Ver Histórico (`GET .../history`)** | Própria | Do Depto | Todas | RN12 (Rastreabilidade) |

---

## 4. Identificação das Regras de Negócio Implementadas

- **RN01 — Identificação:** Todas as rotas restritas exigem um token JWT `Bearer` válido.
- **RN02 — Confidencialidade:** O colaborador só visualiza requisições criadas pelo seu ID.
- **RN03 — Responsabilidade Departamental:** O gestor só acessa/aprova solicitações do seu `department_id`.
- **RN04 — Integridade dos Valores:** Validação Pydantic `amount > 0`.
- **RN05 — Duplicidade:** O sistema impede duplicidade de `receipt_ref` para o mesmo usuário.
- **RN06 — Período da Despesa:** Bloqueio de cadastros com datas no futuro (`date > date.today()`).
- **RN07 — Alteração:** Edições só são aceitas enquanto `status == RASCUNHO`.
- **RN08 — Aprovação:** A aprovação financeira só ocorre após a aprovação do gestor (`AGUARDANDO_FINANCEIRO`).
- **RN09 — Segregação de Responsabilidades:** O criador da solicitação é impedido de aprová-la (`user_id != analyst_id`).
- **RN10 — Pagamento:** Registro de pagamento restrito a solicitações com status `APROVADA`.
- **RN11 — Recusa:** Obrigatoriedade do campo de observação em recusas.
- **RN12 — Rastreabilidade:** Registro automático de quem, quando e o resultado de cada etapa no `analysis_history`.
- **RN13 — Proteção de Credenciais:** Senhas armazenadas com hash `pbkdf2_sha256` e omitidas das respostas da API.
- **RN14 — Controle de Sessão:** Expiração de tokens JWT configurada e validada.
- **RN15 — Proteção dos Perfis:** Impossibilidade de alterar `role` ou `department_id` via atualização comum.

---

## 5. Contratos das Principais Operações da API

### Autenticação (`POST /auth/login`)
- **Entrada (JSON):**
  ```json
  {
    "email": "bruno@nexus.com",
    "password": "senha123"
  }