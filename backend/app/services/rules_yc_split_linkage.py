"""Grupo YC — Vinculação com a Transação de Pagamento do DF-e (#683).

Fonte: **NT 2026.006 v1.00**, adquirida do Portal Nacional da NF-e. Domínio de
``tpMeioPgto``: **IT 2026.001 v1.01** sobre a Tabela Nacional.

FRONTEIRAS DO ARTEFATO — não são opinião nossa, são texto oficial
─────────────────────────────────────────────────────────────────
- *"Não há exigência de preenchimento ou uso dos campos de split payment em
  2026 no ambiente de produção"*. Grupo ausente ⇒ **zero achado**. Sempre.
- *"o DF-e deverá reportar os dados das transações financeiras previamente
  iniciadas, **ainda que estejam pendentes de efetivo pagamento e
  liquidação**"*. Vínculo ≠ pagamento ≠ liquidação.
- *"É possível que o CNPJ do recebedor seja diferente do CNPJ do fornecedor
  constante no documento fiscal"*. Recebedor divergente do emitente **não** é
  erro.
- O grupo **não tem campo de valor**. Não há como calcular split a partir do
  DF-e, e nada aqui tenta.

O QUE ESTE MÓDULO NÃO CRIA
──────────────────────────
``valor_pago``, ``valor_split``, ``liquidado``, ``data_liquidacao``,
``conta_rateio``. Nenhum existe no leiaute; nenhum nasce porque sobrou espaço
numa dataclass.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Optional

from app.data import payment_methods
from app.services.cnpj_validator import is_valid_cnpj_format

#: Cronograma da NT 2026.006 v1.00 para o grupo YC.
HOMOLOGACAO = dt.date(2026, 10, 5)
PRODUCAO = dt.date(2026, 11, 3)

AMBIENTE_HOMOLOGACAO = "HOMOLOGACAO"
AMBIENTE_PRODUCAO = "PRODUCAO"

#: Naturezas de achado. SCHEMA_VALIDATION existe para que a 215 nunca seja
#: lida como conclusão tributária — é falha de esquema XML, e mais nada.
NATUREZA_SCHEMA = "SCHEMA_VALIDATION"
NATUREZA_CONTEUDO = "CONTENT_VALIDATION"

CSTAT_UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True)
class TransacaoVinculada:
    """Uma ocorrência de ``gPgto``. Só o que o leiaute define."""

    n_pag: Optional[str] = None
    id_transacao: Optional[str] = None
    tp_meio_pgto: Optional[str] = None
    cnpj_receb: Optional[str] = None
    cnpj_base_psp: Optional[str] = None


@dataclass(frozen=True)
class GrupoYC:
    presente: bool
    transacoes: list[TransacaoVinculada] = field(default_factory=list)


@dataclass(frozen=True)
class AchadoYC:
    regra: str
    natureza: str
    #: ``int`` quando o artefato é unívoco; ``"UNDETERMINED"`` quando dois
    #: artefatos oficiais divergem. Nunca escolhido por nós.
    cstat_esperado: object
    n_pag: Optional[str]
    detalhe: str
    #: A condição é determinada mesmo antes do corte; o que o corte muda é se
    #: ela já vale como rejeição naquele ambiente.
    determinante_no_ambiente: bool
    evidencia: dict = field(default_factory=dict)


_ATTR = r'{attr}\s*=\s*"([^"]*)"'


def parse_grupo_yc(xml: str) -> GrupoYC:
    """Extrai ``gPgtoVinc``/``gPgto`` do XML. Ausência é ausência, não erro."""
    m = re.search(r"<gPgtoVinc(?=[\s>/])[^>]*>([\s\S]*?)</gPgtoVinc>", xml, re.I)
    if not m:
        return GrupoYC(presente=False)

    transacoes: list[TransacaoVinculada] = []
    for bloco in re.finditer(r"<gPgto(?=[\s>/])([^>]*)>([\s\S]*?)</gPgto>", m.group(1), re.I):
        attrs, corpo = bloco.group(1), bloco.group(2)

        def _attr(nome: str) -> Optional[str]:
            a = re.search(_ATTR.format(attr=nome), attrs, re.I)
            return a.group(1).strip() if a else None

        def _tag(nome: str) -> Optional[str]:
            t = re.search(rf"<{nome}(?=[\s>/])[^>]*>([\s\S]*?)</{nome}>", corpo, re.I)
            return t.group(1).strip() if t else None

        transacoes.append(TransacaoVinculada(
            # nPag e idTransacao são ATRIBUTOS no leiaute (Ele=A); aceitamos
            # também como elemento porque emissores erram e o objetivo é
            # validar o conteúdo, não punir a forma de serialização.
            n_pag=_attr("nPag") or _tag("nPag"),
            id_transacao=_attr("idTransacao") or _tag("idTransacao"),
            tp_meio_pgto=_tag("tpMeioPgto"),
            cnpj_receb=_tag("CNPJReceb"),
            cnpj_base_psp=_tag("CNPJBasePSP"),
        ))
    return GrupoYC(presente=True, transacoes=transacoes)


def _determinante(emissao: Optional[dt.date], ambiente: Optional[str]) -> bool:
    """A regra já vale como rejeição neste ambiente/data?

    Sem data não assume vigência: presumir "hoje" faria regra futura disparar
    sobre documento cuja data não conhecemos.
    """
    if emissao is None:
        return False
    if ambiente == AMBIENTE_HOMOLOGACAO:
        return emissao >= HOMOLOGACAO
    if ambiente == AMBIENTE_PRODUCAO:
        return emissao >= PRODUCAO
    return False


def avaliar(
    grupo: GrupoYC,
    *,
    emissao: Optional[dt.date] = None,
    ambiente: Optional[str] = None,
) -> list[AchadoYC]:
    """Avalia YC03-10, YC04-20, YC05-10 e YC06-10.

    Grupo ausente ⇒ lista vazia, sempre. O artefato veda exigir preenchimento
    em 2026, e "não informou" nunca vira achado.
    """
    if not grupo.presente:
        return []

    det = _determinante(emissao, ambiente)
    achados: list[AchadoYC] = []

    # ── YC03-10 / YC04-20 — duplicidade (Rejeição 215, falha de esquema) ────
    for regra, campo, extrator in (
        ("YC03-10", "nPag", lambda t: t.n_pag),
        ("YC04-20", "idTransacao", lambda t: t.id_transacao),
    ):
        vistos: dict[str, int] = {}
        for t in grupo.transacoes:
            v = extrator(t)
            if not v:
                continue
            vistos[v] = vistos.get(v, 0) + 1
            if vistos[v] == 2:
                achados.append(AchadoYC(
                    regra=regra, natureza=NATUREZA_SCHEMA, cstat_esperado=215,
                    n_pag=t.n_pag,
                    detalhe=f'Atributo "{campo}" duplicado no grupo gPgtoVinc: {v}',
                    determinante_no_ambiente=det,
                    evidencia={"campo": campo, "valor": v,
                               "observacao_oficial": "Validação realizada pelo Schema XML"},
                ))

    for t in grupo.transacoes:
        # ── YC05-10 — meio de pagamento fora do subset ──────────────────────
        # A INVALIDADE é determinada pelo artefato. O cStat NÃO é: dois
        # artefatos oficiais divergem, e escolher um seria inventar
        # precedência. Incerteza sobre o código de rejeição não é incerteza
        # sobre a invalidez.
        if t.tp_meio_pgto:
            admitido = payment_methods.allowed_in_payment_linkage(t.tp_meio_pgto)
            if admitido is not True:
                k = payment_methods.conflito_cstat()
                achados.append(AchadoYC(
                    regra="YC05-10", natureza=NATUREZA_CONTEUDO,
                    cstat_esperado=CSTAT_UNDETERMINED, n_pag=t.n_pag,
                    detalhe=(
                        f"Meio de pagamento {t.tp_meio_pgto} fora do subset permitido para "
                        "vinculação. A documentação oficial diverge quanto ao cStat esperado "
                        "(1273 na NT 2026.006 e 1003 no IT 2026.001)."
                    ),
                    determinante_no_ambiente=det,
                    evidencia={
                        "invalidade": "DETERMINADA",
                        "na_tabela_nacional": admitido is not None,
                        "subset_admitido": sorted(payment_methods.codigos_admitidos_na_vinculacao()),
                        "nt_2026_006_v100": k["nt_2026_006_v100"]["cstat"],
                        "it_2026_001_v101": k["it_2026_001_v101"]["cstat"],
                        "conflict_status": k["conflict_status"],
                    },
                ))

        # ── YC06-10 — CNPJ do recebedor documentalmente inválido ───────────
        # LIMITE DECLARADO: checagem de FORMATO (contrato de
        # `is_valid_cnpj_format`, que já cobre CNPJ alfanumérico). O dígito
        # verificador do CNPJ alfanumérico não é conferido: o algoritmo não
        # está canonizado neste repo, e inventá-lo produziria falso positivo
        # nacional. Erra para o lado de não acusar.
        if t.cnpj_receb is not None and not is_valid_cnpj_format(t.cnpj_receb):
            achados.append(AchadoYC(
                regra="YC06-10", natureza=NATUREZA_CONTEUDO, cstat_esperado=1274,
                n_pag=t.n_pag,
                detalhe=f"CNPJ do recebedor do pagamento inválido: {t.cnpj_receb!r}",
                determinante_no_ambiente=det,
                evidencia={"campo": "CNPJReceb", "valor": t.cnpj_receb,
                           "limite": "validação de formato; DV alfanumérico não conferido"},
            ))
    return achados
