"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAdminData, adminPost, adminRequest, adminUpload } from "@/lib/useAdminData";
import { ORIGIN_LABEL, RECOGNITION_LABEL } from "../page";

// Cockpit Operacional do Programa Early Adopters (RFC-0024) — Tela 02: perfil
// do participante. Observa e organiza estados do sistema; não os replica.

const JOURNEY_STAGES: [string, string][] = [
  ["convite_enviado", "Convite enviado"],
  ["formulario_recebido", "Formulário recebido"],
  ["selecionado", "Selecionado"],
  ["convite_acesso_enviado", "Convite de acesso enviado"],
  ["primeiro_login", "Primeiro login"],
  ["xml_recebido", "XML recebido"],
  ["tera_em_preparacao", "TERA em preparação"],
  ["tera_apresentado", "TERA apresentado"],
  ["reuniao_realizada", "Reunião realizada"],
  ["em_acompanhamento", "Em acompanhamento"],
  ["convertido", "Convertido"],
  ["encerrado", "Encerrado"],
];
const JOURNEY_LABEL = Object.fromEntries(JOURNEY_STAGES);

const EVIDENCE_TYPES: [string, string][] = [
  ["problema_percebido", "Problema percebido"],
  ["problema_confirmado", "Problema confirmado"],
  ["objecao", "Objeção"],
  ["frase_marcante", "Frase marcante"],
  ["momento_wow", "Momento WOW"],
  ["momento_friccao", "Momento de fricção"],
  ["insight", "Insight"],
  ["hipotese", "Hipótese"],
  ["aprendizado", "Aprendizado"],
  ["proximo_passo", "Próximo passo"],
];
const EVIDENCE_LABEL = Object.fromEntries(EVIDENCE_TYPES);

type Grant = { id: string; plan_slug: string; starts_at: string; ends_at: string; status: string };
type JourneyEvent = { id: string | null; stage: string; occurred_at: string; note: string | null; source: "auto" | "manual"; created_by_email: string | null };
type Evidence = { id: string; tipo: string; texto: string; autor: string | null; occurred_at: string; created_at: string };
type Tera = { id: string; versao: string; status: string; responsavel: string | null; has_file: boolean; pdf_link: string | null; created_at: string };
type Conversion = { interesse: string | null; motivo: string | null; plano_slug: string | null; data: string | null; valor_cents: number | null; origem: string | null };
type Detail = {
  id: string; empresa: string; cnpj: string | null; email: string; responsavel: string | null;
  telefone: string | null; cargo: string | null; cidade: string | null; uf: string | null; erp: string | null;
  qtd_cnpjs: number | null; volume_nfe_mensal_aprox: number | null; origem: string; status: string;
  observacoes: string | null; proxima_acao: string | null; owner_email: string | null; recognition: string;
  conversion: Conversion; effective_plan: string | null; grant_ends_at: string | null; active_grant_id: string | null;
  grants: Grant[]; journey: JourneyEvent[]; customer_evidence: Evidence[]; tera: Tera[];
  system: { user_id: string | null; first_login_at: string | null; last_login_at: string | null };
};

function fmt(d: string | null): string {
  return d ? new Date(d).toLocaleString("pt-BR") : "—";
}

const inputCls = "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm";
const cardCls = "rounded-xl border border-slate-200 p-4";

