# Tribultz - Inteligência Fiscal Determinística 🚀

SaaS de conformidade para a reforma tributária brasileira (LC 214/227).

### 🛠️ Stack Tecnológica
- **Backend:** FastAPI (Python 3.12) + Pydantic V2 (Fail-fast)
- **Processamento:** Celery + Redis (Async Processing)
- **IA:** CrewAI com Memória Persistente & Multi-tenant isolation
- **Banco de Dados:** PostgreSQL (Audit-ready)
- **Storage:** S3-Compatible (Magalu Cloud Native)

### 🧠 Diferenciais do Produto
- **Memória Fiscal:** Recuperação automática de precedentes fiscais, acelerando a validação de lotes massivos.
- **Isolamento de Dados:** Arquitetura desenhada para multi-tenancy real, garantindo conformidade estrita com a LGPD.
- **Soberania Digital:** Infraestrutura otimizada para nuvem brasileira, eliminando exposição cambial e latência internacional.

### 🚀 Setup
1. `cp .env.example .env` (Configure as chaves obrigatórias)
2. `docker-compose up --build`
3. Documentação: `http://localhost:8000/docs`

---
