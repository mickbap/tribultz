"""Guard do publicador do changelog público (`.github/scripts/publish_news.py`).

Contexto (incidente 16/08/2026, Lote 0 da ordem QA→Techlead): o script publicava
o primeiro parágrafo do body INTERNO do PR quando a seção `## Changelog público`
estava ausente — todo merge feat/fix/security em `main` virava entrada pública
com conteúdo de processo. A correção inverte o default para opt-in estrito e
adiciona uma denylist de vocabulário interno como rede de segurança.

Estes testes fixam as duas propriedades como contrato: **sem seção declarada,
nada é publicado** e **termos internos abortam a publicação**. O teste vive em
backend/tests/ para rodar nos gates de CI (job backend-gates), seguindo o mesmo
padrão de test_architecture_audit_smoke.py para script fora da árvore do backend.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "publish_news.py"


@pytest.fixture(scope="module")
def pn():
    spec = importlib.util.spec_from_file_location("publish_news_under_test", SCRIPT)
    assert spec and spec.loader, f"não consegui carregar {SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TITULADO_BODY = """\
Contexto interno.

## Changelog público

Título: Relatório agora resume por nota fiscal

O relatório de validação passou a trazer o resumo por nota.

## Notas
Interno.
"""

PUBLIC_SECTION_BODY = """\
Contexto interno que jamais pode vazar: rodamos o deploy na VM depois do rollback.

## Changelog público

Agora o relatório de validação sai com o resumo por nota fiscal.

## Notas de revisão
Detalhe interno de processo.
"""

NO_SECTION_BODY = """\
## Resumo
Corrige a contagem de regras exibida no diagnóstico.