export default function FoundingPartnerDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data, error, loading, reload } = useAdminData<Detail>(`/api/v1/admin/founding-partners/${id}`);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState<Record<string, string>>({});
  const [journeyOpen, setJourneyOpen] = useState(false);
  const [journeyForm, setJourneyForm] = useState({ stage: JOURNEY_STAGES[0][0], note: "" });
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [evidenceForm, setEvidenceForm] = useState({ tipo: EVIDENCE_TYPES[0][0], texto: "" });
  const [teraOpen, setTeraOpen] = useState(false);
  const [teraForm, setTeraForm] = useState({ versao: "", tera_status: "rascunho", responsavel: "", pdf_link: "" });
  const [teraFile, setTeraFile] = useState<File | null>(null);
  const [convertOpen, setConvertOpen] = useState(false);
  const [convertForm, setConvertForm] = useState({ plan_slug: "starter", billing_type: "PIX", motivo: "", origem: "cockpit" });
  const [convertResult, setConvertResult] = useState<{ checkout_url: string | null; pix_qr_code: string | null; pix_copy_paste: string | null } | null>(null);

  function openEdit() {
    if (!data) return;
    setEditForm({
      empresa: data.empresa, responsavel: data.responsavel ?? "", telefone: data.telefone ?? "",
      cargo: data.cargo ?? "", cidade: data.cidade ?? "", uf: data.uf ?? "", erp: data.erp ?? "",
      qtd_cnpjs: data.qtd_cnpjs?.toString() ?? "", volume_nfe_mensal_aprox: data.volume_nfe_mensal_aprox?.toString() ?? "",
      observacoes: data.observacoes ?? "", proxima_acao: data.proxima_acao ?? "", owner_email: data.owner_email ?? "",
    });
    setEditOpen(true);
  }

  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    setBusy("edit");
    try {
      await adminRequest("PATCH", `/api/v1/admin/founding-partners/${id}`, {
        empresa: editForm.empresa, responsavel: editForm.responsavel || null, telefone: editForm.telefone || null,
        cargo: editForm.cargo || null, cidade: editForm.cidade || null, uf: editForm.uf || null, erp: editForm.erp || null,
        qtd_cnpjs: editForm.qtd_cnpjs ? Number(editForm.qtd_cnpjs) : null,
        volume_nfe_mensal_aprox: editForm.volume_nfe_mensal_aprox ? Number(editForm.volume_nfe_mensal_aprox) : null,
        observacoes: editForm.observacoes || null, proxima_acao: editForm.proxima_acao || null,
        owner_email: editForm.owner_email || null,
      });
      setEditOpen(false);
      reload();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Falha ao salvar.");
    } finally {
      setBusy(null);
    }
  }

  async function toggleRecognition() {
    if (!data) return;
    const next = data.recognition === "founding_partner" ? "early_adopter" : "founding_partner";
    if (!window.confirm(`Marcar reconhecimento como "${RECOGNITION_LABEL[next]}"?`)) return;
    setBusy("recognition");
    try {
      await adminRequest("PATCH", `/api/v1/admin/founding-partners/${id}`, { recognition: next });
      reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Falha ao atualizar reconhecimento.");
    } finally {
      setBusy(null);
    }
  }

  async function addJourney(e: React.FormEvent) {
    e.preventDefault();
    setBusy("journey");
    try {
      await adminPost(`/api/v1/admin/founding-partners/${id}/journey`, {
        stage: journeyForm.stage, note: journeyForm.note || null,
      });
      setJourneyForm({ stage: JOURNEY_STAGES[0][0], note: "" });
      setJourneyOpen(false);
      reload();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Falha ao lançar evento.");
    } finally {
      setBusy(null);
    }
  }

  async function addEvidence(e: React.FormEvent) {
    e.preventDefault();
    setBusy("evidence");
    try {
      await adminPost(`/api/v1/admin/founding-partners/${id}/evidence`, {
        tipo: evidenceForm.tipo, texto: evidenceForm.texto,
      });
      setEvidenceForm({ tipo: EVIDENCE_TYPES[0][0], texto: "" });
      setEvidenceOpen(false);
      reload();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Falha ao registrar evidência.");
    } finally {
      setBusy(null);
    }
  }

  async function addTera(e: React.FormEvent) {
    e.preventDefault();
    setBusy("tera");
    try {
      const form = new FormData();
      form.append("versao", teraForm.versao);
      form.append("tera_status", teraForm.tera_status);
      if (teraForm.responsavel) form.append("responsavel", teraForm.responsavel);
      if (teraForm.pdf_link) form.append("pdf_link", teraForm.pdf_link);
      if (teraFile) form.append("file", teraFile);
      await adminUpload(`/api/v1/admin/founding-partners/${id}/tera`, form);
      setTeraForm({ versao: "", tera_status: "rascunho", responsavel: "", pdf_link: "" });
      setTeraFile(null);
      setTeraOpen(false);
      reload();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Falha ao registrar TERA.");
    } finally {
      setBusy(null);
    }
  }

  async function downloadTera(teraId: string) {
    try {
      const r = await adminRequest<{ download_url: string }>("GET", `/api/v1/admin/founding-partners/tera/${teraId}/download`);
      window.open(r.download_url, "_blank");
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Falha ao gerar link de download.");
    }
  }

  async function setInterest(interesse: string) {
    setBusy("interest");
    try {
      await adminRequest("PATCH", `/api/v1/admin/founding-partners/${id}/conversion`, { interesse });
      reload();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Falha ao registrar interesse.");
    } finally {
      setBusy(null);
    }
  }

  async function convert(e: React.FormEvent) {
    e.preventDefault();
    setBusy("convert");
    setConvertResult(null);
    try {
      const r = await adminRequest<{ checkout_url: string | null; pix_qr_code: string | null; pix_copy_paste: string | null }>(
        "POST", `/api/v1/admin/founding-partners/${id}/convert`,
        { plan_slug: convertForm.plan_slug, billing_type: convertForm.billing_type, motivo: convertForm.motivo || null, origem: convertForm.origem || null },
      );
      setConvertResult(r);
      reload();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Falha ao gerar assinatura ASAAS.");
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <p className="text-sm text-slate-500">Carregando…</p>;
  if (error || !data) return <p className="text-sm text-red-600">{error ?? "Não encontrado."}</p>;

  const journeySorted = [...data.journey].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));

  return (
    <div>
      <Link href="/admin/founding-partners" className="mb-3 inline-block text-xs text-slate-500 hover:underline">&larr; Founding Partners</Link>
      <div className="mb-1 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{data.empresa}</h1>
          <p className="text-sm text-slate-500">{data.email}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-3 py-1 text-xs font-medium ${data.recognition === "founding_partner" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
            {RECOGNITION_LABEL[data.recognition]}
          </span>
          <button onClick={toggleRecognition} disabled={busy === "recognition"} className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            {data.recognition === "founding_partner" ? "Reverter p/ Early Adopter" : "Marcar Founding Partner"}
          </button>
        </div>
      </div>
      {msg && <p className="mb-3 text-sm text-red-600">{msg}</p>}

      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Cadastrais */}
        <section className={cardCls}>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Cadastrais</h2>
            <button onClick={openEdit} className="text-xs font-medium text-blue-700 hover:underline">Editar</button>
          </div>
          {!editOpen ? (
            <dl className="grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-slate-400">Responsável</dt><dd className="text-slate-700">{data.responsavel ?? "—"}</dd>
              <dt className="text-slate-400">Cargo</dt><dd className="text-slate-700">{data.cargo ?? "—"}</dd>
              <dt className="text-slate-400">WhatsApp</dt><dd className="text-slate-700">{data.telefone ?? "—"}</dd>
              <dt className="text-slate-400">CNPJ</dt><dd className="text-slate-700">{data.cnpj ?? "—"}</dd>
              <dt className="text-slate-400">Cidade/UF</dt><dd className="text-slate-700">{data.cidade ?? "—"}{data.uf ? `/${data.uf}` : ""}</dd>
              <dt className="text-slate-400">ERP</dt><dd className="text-slate-700">{data.erp ?? "—"}</dd>
              <dt className="text-slate-400">Qtd. CNPJs</dt><dd className="text-slate-700">{data.qtd_cnpjs ?? "—"}</dd>
              <dt className="text-slate-400">Volume NF-e/mês</dt><dd className="text-slate-700">{data.volume_nfe_mensal_aprox ?? "—"}</dd>
              <dt className="text-slate-400">Origem</dt><dd className="text-slate-700">{ORIGIN_LABEL[data.origem] ?? data.origem}</dd>
              <dt className="text-slate-400">Owner</dt><dd className="text-slate-700">{data.owner_email ?? "—"}</dd>
              <dt className="text-slate-400">Próxima ação</dt><dd className="text-slate-700">{data.proxima_acao ?? "—"}</dd>
              <dt className="text-slate-400">Observações</dt><dd className="text-slate-700 col-span-1">{data.observacoes ?? "—"}</dd>
            </dl>
          ) : (
            <form onSubmit={saveEdit} className="grid grid-cols-2 gap-2 text-sm">
              {(["empresa", "responsavel", "cargo", "telefone", "cidade", "uf", "erp", "owner_email"] as const).map((f) => (
                <input key={f} className={inputCls} placeholder={f} value={editForm[f] ?? ""} onChange={(e) => setEditForm({ ...editForm, [f]: e.target.value })} />
              ))}
              <input className={inputCls} type="number" placeholder="Qtd. CNPJs" value={editForm.qtd_cnpjs ?? ""} onChange={(e) => setEditForm({ ...editForm, qtd_cnpjs: e.target.value })} />
              <input className={inputCls} type="number" placeholder="Volume NF-e/mês" value={editForm.volume_nfe_mensal_aprox ?? ""} onChange={(e) => setEditForm({ ...editForm, volume_nfe_mensal_aprox: e.target.value })} />
              <textarea className={`${inputCls} col-span-2`} placeholder="Próxima ação" value={editForm.proxima_acao ?? ""} onChange={(e) => setEditForm({ ...editForm, proxima_acao: e.target.value })} />
              <textarea className={`${inputCls} col-span-2`} placeholder="Observações" value={editForm.observacoes ?? ""} onChange={(e) => setEditForm({ ...editForm, observacoes: e.target.value })} />
              <div className="col-span-2 flex gap-2">
                <button type="submit" disabled={busy === "edit"} className="rounded-lg bg-[#2956E3] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">Salvar</button>
                <button type="button" onClick={() => setEditOpen(false)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600">Cancelar</button>
              </div>
            </form>
          )}
        </section>

        {/* Programa / Grant + sistema */}
        <section className={cardCls}>
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Programa</h2>
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-slate-400">Status</dt>
            <dd><span className={`rounded-full px-2 py-0.5 text-xs font-medium ${data.status === "active" ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-600"}`}>{data.status === "active" ? "Ativo" : "Encerrado"}</span></dd>
            <dt className="text-slate-400">Licença efetiva</dt>
            <dd className="text-slate-700">{data.effective_plan ? `${data.effective_plan} · até ${fmt(data.grant_ends_at)}` : "sem concessão ativa"}</dd>
            <dt className="text-slate-400">1º login</dt><dd className="text-slate-700">{fmt(data.system.first_login_at)}</dd>
            <dt className="text-slate-400">Último login</dt><dd className="text-slate-700">{fmt(data.system.last_login_at)}</dd>
          </dl>
        </section>

        {/* Jornada */}
        <section className={`${cardCls} md:col-span-2`}>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Jornada</h2>
            <button onClick={() => setJourneyOpen((v) => !v)} className="text-xs font-medium text-blue-700 hover:underline">{journeyOpen ? "Fechar" : "Lançar evento"}</button>
          </div>
          {journeyOpen && (
            <form onSubmit={addJourney} className="mb-4 grid grid-cols-1 gap-2 rounded-lg border border-slate-100 p-3 md:grid-cols-3">
              <select className={inputCls} value={journeyForm.stage} onChange={(e) => setJourneyForm({ ...journeyForm, stage: e.target.value })}>
                {JOURNEY_STAGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <input className={`${inputCls} md:col-span-1`} placeholder="Nota (opcional)" value={journeyForm.note} onChange={(e) => setJourneyForm({ ...journeyForm, note: e.target.value })} />
              <button type="submit" disabled={busy === "journey"} className="rounded-lg bg-[#2956E3] px-3 py-2 text-xs font-medium text-white disabled:opacity-50">Lançar</button>
            </form>
          )}
          <ol className="space-y-2">
            {journeySorted.map((e, i) => (
              <li key={e.id ?? `auto-${i}`} className="flex items-start gap-3 text-sm">
                <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${e.source === "auto" ? "bg-green-500" : "bg-blue-500"}`} />
                <div>
                  <span className="font-medium text-slate-800">{JOURNEY_LABEL[e.stage] ?? e.stage}</span>
                  <span className="ml-2 text-xs text-slate-400">{fmt(e.occurred_at)} · {e.source === "auto" ? "automático" : `manual${e.created_by_email ? ` (${e.created_by_email})` : ""}`}</span>
                  {e.note && <p className="text-xs text-slate-500">{e.note}</p>}
                </div>
              </li>
            ))}
            {journeySorted.length === 0 && <p className="text-sm text-slate-400">Nenhum evento ainda.</p>}
          </ol>
        </section>

        {/* Customer Evidence */}
        <section className={cardCls}>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Customer Evidence</h2>
            <button onClick={() => setEvidenceOpen((v) => !v)} className="text-xs font-medium text-blue-700 hover:underline">{evidenceOpen ? "Fechar" : "Registrar"}</button>
          </div>
          <p className="mb-3 text-xs text-slate-400">Discovery — nunca altera o Brain automaticamente.</p>
          {evidenceOpen && (
            <form onSubmit={addEvidence} className="mb-4 space-y-2 rounded-lg border border-slate-100 p-3">
              <select className={inputCls} value={evidenceForm.tipo} onChange={(e) => setEvidenceForm({ ...evidenceForm, tipo: e.target.value })}>
                {EVIDENCE_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <textarea className={inputCls} required placeholder="Texto" value={evidenceForm.texto} onChange={(e) => setEvidenceForm({ ...evidenceForm, texto: e.target.value })} />
              <button type="submit" disabled={busy === "evidence"} className="rounded-lg bg-[#2956E3] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">Registrar</button>
            </form>
          )}
          <ul className="space-y-2">
            {data.customer_evidence.map((ev) => (
              <li key={ev.id} className="rounded-lg bg-slate-50 p-2 text-sm">
                <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-600">{EVIDENCE_LABEL[ev.tipo] ?? ev.tipo}</span>
                <p className="mt-1 text-slate-700">{ev.texto}</p>
                <p className="text-xs text-slate-400">{fmt(ev.occurred_at)}{ev.autor ? ` · ${ev.autor}` : ""}</p>
              </li>
            ))}
            {data.customer_evidence.length === 0 && <p className="text-sm text-slate-400">Nenhuma evidência ainda.</p>}
          </ul>
        </section>

        {/* TERA */}
        <section className={cardCls}>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">TERA</h2>
            <button onClick={() => setTeraOpen((v) => !v)} className="text-xs font-medium text-blue-700 hover:underline">{teraOpen ? "Fechar" : "Registrar versão"}</button>
          </div>
          <p className="mb-3 text-xs text-slate-400">Registro manual (upload/link). Geração automática depende do RFC-0018.</p>
          {teraOpen && (
            <form onSubmit={addTera} className="mb-4 space-y-2 rounded-lg border border-slate-100 p-3">
              <input className={inputCls} required placeholder="Versão (ex.: v1)" value={teraForm.versao} onChange={(e) => setTeraForm({ ...teraForm, versao: e.target.value })} />
              <select className={inputCls} value={teraForm.tera_status} onChange={(e) => setTeraForm({ ...teraForm, tera_status: e.target.value })}>
                <option value="rascunho">Rascunho</option>
                <option value="apresentado">Apresentado</option>
              </select>
              <input className={inputCls} placeholder="Responsável" value={teraForm.responsavel} onChange={(e) => setTeraForm({ ...teraForm, responsavel: e.target.value })} />
              <input className={inputCls} placeholder="Link do PDF (opcional)" value={teraForm.pdf_link} onChange={(e) => setTeraForm({ ...teraForm, pdf_link: e.target.value })} />
              <input className={inputCls} type="file" accept="application/pdf" onChange={(e) => setTeraFile(e.target.files?.[0] ?? null)} />
              <button type="submit" disabled={busy === "tera"} className="rounded-lg bg-[#2956E3] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">Registrar</button>
            </form>
          )}
          <ul className="space-y-2">
            {data.tera.map((t) => (
              <li key={t.id} className="flex items-center justify-between rounded-lg bg-slate-50 p-2 text-sm">
                <div>
                  <span className="font-medium text-slate-800">{t.versao}</span>
                  <span className="ml-2 rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-600">{t.status === "apresentado" ? "Apresentado" : "Rascunho"}</span>
                  <p className="text-xs text-slate-400">{fmt(t.created_at)}{t.responsavel ? ` · ${t.responsavel}` : ""}</p>
                </div>
                {t.has_file ? (
                  <button onClick={() => downloadTera(t.id)} className="text-xs font-medium text-blue-700 hover:underline">Baixar</button>
                ) : t.pdf_link ? (
                  <a href={t.pdf_link} target="_blank" rel="noreferrer" className="text-xs font-medium text-blue-700 hover:underline">Abrir link</a>
                ) : null}
              </li>
            ))}
            {data.tera.length === 0 && <p className="text-sm text-slate-400">Nenhum TERA registrado ainda.</p>}
          </ul>
        </section>

        {/* Conversão */}
        <section className={`${cardCls} md:col-span-2`}>
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Conversão</h2>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-slate-500">Interesse em continuar:</span>
            {(["sim", "pensando", "nao"] as const).map((v) => (
              <button key={v} onClick={() => setInterest(v)} disabled={busy === "interest"}
                className={`rounded-full px-3 py-1 text-xs font-medium ${data.conversion.interesse === v ? "bg-blue-600 text-white" : "border border-slate-200 text-slate-600 hover:bg-slate-50"}`}>
                {v === "sim" ? "Sim" : v === "nao" ? "Não" : "Pensando"}
              </button>
            ))}
            {data.conversion.data && <span className="ml-2 text-xs text-slate-400">Convertido em {fmt(data.conversion.data)} · plano {data.conversion.plano_slug}</span>}
          </div>

          {!convertOpen ? (
            <button onClick={() => setConvertOpen(true)} className="rounded-lg bg-[#2956E3] px-4 py-2 text-sm font-medium text-white hover:opacity-90">
              Gerar assinatura ASAAS
            </button>
          ) : (
            <form onSubmit={convert} className="grid grid-cols-1 gap-2 rounded-lg border border-slate-100 p-3 md:grid-cols-2">
              <select className={inputCls} value={convertForm.plan_slug} onChange={(e) => setConvertForm({ ...convertForm, plan_slug: e.target.value })}>
                <option value="starter">Starter</option>
                <option value="profissional">Profissional</option>
                <option value="empresarial">Empresarial</option>
                <option value="contador">Contador</option>
              </select>
              <select className={inputCls} value={convertForm.billing_type} onChange={(e) => setConvertForm({ ...convertForm, billing_type: e.target.value })}>
                <option value="PIX">PIX</option>
                <option value="BOLETO">Boleto</option>
                <option value="CREDIT_CARD">Cartão de crédito</option>
              </select>
              <input className={`${inputCls} md:col-span-2`} placeholder="Motivo (opcional)" value={convertForm.motivo} onChange={(e) => setConvertForm({ ...convertForm, motivo: e.target.value })} />
              <div className="md:col-span-2 flex gap-2">
                <button type="submit" disabled={busy === "convert"} className="rounded-lg bg-[#2956E3] px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
                  {busy === "convert" ? "Gerando…" : "Confirmar e iniciar assinatura ASAAS"}
                </button>
                <button type="button" onClick={() => setConvertOpen(false)} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600">Cancelar</button>
              </div>
            </form>
          )}

          {convertResult && (
            <div className="mt-3 rounded-lg bg-green-50 p-3 text-sm text-green-800">
              <p className="font-medium">Assinatura iniciada.</p>
              {convertResult.checkout_url && <a href={convertResult.checkout_url} target="_blank" rel="noreferrer" className="underline">Abrir checkout</a>}
              {convertResult.pix_copy_paste && <p className="mt-1 break-all text-xs">PIX copia-e-cola: {convertResult.pix_copy_paste}</p>}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
