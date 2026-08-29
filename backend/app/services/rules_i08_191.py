"""RV I08-191 — CFOP restrito ao contribuinte exclusivo do IBS/CBS (#615).

Fonte normativa: **NT 2026.007 v1.00**, adquirida do Portal Nacional da NF-e.
Texto oficial da regra:

    I08-191 | mod. 55 | Se não informada a IE do emitente (tag: emit/IE):
      - Consultar tabela de CFOP permitidos para emitentes exclusivos do
        IBS/CBS (coluna: indExcIBSCBS) publicada no Portal Nacional da NF-e.
      Exceção 1: não se aplica no caso de finalidade da NF-e igual a devolução
        (tag:finNFe=4).
      Exceção 2: não se aplica no caso Tipo de Nota de Crédito igual a
        "03=Retorno por Recusa Total na Entrega ou Por Não Localização do
        Destinatário na Tentativa de Entrega" (tag: tpNFCredito=03).
      Observação: Regra de validação exclusiva da SVRS.
    Msg 159 — "Operação não permitida para contribuinte exclusivo do IBS/CBS."

DUAS PERGUNTAS, NUNCA COLAPSADAS
────────────────────────────────
A) O XML satisfaz as condições DOCUMENTAIS da regra e o CFOP tem
   ``indExcIBSCBS=0``?  → decidível só com o documento e a tabela oficial.

B) Há evidência de que a regra é APLICÁVEL a este documento, isto é, de que o
   autorizador é a SVRS?  → NÃO é decidível a partir do XML.

Colapsar A e B produziria rejeição em UF onde a regra não vale. Por isso B
entra como ``autorizador`` explícito, fornecido por quem sabe. Nunca derivado.

O QUE ESTE MÓDULO NÃO FAZ, DE PROPÓSITO
────────────────────────────────────────
- Não mapeia ``cUF``/UF → autorizador. Não há tabela canonizada disso no
  produto, e inventá-la por memória operacional é exatamente o que produz o
  falso positivo. **Gap registrado**: adquirir esse mapeamento como artefato
  versionado é trabalho futuro, com proveniência própria.
- Não classifica o contribuinte. Ausência de ``emit/IE`` é CONDIÇÃO DOCUMENTAL
  do gatilho da RV, não conclusão de que o emitente é contribuinte exclusivo do
  IBS/CBS. A qualificação de perfil vive em outras RVs da mesma NT
  (12C02-10/20, 12C21-20, 1P10-30/32, 5AF*, 5BG*), que consultam LCC-RFB e CCC
  — cadastros que não temos e que não serão simulados.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

from app.data import cfop_table

#: Valor de ``autorizador`` que comprova a aplicabilidade da regra.
AUTORIZADOR_SVRS = "SVRS"

#: Exceções documentais, texto oficial da RV.
EXCECAO_DEVOLUCAO = "finNFe=4"
EXCECAO_RETORNO_RECUSA = "tpNFCredito=03"

# Resultados possíveis.
SEM_ACHADO = "SEM_ACHADO"
REJEICAO_159 = "REJEICAO_159"
POSSIVEL_REJEICAO_159 = "POSSIVEL_REJEICAO_159"

# Estados de aplicabilidade (pergunta B).
SVRS_COMPROVADA = "SVRS_COMPROVADA"
SVRS_NAO_DETERMINADA = "APLICABILIDADE_SVRS_NAO_DETERMINADA"


@dataclass(frozen=True)
class I08191Entrada:
    """Só campos lidos do próprio documento — mais ``autorizador``, que vem de fora."""

    modelo: str
    emit_ie: Optional[str]
    cfops: list[str] = field(default_factory=list)
    fin_nfe: Optional[str] = None
    tp_nf_credito: Optional[str] = None
    emissao: Optional[dt.date] = None
    #: ``"SVRS"`` quando COMPROVADO por quem sabe. ``None`` = não determinado.
    #: Jamais preenchido por dedução a partir de cUF, chave de acesso ou UF.
    autorizador: Optional[str] = None


@dataclass(frozen=True)
class I08191Resultado:
    resultado: str
    aplicabilidade: str
    severidade: Optional[str]
    condicoes_documentais: bool
    cfop_nao_permitido: Optional[str]
    excecao_aplicada: Optional[str]
    produz_rejeicao_na_data: bool
    motivo: str


def _ie_ausente(ie: Optional[str]) -> bool:
    """A RV dispara com ``emit/IE`` não informada. Zeros contam como ausente
    pela C17-10 ("IE Emitente com zeros ou nulo")."""
    if ie is None:
        return True
    limpo = ie.strip()
    return limpo == "" or set(limpo) == {"0"}


def avaliar(entrada: I08191Entrada) -> I08191Resultado:
    """Avalia A e B separadamente e devolve o resultado sem colapsá-las."""
    aplic = SVRS_COMPROVADA if entrada.autorizador == AUTORIZADOR_SVRS else SVRS_NAO_DETERMINADA

    def _sem(motivo: str, *, docs: bool = False, cfop: Optional[str] = None,
             excecao: Optional[str] = None) -> I08191Resultado:
        return I08191Resultado(
            resultado=SEM_ACHADO, aplicabilidade=aplic, severidade=None,
            condicoes_documentais=docs, cfop_nao_permitido=cfop,
            excecao_aplicada=excecao, produz_rejeicao_na_data=False, motivo=motivo,
        )

    # ── A) condições documentais ───────────────────────────────────────────
    if entrada.modelo.strip() != "55":
        return _sem("RV é exclusiva do modelo 55")
    if not _ie_ausente(entrada.emit_ie):
        return _sem("emit/IE informada — gatilho documental da RV não ocorre")

    # Exceções ANTES da consulta à tabela: a RV não se aplica, e checar CFOP
    # depois disso seria produzir achado onde a norma diz que não há regra.
    if (entrada.fin_nfe or "").strip() == "4":
        return _sem("Exceção 1 — devolução", docs=True, excecao=EXCECAO_DEVOLUCAO)
    if (entrada.tp_nf_credito or "").strip().zfill(2) == "03":
        return _sem("Exceção 2 — retorno por recusa total/não localização",
                    docs=True, excecao=EXCECAO_RETORNO_RECUSA)

    nao_permitido = next(
        (c for c in (x.strip() for x in entrada.cfops)
         if cfop_table.permitido_contribuinte_exclusivo_ibscbs(c) is False),
        None,
    )
    if nao_permitido is None:
        return _sem("nenhum CFOP do documento tem indExcIBSCBS=0", docs=True)

    # CFOP fora do domínio oficial (`None`) NÃO entra aqui: desconhecido não é
    # "não permitido". Quem trata código inexistente é outra regra.

    vigente = cfop_table.efeito_de_rejeicao_em(entrada.emissao) if entrada.emissao else False

    # ── B) aplicabilidade ──────────────────────────────────────────────────
    if aplic == SVRS_COMPROVADA and vigente:
        return I08191Resultado(
            resultado=REJEICAO_159, aplicabilidade=aplic, severidade="FATAL",
            condicoes_documentais=True, cfop_nao_permitido=nao_permitido,
            excecao_aplicada=None, produz_rejeicao_na_data=True,
            motivo="condições documentais satisfeitas, CFOP com indExcIBSCBS=0, "
                   "autorizador SVRS comprovado e coluna já em produção",
        )
    if aplic == SVRS_COMPROVADA:
        return I08191Resultado(
            resultado=POSSIVEL_REJEICAO_159, aplicabilidade=aplic, severidade="WARNING",
            condicoes_documentais=True, cfop_nao_permitido=nao_permitido,
            excecao_aplicada=None, produz_rejeicao_na_data=False,
            motivo="autorizador SVRS comprovado, mas até 03/11/2026 a coluna "
                   "indExcIBSCBS tem caráter informativo e não produz rejeição",
        )
    return I08191Resultado(
        resultado=POSSIVEL_REJEICAO_159, aplicabilidade=SVRS_NAO_DETERMINADA,
        severidade="WARNING", condicoes_documentais=True,
        cfop_nao_permitido=nao_permitido, excecao_aplicada=None,
        produz_rejeicao_na_data=vigente,
        motivo="condições documentais satisfeitas e CFOP com indExcIBSCBS=0, "
               "mas a RV é exclusiva da SVRS e o autorizador não foi determinado",
    )


def mensagem(r: I08191Resultado) -> str:
    """Texto funcional do achado, na fronteira semântica autorizada."""
    if r.resultado == REJEICAO_159:
        return (
            f"CFOP {r.cfop_nao_permitido} não é permitido ao contribuinte exclusivo do "
            "IBS/CBS (indExcIBSCBS=0, Tabela de CFOP oficial). SEFAZ: Rejeição 159 "
            "(RV I08-191, NT 2026.007 v1.00)."
        )
    return (
        "A operação satisfaz as condições documentais da RV I08-191 e utiliza CFOP "
        f"{r.cfop_nao_permitido}, não permitido pela tabela corrente (indExcIBSCBS=0). "
        "A regra é exclusiva da SVRS; o autorizador aplicável não foi determinado."
    )