## Como testar
Rodar a suíte.
"""


@pytest.fixture
def capture_post(pn, monkeypatch):
    """Substitui httpx.post e devolve a lista de payloads enviados."""
    sent: list[dict] = []

    class _Resp:
        status_code = 201

        @staticmethod
        def json() -> dict:
            return {"id": "news-1"}

    def _fake_post(url, json=None, headers=None, timeout=None):  # noqa: A002
        sent.append({"url": url, "payload": json})
        return _Resp()

    monkeypatch.setattr(pn.httpx, "post", _fake_post)
    return sent


@pytest.fixture
def run_main(pn, monkeypatch):
    """Executa main() com commit/PR simulados e ambiente completo."""

    def _run(*, subject: str, pr_body: str, labels: list[str] | None = None, pr_ref: str = "(#777)"):
        monkeypatch.setenv("COMMIT_SHA", "deadbeef")
        monkeypatch.setenv("BACKEND_URL", "https://api.example.test")
        monkeypatch.setenv("NEWS_PUBLISH_TOKEN", "token-de-teste")
        monkeypatch.setattr(pn, "get_commit_subject", lambda sha: f"{subject} {pr_ref}".strip())
        monkeypatch.setattr(pn, "get_commit_body", lambda sha: "")
        monkeypatch.setattr(
            pn,
            "fetch_pr_data",
            lambda n: {"body": pr_body, "labels": [{"name": x} for x in (labels or [])]},
        )
        return pn.main()

    return _run


# --- L0.1 — opt-in estrito -------------------------------------------------


def test_sem_secao_nao_publica(run_main, capture_post):
    """PR sem `## Changelog público` → skip silencioso, exit 0, zero POST."""
    assert run_main(subject="feat(site): melhora a tela de diagnóstico", pr_body=NO_SECTION_BODY) == 0
    assert capture_post == []


def test_com_secao_publica_somente_a_secao(run_main, capture_post):
    """Publica a seção declarada — e nada do body interno ao redor dela."""
    assert run_main(subject="feat(reports): resumo por nota fiscal", pr_body=TITULADO_BODY) == 0
    assert len(capture_post) == 1
    description = capture_post[0]["payload"]["description"]
    assert "resumo por nota" in description
    assert "Contexto interno" not in description
    assert "Interno." not in description


def test_body_vazio_nao_publica(run_main, capture_post):
    """Sem body de PR (ou `gh` falhando) o fail-safe é não publicar."""
    assert run_main(subject="fix(site): ajuste de rótulo", pr_body="") == 0
    assert capture_post == []


def test_sem_pr_referenciado_nao_publica(run_main, capture_post):
    """Commit direto em main, sem PR: não há seção declarável → não publica."""
    assert run_main(subject="fix(site): ajuste de rótulo", pr_body=PUBLIC_SECTION_BODY, pr_ref="") == 0
    assert capture_post == []


def test_label_no_changelog_vence_a_secao(run_main, capture_post):
    """`no-changelog` bloqueia mesmo com a seção presente."""
    assert (
        run_main(
            subject="fix(site): contenção do feed público",
            pr_body=PUBLIC_SECTION_BODY,
            labels=["no-changelog"],
        )
        == 0
    )
    assert capture_post == []


def test_build_description_sem_fallback(pn):
    """A função não inventa descrição: sem seção, retorna None."""
    assert pn.build_description(NO_SECTION_BODY) is None
    assert pn.build_description("") is None
    assert pn.build_description(PUBLIC_SECTION_BODY) is not None


# --- L0.2 — denylist de termos internos ------------------------------------


@pytest.mark.parametrize(
    "termo",
    ["deploy", "branch", "migration", "SSH", "Redis", "worker", "beat", "Round 8", "gate", "PR #42", "main"],
)
def test_denylist_aborta_publicacao(run_main, capture_post, termo):
    """Termo interno na seção pública → exit 1 e nenhum POST."""
    body = f"## Changelog público\n\nTítulo: Melhoria entregue\n\nEntregue via {termo} nesta versão.\n"
    assert run_main(subject="feat(site): melhoria", pr_body=body) == 1
    assert capture_post == []


def test_denylist_alcanca_o_titulo_declarado(run_main, capture_post):
    """A denylist protege o título DECLARADO pelo autor.

    Antes de o `Título:` ser obrigatório, esta checagem servia para barrar o
    assunto do commit, que virava título por fallback. Com o fallback removido,
    o assunto interno já não chega ao feed — mas o autor ainda pode escrever
    vocabulário de processo na linha `Título:`, e é isso que a denylist pega.
    """
    body = "## Changelog público\n\nTítulo: Rollback da migration executado\n\nCorreção entregue.\n"
    assert run_main(subject="fix(reports): resumo", pr_body=body) == 1
    assert capture_post == []


def test_assunto_interno_do_commit_nao_impede_publicacao(run_main, capture_post):
    """Efeito colateral desejado do título obrigatório: o assunto do commit deixa
    de contaminar o feed, então commit interno com seção bem escrita publica."""
    body = "## Changelog público\n\nTítulo: Resumo por nota fiscal\n\nRelatório agora traz o resumo por nota.\n"
    assert run_main(subject="fix(crm): ajuste no worker do beat", pr_body=body) == 0
    assert capture_post[0]["payload"]["title"] == "Resumo por nota fiscal"


def test_copy_publica_legitima_passa(run_main, capture_post):
    """Rede de segurança não pode bloquear linguagem de cliente."""
    body = (
        "## Changelog público\n\nTítulo: Detalhamento por item na calculadora\n\n"
        "A calculadora CBS/IBS passou a aceitar NCM de 8 dígitos e mostra o "
        "detalhamento por item da nota fiscal.\n"
    )
    assert run_main(subject="feat(calculadora): detalhamento por item", pr_body=body) == 0
    assert len(capture_post) == 1


def test_find_internal_terms_lista_os_achados(pn):
    hits = pn.find_internal_terms("Deploy concluído", "rodamos o worker no Redis")
    assert {h.lower() for h in hits} == {"deploy", "worker", "redis"}
    assert pn.find_internal_terms("Resumo por nota fiscal no relatório") == []


# --- detecção do número do PR (regressão de 17/08) --------------------------


def test_detecta_pr_do_fim_do_assunto_nao_a_issue(pn):
    """Squash merge: `titulo (#issue) (#PR)` — vale o do fim.

    Este é o defeito que fez o feed parar: a busca pegava o primeiro `#N`, que
    é a issue citada no título. `gh pr view <issue>` falha, o body vinha vazio e
    tudo era pulado com a mensagem de "sem seção", mascarando a causa.
    """
    assert pn.detect_pr_number("feat(billing): Trial com fonte única (#635) (#647)", "") == "647"
    assert pn.detect_pr_number("fix(seo): canonical por rota (#634) (#641)", "") == "641"


def test_detecta_pr_sem_sufixo_de_squash(pn):
    """Merge commit comum: fica o último #N citado, não o primeiro."""
    assert pn.detect_pr_number("fix: algo", "Fecha #100\nRef #204") == "204"


def test_sem_numero_algum(pn):
    assert pn.detect_pr_number("chore: sem referência", "") is None


