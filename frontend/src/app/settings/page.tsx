"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Toast } from "@/components/common/Toast";
import { getTenantId, getToken } from "@/lib/storage";
import { API_BASE } from "@/lib/api";

type ManifestacaoEleicao = {
  id: string;
  manifestada_em: string;
  eficacia_inicio: string;
  eficacia_fim: string;
  fonte: string;
  evidencia_ref: string;
  cancelada_em: string | null;
  cancelamento_evidencia_ref: string | null;
};

type EstadoEleicao = {
  eleicao: string;
  modalidade_vigente: string;
  opcao_apresentada: boolean;
  opcao_eficaz: boolean;
  historico: ManifestacaoEleicao[];
};

export default function SettingsPage() {
  const [tenant, setTenant] = useState("");
  const [tokenDisplay, setTokenDisplay] = useState("");
  const [toast, setToast] = useState<{ tone: "error" | "success" | "info"; msg: string } | null>(null);
  const [pedagogicalMode, setPedagogicalMode] = useState<boolean | null>(null);
  const [pedagogicalLoading, setPedagogicalLoading] = useState(false);
  // Troca de senha do próprio usuário. Contas provisionadas pelo Command Center
  // (Founding Partners) nascem com senha definida pelo Owner, e até agora o
  // titular só conseguia trocá-la saindo e usando "Esqueci minha senha".
  const [senhaAtual, setSenhaAtual] = useState("");
  const [senhaNova, setSenhaNova] = useState("");
  const [senhaConfirma, setSenhaConfirma] = useState("");
  const [senhaLoading, setSenhaLoading] = useState(false);
  const [senhaErro, setSenhaErro] = useState("");
  const [eleicaoCnpj, setEleicaoCnpj] = useState("");
  const [manifestadaEm, setManifestadaEm] = useState("");
  const [evidenciaRef, setEvidenciaRef] = useState("");
  const [canceladaEm, setCanceladaEm] = useState("");
  const [cancelamentoEvidencia, setCancelamentoEvidencia] = useState("");
  const [estadoEleicao, setEstadoEleicao] = useState<EstadoEleicao | null>(null);
  const [eleicaoLoading, setEleicaoLoading] = useState(false);

  function cnpjNormalizado() {
    return eleicaoCnpj.replace(/[^0-9A-Za-z]/g, "").toUpperCase();
  }

  async function lerRespostaEleicao(res: Response): Promise<EstadoEleicao> {
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail ?? "Não foi possível atualizar a eleição.");
    return body as EstadoEleicao;
  }

  async function consultarEleicao() {
    const cnpj = cnpjNormalizado();
    if (cnpj.length !== 14) {
      setToast({ tone: "error", msg: "Informe um CNPJ com 14 caracteres." });
      return;
    }
    setEleicaoLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/auth/settings/tenant/eleicao-ibs-cbs?cnpj=${encodeURIComponent(cnpj)}`,
        { headers: { Authorization: `Bearer ${getToken()}` } },
      );
      setEstadoEleicao(await lerRespostaEleicao(res));
    } catch (error) {
      setToast({ tone: "error", msg: error instanceof Error ? error.message : "Erro de conexão." });
    } finally {
      setEleicaoLoading(false);
    }
  }

  async function registrarEleicao(e: React.FormEvent) {
    e.preventDefault();
    setEleicaoLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/settings/tenant/eleicao-ibs-cbs/opcao`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          cnpj: cnpjNormalizado(),
          manifestada_em: manifestadaEm,
          evidencia_ref: evidenciaRef,
        }),
      });
      setEstadoEleicao(await lerRespostaEleicao(res));
      setEvidenciaRef("");
      setToast({ tone: "success", msg: "Opção registrada com a evidência oficial." });
    } catch (error) {
      setToast({ tone: "error", msg: error instanceof Error ? error.message : "Erro de conexão." });
    } finally {
      setEleicaoLoading(false);
    }
  }

  async function cancelarEleicao(id: string) {
    if (!canceladaEm || !cancelamentoEvidencia.trim()) {
      setToast({ tone: "error", msg: "Informe data e evidência oficial do cancelamento." });
      return;
    }
    setEleicaoLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/auth/settings/tenant/eleicao-ibs-cbs/${id}/cancelamento`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
          body: JSON.stringify({
            cancelada_em: canceladaEm,
            evidencia_ref: cancelamentoEvidencia,
          }),
        },
      );
      setEstadoEleicao(await lerRespostaEleicao(res));
      setCancelamentoEvidencia("");
      setToast({ tone: "success", msg: "Cancelamento registrado sem apagar o histórico." });
    } catch (error) {
      setToast({ tone: "error", msg: error instanceof Error ? error.message : "Erro de conexão." });
    } finally {
      setEleicaoLoading(false);
    }
  }

  async function trocarSenha(e: React.FormEvent) {
    e.preventDefault();
    setSenhaErro("");

    if (senhaNova.length < 8) {
      setSenhaErro("A nova senha deve ter no mínimo 8 caracteres.");
      return;
    }
    if (senhaNova !== senhaConfirma) {
      setSenhaErro("A confirmação não confere com a nova senha.");
      return;
    }

    setSenhaLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/change-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ current_password: senhaAtual, new_password: senhaNova }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setSenhaErro(d.detail ?? "Não foi possível alterar a senha.");
        return;
      }
      setSenhaAtual("");
      setSenhaNova("");
      setSenhaConfirma("");
      setToast({ tone: "success", msg: "Senha alterada." });
    } catch {
      setSenhaErro("Falha de conexão. Tente novamente.");
    } finally {
      setSenhaLoading(false);
    }
  }

  useEffect(() => {
    setTenant(getTenantId());
    setTokenDisplay(getToken() ? "••••••••" : "(não autenticado)");
    // Carregar configuração do modo pedagógico
    const tok = getToken();
    if (tok) {
      fetch(`${API_BASE}/api/v1/auth/settings/tenant`, {
        headers: { Authorization: `Bearer ${tok}` },
      })
        .then((r) => r.json())
        .then((d) => setPedagogicalMode(d.pedagogical_mode_2026 ?? true))
        .catch(() => setPedagogicalMode(true));
    }
  }, []);

  async function togglePedagogicalMode() {
    const tok = getToken();
    if (!tok || pedagogicalMode === null) return;
    const next = !pedagogicalMode;
    setPedagogicalLoading(true);
    try {
      const r = await fetch(`${API_BASE}/api/v1/auth/settings/tenant`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${tok}`, "Content-Type": "application/json" },
        body: JSON.stringify({ pedagogical_mode_2026: next }),
      });
      if (r.ok) {
        setPedagogicalMode(next);
        setToast({ tone: "success", msg: `Modo Pedagógico ${next ? "ativado" : "desativado"}.` });
      } else {
        setToast({ tone: "error", msg: "Falha ao atualizar configuração." });
      }
    } catch {
      setToast({ tone: "error", msg: "Erro de conexão." });
    } finally {
      setPedagogicalLoading(false);
    }
  }

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Configurações</h1>
        <p className="text-sm text-slate-500">Informações da sessão e seus direitos de dados.</p>
      </header>

      <section className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 px-3 py-2">
          <p className="text-sm font-medium text-slate-800">Ambiente</p>
          <p className="mt-1 break-all text-xs text-slate-500">{API_BASE}</p>
        </div>

        <div className="rounded-lg border border-slate-200 px-3 py-2">
          <p className="text-sm font-medium text-slate-800">Tenant ativo</p>
          <p className="mt-1 text-xs text-slate-500 font-mono">{tenant || "—"}</p>
        </div>

        <div className="rounded-lg border border-slate-200 px-3 py-2">
          <p className="text-sm font-medium text-slate-800">Token de sessão</p>
          <p className="mt-1 text-xs text-slate-500 font-mono">{tokenDisplay}</p>
        </div>
      </section>

      {/* ── Modo Período Educativo 2026 ── */}
      <section className="rounded-xl border border-blue-200 bg-white p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Modo Período Educativo 2026
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Quando ativo, irregularidades em <strong>obrigações acessórias</strong> CBS/IBS
              (formato CST, cClassTrib, layout XML) são sinalizadas como{" "}
              <strong>Aviso</strong> em vez de bloqueio — conforme o{" "}
              <strong>art. 348, §§ 3º e 4º, da LC 214/2025</strong> (incluídos pela LC 227/2026): 60 dias
              contados da notificação para regularizar, extinguindo a penalidade.
            </p>
            <p className="mt-2 text-xs text-blue-700 font-medium">
              ⚖️ Válido durante o período pedagógico de 2026. Recomendado manter ativo.
            </p>
          </div>
          <button
            type="button"
            onClick={togglePedagogicalMode}
            disabled={pedagogicalLoading || pedagogicalMode === null}
            className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
              pedagogicalMode ? "bg-blue-600" : "bg-slate-300"
            } disabled:cursor-not-allowed disabled:opacity-60`}
            aria-label="Toggle modo pedagógico"
          >
            <span
              className={`inline-block h-6 w-6 rounded-full bg-white shadow ring-0 transition-transform duration-200 ${
                pedagogicalMode ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>
        {pedagogicalMode !== null && (
          <p className="mt-2 text-xs text-slate-400">
            Status atual: <strong>{pedagogicalMode ? "Ativo — avisos pedagógicos habilitados" : "Inativo — todos os erros são bloqueantes"}</strong>
          </p>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-slate-900">Eleição de IBS/CBS no Simples</h2>
        <p className="mt-1 text-sm text-slate-600">
          Registre aqui somente uma opção efetivamente manifestada no Portal do Simples Nacional.
          O Tribultz não presume a opção pelo CRT, pelo cadastro ou pela ausência de informação.
        </p>

        <form onSubmit={registrarEleicao} className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            CNPJ
            <input
              required
              minLength={14}
              maxLength={18}
              value={eleicaoCnpj}
              onChange={(e) => { setEleicaoCnpj(e.target.value); setEstadoEleicao(null); }}
              placeholder="00.000.000/0000-00"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Data da manifestação oficial
            <input
              required
              type="date"
              value={manifestadaEm}
              onChange={(e) => setManifestadaEm(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Protocolo, recibo ou referência do comprovante oficial
            <input
              required
              value={evidenciaRef}
              onChange={(e) => setEvidenciaRef(e.target.value)}
              placeholder="Ex.: protocolo RFB, URL ou identificação do recibo"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <div className="flex flex-wrap gap-2 md:col-span-2">
            <button
              type="button"
              onClick={consultarEleicao}
              disabled={eleicaoLoading}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
            >
              Consultar estado
            </button>
            <button
              type="submit"
              disabled={eleicaoLoading}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Registrar opção pelo regime regular
            </button>
          </div>
        </form>

        {estadoEleicao && (
          <div className="mt-4 space-y-3 border-t border-slate-200 pt-4">
            <div className="rounded-lg bg-slate-50 p-3 text-sm">
              <p><strong>Comprovação:</strong> {estadoEleicao.eleicao}</p>
              <p><strong>Modalidade vigente:</strong> {estadoEleicao.modalidade_vigente}</p>
              {!estadoEleicao.opcao_apresentada && (
                <p className="mt-1 text-amber-700">
                  Sem evidência suficiente: eleição não comprovada e modalidade não determinada.
                </p>
              )}
            </div>

            {estadoEleicao.historico.map((item) => (
              <div key={item.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <p className="font-medium text-slate-800">
                  Manifestação em {item.manifestada_em} · efeitos {item.eficacia_inicio} a {item.eficacia_fim}
                </p>
                <p className="mt-1 break-all text-xs text-slate-500">
                  Evidência: {item.evidencia_ref} · fonte: {item.fonte}
                </p>
                {item.cancelada_em ? (
                  <p className="mt-2 text-xs text-slate-600">
                    Cancelada em {item.cancelada_em} · evidência: {item.cancelamento_evidencia_ref}
                  </p>
                ) : (
                  <div className="mt-3 grid gap-2 md:grid-cols-[160px_1fr_auto]">
                    <input
                      type="date"
                      aria-label="Data do cancelamento"
                      value={canceladaEm}
                      onChange={(e) => setCanceladaEm(e.target.value)}
                      className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                    <input
                      aria-label="Evidência oficial do cancelamento"
                      value={cancelamentoEvidencia}
                      onChange={(e) => setCancelamentoEvidencia(e.target.value)}
                      placeholder="Protocolo ou recibo oficial do cancelamento"
                      className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => cancelarEleicao(item.id)}
                      disabled={eleicaoLoading}
                      className="rounded-lg border border-red-300 px-3 py-2 text-sm font-medium text-red-700 disabled:opacity-50"
                    >
                      Registrar cancelamento
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-slate-900">Senha</h2>
        <p className="mt-1 text-sm text-slate-600">
          Se você recebeu uma senha inicial da Tribultz, troque-a por uma que só você conheça.
        </p>
        <form onSubmit={trocarSenha} className="mt-3 grid max-w-md gap-3">
          <div>
            <label htmlFor="senha-atual" className="mb-1 block text-sm font-medium text-slate-700">
              Senha atual
            </label>
            <input
              id="senha-atual"
              name="current_password"
              type="password"
              required
              autoComplete="current-password"
              value={senhaAtual}
              onChange={(e) => setSenhaAtual(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-tribultz-500 focus:outline-none focus:ring-1 focus:ring-tribultz-500"
            />
          </div>
          <div>
            <label htmlFor="senha-nova" className="mb-1 block text-sm font-medium text-slate-700">
              Nova senha
            </label>
            <input
              id="senha-nova"
              name="new_password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              aria-describedby="senha-nova-ajuda"
              value={senhaNova}
              onChange={(e) => setSenhaNova(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-tribultz-500 focus:outline-none focus:ring-1 focus:ring-tribultz-500"
            />
            <p id="senha-nova-ajuda" className="mt-0.5 text-xs text-slate-400">
              Mínimo de 8 caracteres.
            </p>
          </div>
          <div>
            <label htmlFor="senha-confirma" className="mb-1 block text-sm font-medium text-slate-700">
              Confirmar nova senha
            </label>
            <input
              id="senha-confirma"
              name="confirm_password"
              type="password"
              required
              autoComplete="new-password"
              value={senhaConfirma}
              onChange={(e) => setSenhaConfirma(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-tribultz-500 focus:outline-none focus:ring-1 focus:ring-tribultz-500"
            />
          </div>
          {senhaErro && (
            <p role="alert" className="text-xs text-red-600">
              {senhaErro}
            </p>
          )}
          <div>
            <button
              type="submit"
              disabled={senhaLoading}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {senhaLoading ? "Alterando..." : "Alterar senha"}
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-slate-900">API Keys</h2>
        <p className="mt-1 text-sm text-slate-500">
          Integre ERPs e sistemas externos via API pay-per-call.
        </p>
        <div className="mt-3">
          <Link
            href="/settings/api"
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Gerenciar API Keys
          </Link>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-slate-900">Meus Dados (LGPD)</h2>
        <p className="mt-1 text-sm text-slate-500">
          Seus direitos conforme a Lei Geral de Proteção de Dados (Lei 13.709/2018).
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={async () => {
              const currentToken = getToken();
              const currentTenant = getTenantId();
              try {
                const res = await fetch(`${API_BASE}/api/v1/lgpd/my-data`, {
                  headers: { Authorization: `Bearer ${currentToken}`, "X-Tenant-Id": currentTenant },
                });
                const data = await res.json();
                setToast({ tone: "success", msg: `Dados carregados: ${data.user?.email ?? "OK"}` });
              } catch {
                setToast({ tone: "error", msg: "Falha ao carregar dados." });
              }
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Ver meus dados
          </button>
          <button
            type="button"
            onClick={() => {
              const currentToken = getToken();
              const currentTenant = getTenantId();
              window.open(`${API_BASE}/api/v1/lgpd/export?token=${encodeURIComponent(currentToken)}&tenant=${encodeURIComponent(currentTenant)}`, "_blank");
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Exportar dados (JSON)
          </button>
          <button
            type="button"
            onClick={async () => {
              if (!window.confirm("Tem certeza? Esta ação é irreversível. Seus dados serão anonimizados.")) return;
              const currentToken = getToken();
              const currentTenant = getTenantId();
              try {
                const res = await fetch(`${API_BASE}/api/v1/lgpd/delete-account`, {
                  method: "POST",
                  headers: { Authorization: `Bearer ${currentToken}`, "X-Tenant-Id": currentTenant, "Content-Type": "application/json" },
                });
                if (res.ok) {
                  setToast({ tone: "success", msg: "Conta desativada. Redirecionando..." });
                  setTimeout(() => window.location.href = "/login", 2000);
                } else {
                  const data = await res.json().catch(() => ({}));
                  setToast({ tone: "error", msg: data.detail ?? "Falha ao excluir conta." });
                }
              } catch {
                setToast({ tone: "error", msg: "Falha ao excluir conta." });
              }
            }}
            className="rounded-lg border border-red-300 px-4 py-2 text-sm font-semibold text-red-600 hover:bg-red-50"
          >
            Excluir minha conta
          </button>
        </div>
        <p className="mt-3 text-xs text-slate-400">
          Dados fiscais são retidos conforme obrigação legal. Contato DPO: dpo@tribultz.com.br
        </p>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-slate-900">Privacidade e Cookies</h2>
        <p className="mt-1 text-sm text-slate-500">
          O console usa armazenamento local do navegador para sessão e preferências, além de
          controles técnicos de segurança quando necessário.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href="/privacy"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Política de Privacidade
          </Link>
          <Link
            href="/cookies"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Política de Cookies
          </Link>
          <Link
            href="/terms"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Termos de Uso
          </Link>
        </div>
      </section>

      {toast ? <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </section>
  );
}
