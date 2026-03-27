# Readiness para Magalu Cloud (DevSecOps)

## Abstração de Ambiente: Env Vars e 12-Factor App

Dado que migraremos para a Magalu Cloud em breve, a lógica core não pode ter referências engessadas (hardcoded) para volumes locais (`C:\`, `/app/data/`) ou secrets no código.

## Estratégias Inseridas no Código Hoje

1. **Gestão de Segredos:**
   - Utilizaremos a biblioteca `pydantic-settings` (Python) para injetar todo o roteamento de serviços e senhas via variáveis de ambiente (`.env` local, ou Engine de Secrets na cloud).
   - Nenhuma API Key do LLM, banco de dados, ou chave criptográfica reside em código-fonte.
   - Padrão: Substituir chaves de acesso estáticas por injetores dinâmicos ou integração com cofres de segredo (Vault / Magalu Cloud Secrets).

2. **Volume Storage Agnosticismo:**
   - Os caminhos de persistência de arquivo e outputs que não vão ao banco devem utilizar `os.getenv("STORAGE_PATH", "/tmp")`. 
   - Ao transpor para a Magalu Cloud, basta plugar um `Volume` distribuído (como NFS ou S3 Block Storage API) e passar o caminho para o contêiner pelo `docker-compose.yml` ou Manifesto Kubernetes / Helm. 

3. **Injecão de Dependência via Interfaces:**
   - O código se comunicará com o "Repositório de Arquivos" e não diretamente com o file system (`os.open`). Se precisarmos trocar FileSystem local por Object Storage de forma mandatória, só implementaremos o adaptador S3-compatible, com o núcleo de regras fiscais intocado.
