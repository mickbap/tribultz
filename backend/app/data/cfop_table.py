"""Catálogo de CFOP versionado (#688) — Tabela oficial do Portal Nacional da NF-e.

Substitui a dependência conceitual de uma allowlist literal tratada como se
fosse catálogo. O artefato corrente é a **Tabela de CFOP** publicada em
04/09/2026, vinculada ao **IT 2023.002 v2.10**. Essa versão apenas acrescenta
``titulo`` e ``descricao`` como metadados explicativos; os 619 códigos e todas
as 11 propriedades operacionais permanecem idênticos à v2.00.

Representamos o DOMÍNIO OFICIAL COMPLETO (619 códigos, 11 propriedades cada),
não o subconjunto permitido. Guardar só os permitidos transformaria a tabela
oficial em nova allowlist artesanal — o defeito que a #688 existe para corrigir.

────────────────────────────────────────────────────────────────────────────
SEMÂNTICA ESTRITA DE ``indExcIBSCBS`` — texto oficial, IT 2023.002 v2.00 §03:

    "Indica se o CFOP é permitido na NF-e (modelo 55) emitida por contribuinte
     exclusivo do IBS/CBS."
        0 – CFOP não permitido ao contribuinte exclusivo do IBS/CBS
        1 – CFOP permitido ao contribuinte exclusivo do IBS/CBS

É PROIBIDO derivar deste indicador: incidência, não incidência, isenção,
imunidade, crédito, débito ou conformidade tributária global. Ele responde uma
única pergunta — admissibilidade do código naquele contexto de emissão — e
nada mais. ``indExcIBSCBS=1`` não diz que a operação é tributada, nem que está
correta; diz que o código não é recusado por esta validação.

E há um limite temporal explícito no próprio artefato: até a implantação em
produção (03/11/2026) a coluna tem **caráter informativo, não produzindo efeito
de rejeição**. Homologação a partir de 01/09/2026.
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import pathlib
from typing import Optional

from app.data.provenance import ArtifactProvenance

_ARQUIVO = pathlib.Path(__file__).with_name("cfop_table.json")

#: Datas declaradas pelo IT 2023.002 v2.00 para a coluna indExcIBSCBS.
HOMOLOGACAO = dt.date(2026, 9, 1)
PRODUCAO = dt.date(2026, 11, 3)


@functools.lru_cache(maxsize=1)
def _doc() -> dict:
    return json.loads(_ARQUIVO.read_text(encoding="utf-8"))


def provenance() -> ArtifactProvenance:
    """Identidade auditável do artefato (#682).

    ``versao=None``: a Tabela de CFOP não declara versão própria — é publicada
    por data. Quem carrega versão é o IT associado, em ``instituido_por``.
    """
    m = _doc()["meta"]
    return ArtifactProvenance(
        artefato=m["artefato"],
        versao=m["versao"],
        fonte=m["fonte"],
        source_url=m["source_url"],
        observado_em=dt.date.fromisoformat(m["observado_em"]),
        fingerprint=m["fingerprint"],
        notas=m["conflito_contagem"]["nota"],
    )


def instituido_por() -> ArtifactProvenance:
    """Identidade do IT associado à publicação corrente da tabela."""
    i = _doc()["meta"]["instituido_por"]
    m = _doc()["meta"]
    return ArtifactProvenance(
        artefato=i["artefato"],
        versao=i["versao"],
        fonte="Portal Nacional da NF-e — Informes Técnicos",
        source_url=i["source_url"],
        observado_em=dt.date.fromisoformat(m["observado_em"]),
        fingerprint=i["fingerprint"],
    )


def historico() -> tuple[dict, ...]:
    """Snapshots anteriores preservados com origem, fingerprint e vigência."""
    return tuple(_doc()["meta"].get("historico", ()))


def aplicacao_v210() -> dict:
    """Aplicação documental da v2.10, sem converter “não aplicável” em data."""
    return dict(_doc()["meta"]["aplicacao_v210"])


def conflito_contagem() -> dict:
    """Conflito ABERTO entre dois artefatos oficiais, preservado como dado.

    O IT 2023.002 v2.00 (06/08/2026, §03) diz "(84 códigos)". As tabelas de
    25/08/2026 e 04/09/2026 trazem os mesmos 72. ``conflict_status`` segue
    ``UNRESOLVED`` porque a v2.10 não declara retificação da contagem textual.

    O conflito NÃO condiciona comportamento. O Round Fiscal 27/08-D canonizou a
    Tabela de 25/08 como domínio operacional; o lookup responde pelo valor
    individual publicado de cada CFOP, e o determinismo da I08-191 depende de
    condições documentais + indExcIBSCBS=0 + SVRS comprovada + vigência — nunca
    de resolver esta divergência. Ver ``efeito_operacional``.

    O que NÃO foi feito, de propósito: gerar os 12 códigos que fechariam 84,
    alterar o XLSX, ou afirmar que 84 foi oficialmente retificado para 72. O
    domínio operacional é a Tabela, e o lookup por CFOP usa o valor individual
    efetivamente publicado — não uma contagem agregada.
    """
    return _doc()["meta"]["conflito_contagem"]


def contagem() -> dict:
    """``{total, indExcIBSCBS_0, indExcIBSCBS_1}`` observados na Tabela."""
    return _doc()["meta"]["contagem"]


def all_cfops() -> frozenset[str]:
    """Domínio oficial completo — todos os códigos da tabela, não só os permitidos."""
    return frozenset(_doc()["cfop"])


def get(cfop: str) -> Optional[dict]:
    """Registro completo, inclusive metadados explicativos, ou ``None``.

    ``titulo`` e ``descricao`` reproduzem texto convenial para apoio à leitura.
    Não são interpretados como regra, indicador ou efeito de rejeição.
    """
    return _doc()["cfop"].get(str(cfop).strip())


def ind_exc_ibscbs(cfop: str) -> Optional[str]:
    """Valor BRUTO da coluna (``"0"``/``"1"``), ou ``None`` se o CFOP é desconhecido.

    Devolve o dado como está no artefato, sem traduzir para booleano: ``None``
    (CFOP fora do domínio oficial) é resposta diferente de ``"0"`` (CFOP existe e
    não é permitido), e colapsar as duas em ``False`` apagaria a distinção.
    """
    reg = get(cfop)
    return reg["indExcIBSCBS"] if reg else None


def permitido_contribuinte_exclusivo_ibscbs(cfop: str) -> Optional[bool]:
    """``True``/``False`` de ADMISSIBILIDADE; ``None`` se o CFOP não existe na tabela.

    Estritamente: "este CFOP é aceito numa NF-e modelo 55 emitida por
    contribuinte exclusivo do IBS/CBS?". Nada além disso — ver o cabeçalho do
    módulo para o que é proibido inferir daqui.
    """
    v = ind_exc_ibscbs(cfop)
    return None if v is None else v == "1"


def cfops_permitidos_contribuinte_exclusivo() -> frozenset[str]:
    """Subconjunto com ``indExcIBSCBS=1``, DERIVADO do domínio completo.

    Existe para relatório e teste. Nunca deve ser persistido como lista literal:
    a fonte é a tabela, e é ela que muda.
    """
    return frozenset(c for c in all_cfops() if ind_exc_ibscbs(c) == "1")


def efeito_de_rejeicao_em(quando: dt.date) -> bool:
    """A coluna já produz rejeição nessa data?

    Até a produção (03/11/2026) o próprio artefato declara caráter informativo.
    Tratar como rejeição antes disso seria endurecer regra além do que a fonte
    oficial autoriza.
    """
    return quando >= PRODUCAO
