import { exportJobEvidenceZip } from "../api";
import { downloadZip } from "./jobEvidenceZip";

export type ExportToastFeedback = {
  tone: "success" | "error" | "info";
  message: string;
};

export function toastFromExportError(err: unknown): ExportToastFeedback {
  const rawMessage = err instanceof Error ? err.message : String(err ?? "");
  const message = rawMessage.trim() || "erro desconhecido";

  if (/Export via API ainda n[aã]o dispon[ií]vel\.?/i.test(message)) {
    return {
      tone: "info",
      message: "Export via API ainda não disponível. Use Mock Mode ou tente novamente mais tarde.",
    };
  }

  return {
    tone: "error",
    message: `Falha ao exportar evidências: ${message}`,
  };
}

export async function exportEvidenceZipAndDownload(jobId: string): Promise<ExportToastFeedback> {
  try {
    const result = await exportJobEvidenceZip(jobId);
    downloadZip(result.bytes, result.filename);
    return {
      tone: "success",
      message: "ZIP de evidências exportado com sucesso.",
    };
  } catch (err) {
    return toastFromExportError(err);
  }
}
