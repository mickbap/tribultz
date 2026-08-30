/**
 * Proveniência por claim — server component.
 *
 * Enforcement ESTRUTURAL do critério que o Round C deixou parcial: um claim
 * classificado como `NAO_DETERMINADO` não pode ser apresentado como fato.
 *
 * A garantia não é convenção humana nem revisão de PR. É o único caminho de
 * renderização de proveniência do blog, e ele **ramifica na classificação**:
 * cada natureza tem rótulo próprio e visível, e `NAO_DETERMINADO` recebe
 * tratamento explicitamente distinto de `FATO_NORMATIVO`. Não existe caminho
 * neste componente que renderize uma classificação sob o rótulo de outra.
 *
 * `MARCADOR_NAO_DETERMINADO` é exportado de propósito: o guard de sabotagem
 * verifica a saída renderizada contra ele, não contra o código-fonte.
 */
import type { ClaimProvenance, ClaimClassification } from "@/lib/blog";

export const MARCADOR_NAO_DETERMINADO = "Não determinado pela fonte oficial";

const ROTULO: Record<ClaimClassification, string> = {
  FATO_NORMATIVO: "Fato normativo",
  INTERPRETACAO_SEGURA: "Interpretação segura",
  NAO_DETERMINADO: MARCADOR_NAO_DETERMINADO,
};

const NOTA: Record<ClaimClassification, string> = {
  FATO_NORMATIVO: "Afirmação que consta no artefato oficial citado.",
  INTERPRETACAO_SEGURA:
    "Leitura conservadora feita por nós a partir do artefato — não é texto de norma.",
  NAO_DETERMINADO:
    "O artefato oficial não determina este ponto. O que segue não é afirmação nossa; é registro de que a fonte não decide a questão.",
};

export function ProvenienciaClaims({
  items,
  title = "Proveniência das afirmações",
}: {
  items: ClaimProvenance[];
  title?: string;
}) {
  if (!items?.length) return null;
  return (
    <section aria-labelledby="proveniencia-claims" className="mt-10">
      <h2 id="proveniencia-claims">{title}</h2>
      <ul>
        {items.map((c, i) => (
          <li key={i} data-classification={c.claim_classification}>
            <p>
              <strong>{ROTULO[c.claim_classification]}</strong> — {c.claim_scope}
            </p>
            <p>
              <small>{NOTA[c.claim_classification]}</small>
            </p>
            <p>
              <small>
                {c.artifact}
                {c.artifact_version ? ` v${c.artifact_version}` : ""}
                {c.rule_item ? ` · ${c.rule_item}` : ""} ·{" "}
                <a href={c.source_url} rel="nofollow noopener" target="_blank">
                  {c.source_authority}
                </a>{" "}
                · conferido em <time dateTime={c.verified_at}>{c.verified_at}</time>
              </small>
            </p>
            {c.temporal_applicability && (
              <p>
                <small>Aplicabilidade temporal: {c.temporal_applicability}</small>
              </p>
            )}
            {c.conflict_note && (
              <p>
                <small>Conflito registrado: {c.conflict_note}</small>
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
