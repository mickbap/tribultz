# Contexto do projeto — conhecimento durável

Conhecimento acumulado sobre o Tribultz que **vale para qualquer máquina e qualquer agente**: vocabulário fiscal, base legal, regras do time de contabilidade, referências de APIs externas, convenções de trabalho e decisões de produto.

Estes arquivos nasceram como memória local do Claude em `~/.claude/projects/<caminho>/memory/`. Foram promovidos para cá em 2026-07-15 porque memória local **não viaja**: ela vive fora do repositório, o diretório deriva do caminho do projeto, e nada disso sai no `git clone`. Ao migrar do Windows para o Mac, todo esse conhecimento seria perdido em silêncio — vocabulário fiscal errado, bugs conhecidos reintroduzidos, decisões de produto esquecidas.

## Regra desta pasta

**Nunca coloque credencial aqui.** Nem API key, token, senha, chave privada ou connection string com senha. Esta pasta é versionada — e **o histórico do git é permanente**: um segredo commitado continua acessível a quem tiver o repositório, mesmo depois de deletado do HEAD. Deletar não desfaz o vazamento.

Onde as credenciais vivem, como validá-las e como configurar máquina nova: `docs/infra/secrets_inventory.md`. A fonte de verdade é `/opt/tribultz/.env` na VM.

## Relação com a memória local do agente

Estes arquivos são a **fonte de verdade**. A memória local de cada máquina é cache — útil para o que é efêmero ou específico daquele computador, mas nunca a referência.

Se um agente aprender algo durável (uma convenção, uma armadilha técnica, uma decisão de produto), o lugar é aqui — via PR, revisável — e não só na memória de uma máquina. Foi exatamente esse o erro que motivou esta pasta.

## Índice

| Arquivo | Conteúdo |
|---|---|
| `user_techlead.md` | Quem é o dono do produto |
| `project_s7_vocabulary.md` | Vocabulário fiscal oficial do time de contabilidade |
| `project_s7_legal_bases.md` | Base legal da reforma (LC 214, LC 227) |
| `project_s7_accounting_feedback.md` | Regras e requisitos de relatório definidos pela contabilidade |
| `reference_nt2025002_apis.md` | NT 2025.002-RTC, Calculadora Serpro, ClassTrib SVRS, homologação NF-e |
| `project_s9_domain.md` | Domínio, DNS, Turnstile (site key é pública) |
| `project_s19_sprint.md` | Contexto da sprint 19 e padrão de E2E |
| `project_chat_removed.md` | Chat fiscal removido do produto — não citar em marketing |
| `project_secrets_source_of_truth.md` | Fonte de verdade dos segredos é a VM, não a cópia local |
| `feedback_no_token_rotation.md` | Ordem vigente: não rotacionar credenciais nesta fase |
| `feedback_migrations.md` | Migrations de produção: executar sem pedir confirmação |
| `feedback_bash_vs_native_tools.md` | Usar Read/Grep/Glob em vez de cat/grep/find |
| `feedback_sqlalchemy_cast_syntax.md` | Nunca usar cast `::type` ao lado de `:param` em `sqlalchemy.text()` |
