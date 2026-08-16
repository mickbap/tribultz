import type { Metadata } from "next";
import { LegalPageLayout } from "@/components/legal/LegalPageLayout";

export const metadata: Metadata = {
  alternates: { canonical: "/refund-policy" },
  title: "Política de Reembolso",
  description: "Direito de arrependimento de 7 dias e regras de cancelamento das assinaturas Tribultz.",
};

export default function RefundPolicyPage() {
  return (
    <LegalPageLayout
      title="Política de Reembolso"
      updatedAt="28 de julho de 2026"
      summary="Como funciona o reembolso nos primeiros 7 dias e o que acontece quando você cancela depois desse prazo."
    >
      <section>
        <h2 className="text-lg font-semibold text-slate-900">1. Direito de arrependimento (7 dias)</h2>
        <p>
          Como a contratação da Tribultz acontece à distância (fora do estabelecimento comercial),
          você tem direito de desistir da assinatura em até <strong>7 dias corridos</strong> a partir
          da data em que ela começou — sem precisar justificar o motivo. Esse direito é garantido pelo
          artigo 49 do Código de Defesa do Consumidor (Lei 8.078/1990):
        </p>
        <blockquote className="mt-3 border-l-4 border-slate-200 pl-4 italic text-slate-600">
          &quot;O consumidor pode desistir do contrato, no prazo de 7 dias a contar de sua assinatura
          ou do ato de recebimento do produto ou serviço, sempre que a contratação de fornecimento de
          produtos e serviços ocorrer fora do estabelecimento comercial [...]. Se o consumidor
          exercitar o direito de arrependimento previsto neste artigo, os valores eventualmente pagos,
          a qualquer título, durante o prazo de reflexão, serão devolvidos, de imediato, monetariamente
          atualizados.&quot;
        </blockquote>
        <p className="mt-3">
          Na prática: cancele pelo painel (Configurações → Assinatura → Cancelar) em até 7 dias da sua
          primeira assinatura, e devolvemos <strong>o valor integral pago</strong>, sem retenção. O
          prazo conta a partir da sua primeira assinatura — trocar de plano dentro desses 7 dias não
          reinicia a contagem.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">2. Prazo de processamento do reembolso</h2>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>
            <strong>PIX:</strong> reembolso processado diretamente pelo nosso provedor de pagamentos.
          </li>
          <li>
            <strong>Cartão de crédito:</strong> o estorno é solicitado imediatamente à operadora do
            cartão, mas pode levar até 10 dias úteis para aparecer na fatura — esse prazo é do banco
            emissor do cartão, não da Tribultz.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">3. Cancelamento após os 7 dias</h2>
        <p>
          Depois do prazo de arrependimento, a assinatura Tribultz é <strong>sem fidelidade</strong>:
          cancele quando quiser, direto pelo painel, sem multa. Nesse caso não há reembolso do valor já
          pago no período corrente — você mantém acesso completo ao plano até o fim da data em que a
          próxima cobrança aconteceria, e a cobrança não se repete depois disso.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">4. Como pedir o reembolso</h2>
        <p>
          O cancelamento é feito pelo próprio painel (Configurações → Assinatura → Cancelar) — o
          sistema identifica automaticamente se você ainda está dentro do prazo de 7 dias e processa o
          reembolso sem necessidade de abrir chamado. Em caso de dúvida, fale com{" "}
          <strong>contato@tribultz.com.br</strong>.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900">5. O que não está incluído</h2>
        <p>
          Esta política cobre o valor da assinatura em si. Créditos de API já consumidos (chamadas
          efetivamente processadas antes do cancelamento) não são estornados isoladamente — o
          reembolso incide sobre o valor pago pela assinatura.
        </p>
      </section>
    </LegalPageLayout>
  );
}
