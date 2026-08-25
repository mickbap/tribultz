"""#673 — frescor do dado regulatório cClassTrib.

O defeito coberto: o `classtrib-sync` pode parar e o produto continuar 200,
servindo tabela velha. Os testes fixam três coisas que não podem regredir:

1. **`match` ≠ `unverifiable`** — antes eram o mesmo silêncio.
2. **Drift por atributo** — mudar alíquota de um código existente não pode dar `match`.
3. **Versão embarcada ≠ execução do sync** — `bundled_version_*` descreve o que está
   na imagem; `sync_execution` permanece `unobservable` até a fatia de heartbeat.

Nenhum teste toca a rede: a consulta à fonte é sempre injetada.
"""

from __future__ import annotations

import datetime as dt
import logging

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.config import Settings, settings
from app.data import classtrib_source
from app.main import app
from app.services import regulatory_freshness as rf


@pytest.fixture(autouse=True)
def _cache_limpo():
    """Cache é estado de módulo: sem isto um teste contamina o seguinte."""
    rf.reset_cache()
    yield
    rf.reset_cache()


HOJE = dt.date(2026, 8, 25)
LOCAL = {"000001", "000002", "000003"}

def _cls(codigo, red=0.0):
    return {"CodClassTrib": codigo, "NomeClassTrib": f"Classificação {codigo}",
            "PercRedIbs": red, "PercRedCbs": red, "TipoAliq": "P",
            "DthIniVig": "2026-01-01", "TexUrlLegislacao": "https://exemplo/lc214"}


# `extract_groups` só aceita blobs com mais de 2000 caracteres (heurística que
# separa o payload real de JSONs pequenos espalhados pela página). O fixture
# precisa ser grande o suficiente para atravessar esse filtro.
GRUPOS = [
    {"Cst": "000", "NomeCst": "Tributação integral",
     "ClassificacoesTributarias": [_cls("000001"), _cls("000002")]
     + [_cls(f"0001{i:02d}") for i in range(10)]},
    {"Cst": "400", "NomeCst": "Isenção",
     "ClassificacoesTributarias": [_cls("000003", red=60.0)]
     + [_cls(f"0004{i:02d}") for i in range(10)]},
]
LOCAL_FIXTURE = {c["CodClassTrib"] for g in GRUPOS for c in g["ClassificacoesTributarias"]}


def _f(state, *, versao, remote=None, added=(), removed=()):
    probe = rf.SourceProbe(state=state, remote_codes=remote, added=added, removed=removed)
    return rf.evaluate(
        local_codes=LOCAL, bundled_version_date=versao, probe=probe, now=HOJE,
        warn_days=7, fail_days=21,
    )


def _resposta_svrs(grupos):
    """httpx.get falso devolvendo uma página com o blob JSON embutido."""
    import json as _json
    resp = patch("app.services.regulatory_freshness.httpx.get").start()
    resp.return_value.text = f"<html><script>var d = {_json.dumps(grupos)};</script></html>"
    resp.return_value.raise_for_status = lambda: None
    return resp


# ── 1 · A distinção inegociável ───────────────────────────────────────────────


def test_fonte_consultada_sem_mudanca_e_saudavel_mesmo_com_versao_velha():
    """`match` = a fonte confirmou que nada mudou. Idade sozinha não condena.

    Uma versão de 60 dias cuja fonte responde "idêntico" está CORRETA. Degradar
    por idade aqui seria alarme falso — e ensinaria o plantão a ignorar o sinal.
    """
    f = _f("match", versao="2026-06-26", remote=3)
    assert f.status == "ok"
    assert f.bundled_version_age_days == 60
    assert "sem mudança" in f.detail


def test_os_dois_estados_nao_colapsam():
    """Trava explícita: match e unverifiable, MESMA idade, vereditos diferentes."""
    velha = "2026-08-10"  # 15 dias — entre warn(7) e fail(21)
    assert _f("match", versao=velha, remote=3).status == "ok"
    assert _f("unverifiable", versao=velha).status == "degraded"