def test_fluxo_completo_usa_o_pr_correto(run_main, capture_post, monkeypatch, pn):
    """O body consultado tem de ser o do PR, não o da issue."""
    vistos: list[str] = []

    def _fetch(n):
        vistos.append(n)
        return {"body": TITULADO_BODY, "labels": []}

    monkeypatch.setattr(pn, "fetch_pr_data", _fetch)
    monkeypatch.setenv("COMMIT_SHA", "deadbeef")
    monkeypatch.setenv("BACKEND_URL", "https://api.example.test")
    monkeypatch.setenv("NEWS_PUBLISH_TOKEN", "token-de-teste")
    monkeypatch.setattr(pn, "get_commit_subject", lambda sha: "feat(reports): resumo por nota fiscal (#635) (#647)")
    monkeypatch.setattr(pn, "get_commit_body", lambda sha: "")

    assert pn.main() == 0
    assert vistos == ["647"], f"consultou o PR errado: {vistos}"
    assert len(capture_post) == 1


# --- título público declarado na seção (regressão de 17/08) -----------------


def test_titulo_publico_governa_o_titulo(run_main, capture_post):
    """Sem isso o título vem do commit, que é interno por convenção.

    A primeira publicação do regime novo saiu com descrição em linguagem de
    cliente e título "Publicador do changelog lia o número da ISSUE, não o do
    PR" — internamente irrelevante, e a denylist não podia pegar porque não há
    palavra proibida ali.
    """
    assert run_main(subject="fix(ci): publicador lia o número errado", pr_body=TITULADO_BODY) == 0
    assert len(capture_post) == 1
    payload = capture_post[0]["payload"]
    assert payload["title"] == "Relatório agora resume por nota fiscal"
    assert "publicador" not in payload["title"].lower()


def test_linha_de_titulo_nao_vaza_para_a_descricao(run_main, capture_post):
    assert run_main(subject="fix(reports): resumo", pr_body=TITULADO_BODY) == 0
    descricao = capture_post[0]["payload"]["description"]
    assert "Título:" not in descricao
    assert "resumo por nota" in descricao


def test_secao_sem_titulo_aborta(run_main, capture_post):
    """Título público é obrigatório (decisão de 17/08).

    O fallback para o assunto do commit foi removido: assunto segue Conventional
    Commits e é interno por convenção — foi ele que publicou "[Fix] Publicador do
    changelog lia o número da ISSUE" no feed do cliente. Quem declara a seção
    escreve o título que o cliente vai ler, ou nada sai.
    """
    assert run_main(subject="feat(reports): resumo por nota fiscal", pr_body=PUBLIC_SECTION_BODY) == 1
    assert capture_post == []


# --- exemplo em bloco de código não é declaração (regressão de 17/08) --------

EXEMPLO_EM_FENCE = """\
Este PR cria o recurso. A sintaxe fica assim:

```markdown
## Changelog público

Título: Exemplo que NÃO deve ser publicado

Corpo de demonstração.
```

Sem essa linha, o comportamento é o de hoje.

## Changelog público

Título: Título verdadeiro do autor

Descrição verdadeira para o cliente.
"""

SO_EXEMPLO = """\
PR que apenas documenta a sintaxe:

```markdown
## Changelog público

Título: Só um exemplo

Corpo de demonstração.
```

Nada é declarado de verdade aqui.
"""


def test_exemplo_em_bloco_de_codigo_nao_vira_publicacao(run_main, capture_post):
    """Foi o defeito do #649: o corpo trazia o exemplo do recurso recém-criado
    e o publicador tomou a demonstração por declaração."""
    assert run_main(subject="fix(ci): documenta a seção", pr_body=EXEMPLO_EM_FENCE) == 0
    assert len(capture_post) == 1
    payload = capture_post[0]["payload"]
    assert payload["title"] == "Título verdadeiro do autor"
    assert "NÃO deve ser publicado" not in payload["description"]
    assert "```" not in payload["description"]


def test_pr_que_so_mostra_exemplo_nao_publica(run_main, capture_post):
    """Sem declaração real, nada sai — mesmo com a seção aparecendo no texto.

    Tipo publicável de propósito (`fix`): com `docs` o script pararia antes de
    olhar o corpo, e o teste passaria sem exercitar nada.
    """
    assert run_main(subject="fix(ci): explica a seção", pr_body=SO_EXEMPLO) == 0
    assert capture_post == []


def test_strip_code_fences_preserva_o_resto(pn):
    texto = "antes\n```\ndentro\n```\ndepois"
    limpo = pn.strip_code_fences(texto)
    assert "dentro" not in limpo
    assert "antes" in limpo and "depois" in limpo
