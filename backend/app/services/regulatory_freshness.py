"""Frescor do dado regulatório cClassTrib — observabilidade da dependência SVRS (#673).

O motor valida contra a tabela cClassTrib embarcada em ``app/data/classtrib.json``.
Essa tabela é mantida fresca pelo workflow ``classtrib-sync`` (cron diário), que
abre PR de revisão quando a SVRS publica códigos novos.

O defeito que este módulo fecha: **se o sync parar, o produto continua respondendo
200 e servindo tabela velha**. Nenhuma probe de ``/health/deep`` cobria a
dependência regulatória — só infraestrutura (db, redis, asaas, hubspot, email,
ai, storage).

## A distinção que este módulo torna inequívoca

Antes, três situações eram indistinguíveis de fora:

1. **fonte consultada, conteúdo idêntico** → saudável, o dado simplesmente não mudou
2. **fonte consultada, conteúdo divergente** → o sync está atrasado; há código novo fora do motor
3. **fonte não verificável** → não sabemos em qual das duas estamos

``source_state`` separa as três (``match`` / ``drift`` / ``unverifiable``).
Colapsá-las de novo reabre exatamente o defeito.

## Por que ``unverifiable`` não degrada de imediato

O próprio coletor documenta que o portal SVRS "falha de forma intermitente
(ConnectTimeout/ReadTimeout em ~30% das execuções diárias)" — por isso ele tem
retry com backoff. Uma probe que degradasse a cada falha pontual produziria
alarme constante e sem informação. Aqui a indisponibilidade da fonte só degrada
quando **combinada** com dado velho: é a conjunção que representa risco real.

## Thresholds

- ``warn`` = 7 dias — a SVRS adiciona códigos com frequência (+8 em 2 dias, já
  observado). Uma semana inteira sem incorporação, sem conseguir confirmar a
  fonte, é anômalo.
- ``fail`` = 21 dias — três ciclos semanais. Incompatível com operação saudável;
  aqui o sync está quebrado, não lento.

Ambos configuráveis (``CLASSTRIB_FRESHNESS_WARN_DAYS`` / ``_FAIL_DAYS``).

## Fora de escopo (#673)

Não acopla às futuras APIs RFB/CGIBS. A camada de integração governamental tem
desenho próprio — ADR-0016, ADR-0017, RFC-0027, RFC-0028, todos ``proposed``.
Este módulo trata da dependência regulatória que **já existe**: a consulta
pública da SVRS, sem credencial.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

import httpx

from app.config import settings
from app.core.observability import capture_alert
from app.data import classtrib_source
from app.data.classtrib_table import (
    CLASSTRIB_BY_CODE,
    CLASSTRIB_CONTENT_SIGNATURE,
    CLASSTRIB_SYNCED_AT,
)

logger = logging.getLogger(__name__)

SOURCE_URL = classtrib_source.SOURCE_URL

#: Resultado da consulta à fonte oficial.
#: - ``match``        fonte consultada; conjunto de códigos idêntico ao embarcado
#: - ``drift``        fonte consultada; conjunto divergente (sync atrasado)
#: - ``unverifiable`` fonte não respondeu / resposta não parseável
SourceState = Literal["match", "drift", "unverifiable"]

#: Veredito de frescor. NUNCA vira ``error`` no HTTP — ver `to_service_status`.
FreshnessStatus = Literal["ok", "degraded", "stale"]

#: Estado da EXECUÇÃO do coletor — eixo distinto do conteúdo da fonte.
SyncExecutionState = Literal["success", "failure", "unverifiable"]

SYNC_RUNS_URL = (
    "https://api.github.com/repos/mickbap/tribultz/actions/workflows/"
    "classtrib-sync.yml/runs?status=completed&per_page=10"
)


@dataclass(frozen=True)
class SourceProbe:
    """Resultado bruto da consulta à SVRS, sem julgamento de frescor."""

    state: SourceState
    remote_codes: Optional[int] = None
    remote_signature: Optional[str] = None
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    error: Optional[str] = None


@dataclass(frozen=True)
class SyncProbe:
    """Última execução observada do coletor no GitHub Actions."""

    state: SyncExecutionState
    last_attempt_at: Optional[str] = None
    last_success_at: Optional[str] = None
    run_url: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class Freshness:
    """Veredito completo — o que o /health/deep expõe."""

    status: FreshnessStatus
    source_state: SourceState
    #: Data da versão EMBARCADA na imagem (meta.date do classtrib.json).
    #: NÃO é "último sync bem-sucedido" — ver `sync_execution`.
    bundled_version_date: Optional[str]
    bundled_version_age_days: Optional[int]
    local_codes: int
    remote_codes: Optional[int]
    detail: str
    added: tuple[str, ...] = field(default=())
    removed: tuple[str, ...] = field(default=())
    #: Consultado diretamente no histórico público do workflow. NUNCA inferido
    #: de `source_state == "match"`, pois conteúdo e execução são eixos distintos.
    sync_execution: SyncExecutionState = "unverifiable"
    sync_last_attempt_at: Optional[str] = None
    sync_last_success_at: Optional[str] = None
    sync_run_url: Optional[str] = None


# ── Consulta à fonte ──────────────────────────────────────────────────────────


def probe_source(
    local: set[str], local_signature: str, *, timeout: float = 10.0
) -> SourceProbe:
    """Consulta a SVRS uma vez e compara o conjunto de códigos com o embarcado.

    SEM retry: retry é responsabilidade do coletor, que tem orçamento de tempo
    para isso. Aqui uma falha isolada vira ``unverifiable`` — que, sozinha, não
    degrada nada (ver docstring do módulo).
    """
    try:
        resp = httpx.get(
            SOURCE_URL,
            timeout=timeout,
            follow_redirects=True,
            headers=classtrib_source.SOURCE_HEADERS,
        )
        resp.raise_for_status()
        normalizado = classtrib_source.normalize(classtrib_source.extract_groups(resp.text))
    except Exception as exc:  # noqa: BLE001 — qualquer falha é "não verificável"
        logger.warning("Freshness: fonte SVRS não verificável — %s", exc)
        return SourceProbe(state="unverifiable", error=str(exc)[:200])

    remote = classtrib_source.codes_of(normalizado)
    if not remote:
        return SourceProbe(state="unverifiable", error="fonte respondeu sem códigos")

    remote_sig = classtrib_source.data_signature(normalizado)
    added = tuple(sorted(remote - local))
    removed = tuple(sorted(local - remote))

    # Assinatura de CONTEÚDO, não conjunto de códigos: mudança de alíquota ou de
    # indicador num código existente também é drift.
    if remote_sig == local_signature:
        return SourceProbe(state="match", remote_codes=len(remote), remote_signature=remote_sig)
    return SourceProbe(
        state="drift", remote_codes=len(remote), remote_signature=remote_sig,
        added=added, removed=removed,
    )


def probe_sync_execution(*, timeout: float = 4.0) -> SyncProbe:
    """Observa a execução diária sem confundi-la com o conteúdo da tabela."""
    try:
        resp = httpx.get(
            SYNC_RUNS_URL,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "tribultz-health/1.0",
            },
        )
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs") or []
        latest = runs[0] if runs else None
        latest_success = next(
            (run for run in runs if run.get("conclusion") == "success"), None
        )
        if not latest:
            return SyncProbe(
                state="unverifiable", error="workflow sem execuções concluídas"
            )
        return SyncProbe(
            state="success" if latest.get("conclusion") == "success" else "failure",
            last_attempt_at=latest.get("updated_at"),
            last_success_at=(
                latest_success.get("updated_at") if latest_success else None
            ),
            run_url=latest.get("html_url"),
        )
    except Exception as exc:  # noqa: BLE001 — falha vira ausência explícita
        logger.warning("Freshness: execução do sync não verificável — %s", exc)
        return SyncProbe(state="unverifiable", error=str(exc)[:200])


# ── Veredito ──────────────────────────────────────────────────────────────────


def _age_days(data_date: Optional[str], now: dt.date) -> Optional[int]:
    if not data_date:
        return None
    try:
        return (now - dt.date.fromisoformat(data_date[:10])).days
    except ValueError:
        return None


def evaluate(
    *,
    local_codes: set[str],
    bundled_version_date: Optional[str],
    probe: SourceProbe,
    now: Optional[dt.date] = None,
    warn_days: Optional[int] = None,
    fail_days: Optional[int] = None,
    sync_probe: Optional[SyncProbe] = None,
) -> Freshness:
    """Combina idade do dado embarcado + estado da fonte. Função pura."""
    now = now or dt.date.today()
    warn = warn_days if warn_days is not None else settings.CLASSTRIB_FRESHNESS_WARN_DAYS
    fail = fail_days if fail_days is not None else settings.CLASSTRIB_FRESHNESS_FAIL_DAYS
    age = _age_days(bundled_version_date, now)
    sync = sync_probe or SyncProbe(state="unverifiable")

    def mk(status: FreshnessStatus, detail: str) -> Freshness:
        """Fecha sobre os campos observados — evita dict heterogêneo com **kwargs."""
        return Freshness(
            status=status,
            source_state=probe.state,
            bundled_version_date=bundled_version_date,
            bundled_version_age_days=age,
            local_codes=len(local_codes),
            remote_codes=probe.remote_codes,
            detail=detail,
            added=probe.added,
            removed=probe.removed,
            sync_execution=sync.state,
            sync_last_attempt_at=sync.last_attempt_at,
            sync_last_success_at=sync.last_success_at,
            sync_run_url=sync.run_url,
        )

    if probe.state == "match":
        # Fonte consultada e idêntica: o dado está CORRETO, independentemente da
        # idade. Idade sozinha nunca condena — só a divergência condena.
        return mk("ok", f"fonte consultada, sem mudança ({len(local_codes)} códigos)")

    if probe.state == "drift":
        return mk(
            "degraded",
            f"fonte consultada, DIVERGENTE: +{len(probe.added)} / "
            f"-{len(probe.removed)} códigos não incorporados",
        )

    # unverifiable — só degrada em conjunção com dado velho.
    if age is None:
        return mk("degraded", "fonte não verificável e data da versão embarcada desconhecida")
    if age >= fail:
        return mk("stale", f"fonte não verificável e versão embarcada com {age}d (limite {fail}d)")
    if age >= warn:
        return mk("degraded", f"fonte não verificável e versão embarcada com {age}d (alerta {warn}d)")
    return mk("ok", f"fonte não verificável agora, mas versão embarcada recente ({age}d)")


def to_service_status(f: Freshness) -> Literal["ok", "degraded"]:
    """Mapeia para o vocabulário das demais probes.

    ``stale`` vira ``degraded``, nunca ``unreachable``: dado regulatório velho é
    problema de confiança, não de disponibilidade. **Nunca indisponibiliza o
    produto** — o critério de aceite é explícito quanto a isso.
    """
    return "ok" if f.status == "ok" else "degraded"


#: cClassTrib é sempre 6 dígitos. Qualquer outra coisa vinda da fonte é
#: descartada antes de virar log/Sentry — a origem não escreve nas nossas
#: trilhas. Amostra limitada: diagnóstico, não dump.
_CODIGO_VALIDO = re.compile(r"^[0-9]{6}$")
_AMOSTRA_MAX = 10


def _amostra_segura(codigos: tuple[str, ...]) -> list[str]:
    return [c for c in codigos if _CODIGO_VALIDO.match(c)][:_AMOSTRA_MAX]


def emit_alert(f: Freshness) -> None:
    """Alerta operacional pelo caminho explícito de captura do projeto.

    Não confia na integração implícita logging→Sentry: chama
    ``capture_alert()``, que faz ``sentry_sdk.capture_message`` quando há DSN e
    sempre registra em log. Assim o caminho do alerta é testável.
    """
    if f.status not in ("stale", "degraded"):
        return
    contexto = {
        "bundled_version_date": f.bundled_version_date,
        "bundled_version_age_days": f.bundled_version_age_days,
        "source_state": f.source_state,
        "sync_execution": f.sync_execution,
        "sync_last_attempt_at": f.sync_last_attempt_at,
        "sync_last_success_at": f.sync_last_success_at,
        "sync_run_url": f.sync_run_url,
        "local_codes": f.local_codes,
        "remote_codes": f.remote_codes,
        # Amostra sanitizada: só o que casa com o formato oficial.
        "codes_added_sample": _amostra_segura(f.added),
        "codes_removed_sample": _amostra_segura(f.removed),
        "codes_added_total": len(f.added),
        "codes_removed_total": len(f.removed),
    }
    if f.status == "stale":
        # Mensagem estável: a idade variável fica no contexto. Assim recorrências
        # da mesma condição agrupam no mesmo issue do Sentry.
        contexto["detail"] = f.detail
        capture_alert("ALERTA regulatório: cClassTrib STALE",
                      level="error", extra=contexto)
    else:
        capture_alert(f"Frescor regulatório degradado: cClassTrib — {f.detail}",
                      level="warning", extra=contexto)


# ── Cache com single-flight ───────────────────────────────────────────────────

_lock = threading.Lock()          # protege a leitura/escrita do valor
_refresh_lock = threading.Lock()  # garante UM fetch por vez neste processo
_cache: Optional[tuple[float, Freshness]] = None


def current(
    *,
    monotonic: Callable[[], float],
    ttl_seconds: Optional[float] = None,  # float: testes usam TTL sub-segundo
    probe_fn: Optional[Callable[[set[str]], SourceProbe]] = None,
    sync_probe_fn: Optional[Callable[[], SyncProbe]] = None,
) -> Freshness:
    """Veredito com cache TTL e **single-flight** — /health/deep não martela a SVRS.

    Round 3 (#673): a versão anterior liberava o lock ANTES do fetch, então N
    requisições concorrentes com cache frio disparavam N requisições ao portal
    público — medido: 12 de 12. As probes rodam em ThreadPoolExecutor, então
    concorrência aqui é o caso normal, não a exceção.

    Agora:

    - **cache quente** → devolve na hora, sem tocar em lock de refresh;
    - **cache frio** → todos bloqueiam; o primeiro busca, os demais acordam,
      reveem o cache já preenchido e voltam sem buscar (12 → 1 fetch);
    - **cache vencido mas existente** → o primeiro renova; os demais recebem o
      **último valor conhecido** imediatamente, sem bloquear (stale-while-
      revalidate). Servir dado de 15 min atrás é melhor que segurar o health.

    Escopo deliberado: single-flight **por processo**. Coordenação entre réplicas
    seria arquitetura distribuída nova e não cabe neste Round.
    """
    ttl = ttl_seconds if ttl_seconds is not None else settings.CLASSTRIB_FRESHNESS_TTL_SECONDS

    with _lock:
        cached = _cache
    if cached is not None and (monotonic() - cached[0]) < ttl:
        return cached[1]

    # Sem valor algum ⇒ é obrigatório esperar. Com valor velho ⇒ não bloqueia.
    if not _refresh_lock.acquire(blocking=(cached is None)):
        return cached[1]  # type: ignore[index] — não-bloqueante só com cache existente

    try:
        # Outro thread pode ter renovado enquanto este esperava no lock.
        with _lock:
            atual = _cache
        if atual is not None and (monotonic() - atual[0]) < ttl:
            return atual[1]

        local = set(CLASSTRIB_BY_CODE.keys())
        probe = (
            probe_fn(local) if probe_fn
            else probe_source(local, CLASSTRIB_CONTENT_SIGNATURE)
        )
        # Testes que injetam a fonte continuam herméticos; produção observa o
        # workflow público, ou aceita uma probe explicitamente injetada.
        sync_probe = (
            sync_probe_fn() if sync_probe_fn
            else probe_sync_execution() if probe_fn is None
            else SyncProbe(state="unverifiable")
        )
        verdict = evaluate(
            local_codes=local,
            bundled_version_date=CLASSTRIB_SYNCED_AT,
            probe=probe,
            sync_probe=sync_probe,
        )
        emit_alert(verdict)

        with _lock:
            _cache_novo = (monotonic(), verdict)
            globals()["_cache"] = _cache_novo
        return verdict
    finally:
        _refresh_lock.release()


def reset_cache() -> None:
    """Usado por testes — nunca em produção."""
    global _cache
    with _lock:
        _cache = None