# ── 2 · Drift por conteúdo, não por lista de códigos ──────────────────────────


def test_mudanca_de_atributo_em_codigo_existente_e_drift():
    """O ponto que a revisão exigiu: mesmo conjunto de códigos, conteúdo diferente.

    Se a comparação fosse por `set(CodClassTrib)`, uma alteração de alíquota
    passaria como `match` — falso "está tudo certo" sobre dado fiscal errado.
    """
    base = classtrib_source.normalize(GRUPOS)
    assinatura_local = classtrib_source.data_signature(base)

    alterado = [dict(g, ClassificacoesTributarias=[dict(c) for c in g["ClassificacoesTributarias"]])
                for g in GRUPOS]
    alterado[1]["ClassificacoesTributarias"][0]["PercRedIbs"] = 100  # 60% → 100%

    assert classtrib_source.codes_of(classtrib_source.normalize(alterado)) == \
        classtrib_source.codes_of(base), "pré-condição: o CONJUNTO de códigos não muda"

    try:
        _resposta_svrs(alterado)
        p = rf.probe_source(LOCAL_FIXTURE, assinatura_local)
    finally:
        patch.stopall()

    assert p.state == "drift", "alteração de atributo tem de ser drift, não match"
    assert p.added == () and p.removed == (), "nenhum código entrou ou saiu"


def test_conteudo_identico_e_match():
    base = classtrib_source.normalize(GRUPOS)
    try:
        _resposta_svrs(GRUPOS)
        p = rf.probe_source(LOCAL_FIXTURE, classtrib_source.data_signature(base))
    finally:
        patch.stopall()
    assert p.state == "match" and p.remote_codes == len(LOCAL_FIXTURE)


def test_codigo_novo_aparece_no_diff_legivel():
    base = classtrib_source.normalize(GRUPOS)
    mais = [dict(g) for g in GRUPOS]
    mais.append({"Cst": "410", "NomeCst": "Imunidade", "ClassificacoesTributarias": [
        {"CodClassTrib": "900001", "NomeClassTrib": "Novo", "DthIniVig": "2026-08-01"}]})
    try:
        _resposta_svrs(mais)
        p = rf.probe_source(LOCAL_FIXTURE, classtrib_source.data_signature(base))
    finally:
        patch.stopall()
    assert p.state == "drift" and p.added == ("900001",)


def test_assinatura_ignora_meta():
    """Só o carimbo de data mudar não pode ser lido como mudança de conteúdo."""
    a = classtrib_source.normalize(GRUPOS, today=dt.date(2026, 1, 1))
    b = classtrib_source.normalize(GRUPOS, today=dt.date(2026, 8, 25))
    assert a["meta"]["date"] != b["meta"]["date"]
    assert classtrib_source.data_signature(a) == classtrib_source.data_signature(b)


# ── 3 · Versão embarcada ≠ execução do sync ───────────────────────────────────


def test_sync_execution_permanece_unobservable_mesmo_com_match():
    """`match` prova CONTEÚDO, não que o coletor rodou.

    Se o sync estiver quebrado e a SVRS não tiver publicado nada, o conteúdo
    bate e o veredito é `ok` — corretamente. Mas isso NÃO é evidência de
    execução, e o contrato não pode sugerir que é.
    """
    f = _f("match", versao="2026-08-24", remote=3)
    assert f.status == "ok"
    assert f.sync_execution == "unobservable"


def test_campos_nomeiam_versao_embarcada_nao_ultimo_sync():
    f = _f("unverifiable", versao="2026-08-01")
    assert hasattr(f, "bundled_version_date") and hasattr(f, "bundled_version_age_days")
    assert not hasattr(f, "data_date"), "nome ambíguo não pode voltar"
    assert "versão embarcada" in f.detail


