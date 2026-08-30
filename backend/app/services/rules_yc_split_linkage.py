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


def _achado_meio_pagamento(regra: str, t: TransacaoVinculada, det: bool) -> Optional[AchadoYC]:
    """YC05-10 e P26-10 são a MESMA condição em contextos diferentes.

    A invalidade é DETERMINADA: o código está fora do subset e afirmamos isso.
    O cStat é UNDETERMINED enquanto dois artefatos oficiais divergirem —
    escolher 1273 ou 1003 seria inventar precedência documental. Incerteza
    sobre o código de rejeição não é incerteza sobre a invalidez.
    """
    if not t.tp_meio_pgto:
        return None
    admitido = payment_methods.allowed_in_payment_linkage(t.tp_meio_pgto)
    if admitido is True:
        return None
    k = payment_methods.conflito_cstat()
    return AchadoYC(
        regra=regra, natureza=NATUREZA_CONTEUDO,
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
    )


def _achado_cnpj_receb(regra: str, t: TransacaoVinculada, det: bool) -> Optional[AchadoYC]:
    """YC06-10 e P27-10 — mesma checagem, mesmo limite declarado.

    ESCOPO: FORMATO. O dígito verificador do CNPJ alfanumérico não é conferido —
    o algoritmo não está canonizado neste repo, e inventá-lo produziria falso
    positivo nacional. Formato válido NÃO é promovido a "CNPJ integralmente
    válido"; a evidência carrega o limite.
    """
    if t.cnpj_receb is None or is_valid_cnpj_format(t.cnpj_receb):
        return None
    return AchadoYC(
        regra=regra, natureza=NATUREZA_CONTEUDO, cstat_esperado=1274, n_pag=t.n_pag,
        detalhe=f"CNPJ do recebedor do pagamento inválido: {t.cnpj_receb!r}",
        determinante_no_ambiente=det,
        evidencia={"campo": "CNPJReceb", "valor": t.cnpj_receb,
                   "escopo_validacao": "FORMAT_ONLY",
                   "limite": "validação de formato; DV alfanumérico não conferido"},
    )


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
        achado_meio = _achado_meio_pagamento("YC05-10", t, det)
        if achado_meio:
            achados.append(achado_meio)

        # ── YC06-10 — CNPJ do recebedor documentalmente inválido ───────────
        # LIMITE DECLARADO: checagem de FORMATO (contrato de
        # `is_valid_cnpj_format`, que já cobre CNPJ alfanumérico). O dígito
        # verificador do CNPJ alfanumérico não é conferido: o algoritmo não
        # está canonizado neste repo, e inventá-lo produziria falso positivo
        # nacional. Erra para o lado de não acusar.
        achado_cnpj = _achado_cnpj_receb("YC06-10", t, det)
        if achado_cnpj:
            achados.append(achado_cnpj)
    return achados


# ─────────────────────────────────────────────────────────────────────────────
# Evento 110300 — Vinculação da Transação de Pagamento no DF-e (NT 2026.006 §4)
# ─────────────────────────────────────────────────────────────────────────────
# Função (texto oficial): "gerado pelo emitente do DF-e sempre que se DESEJAR
# vincular uma ou mais transações financeiras a um documento fiscal previamente
# autorizado. Obs.: É possível que a transação financeira vinculada esteja em
# situação iniciada, ainda PENDENTE DE PAGAMENTO E/OU LIQUIDAÇÃO".
#
# Registrar o evento não é pagar, não é liquidar, e "sempre que se desejar" não
# é obrigação. O evento carrega identificação de transação; nada mais.
#
# ESCOPO DESTE MÓDULO: validar documento/evento. Não há transmissão, registro na
# SEFAZ nem cancelamento 110001 operacional — não estamos construindo cliente
# SEFAZ. Cardinalidade: no DF-e, gPgto é 1-99; no evento é 1-1. Vincular várias
# transações após a autorização exige vários eventos.

TP_AUTOR_EMPRESA_EMITENTE = "1"
DESC_EVENTO_110300 = "Vinculação Pagamento"
COD_EVENTO_110300 = "110300"