# ── Matriz de status ──────────────────────────────────────────────────────────


def test_drift_degrada_e_nomeia_os_codigos():
    f = _f("drift", versao="2026-08-24", remote=5, added=("900001", "900002"))
    assert f.status == "degraded" and "+2" in f.detail


def test_fonte_nao_verificavel_com_versao_recente_nao_degrada():
    """O portal SVRS falha em ~30% das execuções. Falha pontual não é incidente."""
    assert _f("unverifiable", versao="2026-08-24").status == "ok"


@pytest.mark.parametrize("versao,esperado", [
    ("2026-08-19", "ok"),        # 6d  — abaixo do warn
    ("2026-08-18", "degraded"),  # 7d  — exatamente no warn
    ("2026-08-05", "degraded"),  # 20d — abaixo do fail
    ("2026-08-04", "stale"),     # 21d — exatamente no fail
])
def test_thresholds_de_idade(versao, esperado):
    assert _f("unverifiable", versao=versao).status == esperado


def test_versao_desconhecida_nunca_vira_ok():
    f = _f("unverifiable", versao=None)
    assert f.status == "degraded" and f.bundled_version_age_days is None


# ── Nunca indisponibiliza o produto ───────────────────────────────────────────


@pytest.mark.parametrize("status", ["ok", "degraded", "stale"])
def test_to_service_status_nunca_e_unreachable(status):
    f = rf.Freshness(status=status, source_state="unverifiable",
                     bundled_version_date="2026-08-01", bundled_version_age_days=24,
                     local_codes=3, remote_codes=None, detail="")
    assert rf.to_service_status(f) in ("ok", "degraded")


def _probes_ok(**extra):
    alvos = {"_probe_db": "ok", "_probe_redis": "ok", "_probe_s3": "ok",
             "_probe_asaas": "unconfigured", "_probe_ai_engine": "unconfigured",
             "_probe_hubspot": "unconfigured", "_probe_email": "unconfigured", **extra}
    return [patch(f"app.routers.health.{k}", return_value=v) for k, v in alvos.items()]


def test_endpoint_nao_vira_error_por_dado_regulatorio():
    stale = rf.Freshness(
        status="stale", source_state="unverifiable", bundled_version_date="2026-07-01",
        bundled_version_age_days=55, local_codes=164, remote_codes=None,
        detail="fonte não verificável e versão embarcada com 55d (limite 21d)",
    )
    ctx = _probes_ok(_probe_classtrib=stale)
    for c in ctx:
        c.start()
    try:
        body = TestClient(app).get("/health/ready").json()
    finally:
        patch.stopall()

    assert body["status"] == "degraded"          # nunca "error"
    assert body["classtrib"] == "degraded"
    ev = body["classtrib_freshness"]
    assert ev["source_state"] == "unverifiable"
    assert ev["bundled_version_date"] == "2026-07-01"
    assert ev["bundled_version_age_days"] == 55
    assert ev["sync_execution"] == "unobservable"


def test_endpoint_omite_evidencia_quando_desligado():
    """Default OFF (dev/CI): contrato antigo preservado e nenhuma chamada à SVRS."""
    assert settings.CLASSTRIB_FRESHNESS_ENABLED is False
    for c in _probes_ok():
        c.start()
    try:
        body = TestClient(app).get("/health/ready").json()
    finally:
        patch.stopall()
    assert body["status"] == "ok"
    assert body["classtrib"] == "unconfigured"
    assert body["classtrib_freshness"] is None


# ── 4 · Alerta real e gate de produção ────────────────────────────────────────


def test_alerta_stale_usa_capture_alert_com_nivel_error():
    """Prova o caminho REAL do alerta, não a integração implícita de logging."""
    f = _f("unverifiable", versao="2026-07-01")
    assert f.status == "stale"
    with patch("app.services.regulatory_freshness.capture_alert") as cap:
        rf.emit_alert(f)
    cap.assert_called_once()
    assert cap.call_args.kwargs["level"] == "error"
    assert "STALE" in cap.call_args.args[0]
    assert cap.call_args.kwargs["extra"]["sync_execution"] == "unobservable"


def test_alerta_degraded_usa_nivel_warning():
    with patch("app.services.regulatory_freshness.capture_alert") as cap:
        rf.emit_alert(_f("drift", versao="2026-08-24", remote=4, added=("900001",)))
    assert cap.call_args.kwargs["level"] == "warning"


def test_ok_nao_alerta():
    with patch("app.services.regulatory_freshness.capture_alert") as cap:
        rf.emit_alert(_f("match", versao="2026-08-24", remote=3))
    cap.assert_not_called()


def test_capture_alert_envia_ao_sentry_quando_ha_dsn(caplog):
    from app.core import observability

    with patch.object(settings, "SENTRY_DSN", "https://k@o.ingest.sentry.io/1"), \
         patch("sentry_sdk.capture_message") as cap, \
         patch("sentry_sdk.push_scope"):
        enviado = observability.capture_alert("teste", level="error", extra={"a": 1})
    assert enviado is True
    cap.assert_called_once_with("teste", level="error")


def test_capture_alert_sem_dsn_e_no_op_mas_registra(caplog):
    from app.core import observability

    with patch.object(settings, "SENTRY_DSN", ""), \
         caplog.at_level(logging.WARNING, logger="app.core.observability"):
        enviado = observability.capture_alert("sem dsn", level="warning")
    assert enviado is False
    assert any("sem dsn" in r.getMessage() for r in caplog.records)


def test_producao_nao_sobe_com_observabilidade_regulatoria_desligada():
    """Gate: o default seguro de dev não pode virar cegueira silenciosa em prod."""
    base = dict(
        POSTGRES_PASSWORD="x", DATABASE_URL="postgresql://u:p@h/d", REDIS_URL="redis://h/0",
        JWT_SECRET="x" * 32, MINIO_ROOT_USER="u", MINIO_ROOT_PASSWORD="p",
        S3_ENDPOINT="http://h", S3_BUCKET="b", S3_ACCESS_KEY="k", S3_SECRET_KEY="s",
    )
    with pytest.raises(ValueError, match="CLASSTRIB_FRESHNESS_ENABLED"):
        Settings(ENVIRONMENT="production", CLASSTRIB_FRESHNESS_ENABLED=False, **base)

    ok = Settings(ENVIRONMENT="production", CLASSTRIB_FRESHNESS_ENABLED=True, **base)
    assert ok.CLASSTRIB_FRESHNESS_ENABLED is True
    # dev/CI seguem livres com o default OFF
    assert Settings(ENVIRONMENT="development", **base).CLASSTRIB_FRESHNESS_ENABLED is False


# ── Cache ─────────────────────────────────────────────────────────────────────


def test_cache_evita_martelar_a_fonte_publica():
    chamadas = []

    def fake(local):
        chamadas.append(1)
        return rf.SourceProbe(state="match", remote_codes=len(local))

    t = [1000.0]
    for _ in range(3):
        rf.current(monotonic=lambda: t[0], ttl_seconds=900, probe_fn=fake)
    assert len(chamadas) == 1, "3 chamadas dentro do TTL deveriam consultar a fonte 1×"

    t[0] += 901
    rf.current(monotonic=lambda: t[0], ttl_seconds=900, probe_fn=fake)
    assert len(chamadas) == 2, "após o TTL a fonte deve ser reconsultada"


def test_probe_source_converte_falha_de_rede_em_unverifiable():
    with patch("app.services.regulatory_freshness.httpx.get", side_effect=OSError("timeout")):
        p = rf.probe_source(LOCAL, "assinatura-qualquer")
    assert p.state == "unverifiable" and "timeout" in (p.error or "")