@dataclass(frozen=True)
class EventoVinculacao:
    """Evento 110300. Só os campos do leiaute P17–P28.

    Não há — e não pode haver — campo de valor, estado de pagamento, data de
    liquidação ou rateio: o leiaute não os define.
    """

    presente: bool
    desc_evento: Optional[str] = None
    c_orgao_autor: Optional[str] = None
    tp_autor: Optional[str] = None
    ver_aplic: Optional[str] = None
    #: Protocolo do DF-e JÁ AUTORIZADO ao qual a transação é vinculada.
    n_prot: Optional[str] = None
    transacao: Optional[TransacaoVinculada] = None


def parse_evento_110300(xml: str) -> EventoVinculacao:
    """Extrai ``detEvento`` do evento 110300. Ausência é ausência, não erro."""
    m = re.search(r"<detEvento(?=[\s>/])[^>]*>([\s\S]*?)</detEvento>", xml, re.I)
    if not m:
        return EventoVinculacao(presente=False)
    corpo = m.group(1)

    def _tag(nome: str, onde: str = corpo) -> Optional[str]:
        t = re.search(rf"<{nome}(?=[\s>/])[^>]*>([\s\S]*?)</{nome}>", onde, re.I)
        return t.group(1).strip() if t else None

    # Só reconhecemos como 110300 pelo descEvento; outro evento não é nosso.
    desc = _tag("descEvento")
    if desc and desc.strip().lower() != DESC_EVENTO_110300.lower():
        return EventoVinculacao(presente=False)

    transacao = None
    g = re.search(r"<gPgto(?=[\s>/])([^>]*)>([\s\S]*?)</gPgto>", corpo, re.I)
    if g:
        attrs, bloco = g.group(1), g.group(2)
        a = re.search(_ATTR.format(attr="idTransacao"), attrs, re.I)
        transacao = TransacaoVinculada(
            # No evento não existe nPag — só uma transação por evento.
            n_pag=None,
            id_transacao=(a.group(1).strip() if a else _tag("idTransacao", bloco)),
            tp_meio_pgto=_tag("tpMeioPgto", bloco),
            cnpj_receb=_tag("CNPJReceb", bloco),
            cnpj_base_psp=_tag("CNPJBasePSP", bloco),
        )
    return EventoVinculacao(
        presente=True, desc_evento=desc, c_orgao_autor=_tag("cOrgaoAutor"),
        tp_autor=_tag("tpAutor"), ver_aplic=_tag("verAplic"),
        n_prot=_tag("nProt"), transacao=transacao,
    )


def avaliar_evento(
    evento: EventoVinculacao,
    *,
    emissao: Optional[dt.date] = None,
    ambiente: Optional[str] = None,
) -> list[AchadoYC]:
    """Avalia P21-10, P26-10 e P27-10. Evento ausente ⇒ lista vazia."""
    if not evento.presente:
        return []

    det = _determinante(emissao, ambiente)
    achados: list[AchadoYC] = []

    # ── P21-10 — "Tipo do Autor difere de 1=Empresa Emitente" → 466 ─────────
    # tpAutor identifica o autor DO EVENTO no leiaute. Não é declaração de
    # obrigação jurídica de ninguém: só diz quem, tecnicamente, pode gerá-lo.
    if evento.tp_autor is not None and evento.tp_autor.strip() != TP_AUTOR_EMPRESA_EMITENTE:
        achados.append(AchadoYC(
            regra="P21-10", natureza=NATUREZA_CONTEUDO, cstat_esperado=466,
            n_pag=None,
            detalhe=(
                f"Evento 110300 com tpAutor={evento.tp_autor!r}; o leiaute admite "
                "somente 1=Empresa Emitente."
            ),
            determinante_no_ambiente=det,
            evidencia={"campo": "tpAutor", "valor": evento.tp_autor,
                       "admitido": TP_AUTOR_EMPRESA_EMITENTE,
                       "semantica": "identificação do autor do evento; não é obrigação jurídica"},
        ))

    if evento.transacao is not None:
        for achado in (_achado_meio_pagamento("P26-10", evento.transacao, det),
                       _achado_cnpj_receb("P27-10", evento.transacao, det)):
            if achado:
                achados.append(achado)
    return achados
