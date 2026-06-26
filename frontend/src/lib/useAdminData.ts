"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";
import { getToken } from "@/lib/storage";

/** Busca autenticada de dados do admin BFF. O acesso é garantido pelo guard do layout /admin. */
export function useAdminData<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    (async () => {
      try {
        const res = await fetch(`${API_BASE}${path}`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!alive) return;
        if (!res.ok) setError(`Erro ${res.status}`);
        else {
          setError(null);
          setData((await res.json()) as T);
        }
      } catch {
        if (alive) setError("Erro de conexão.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [path, tick]);

  return { data, error, loading, reload };
}

/** Mutação autenticada (ação administrativa). Lança em erro para o chamador tratar. */
export async function adminPost(path: string, body: unknown): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Erro ${res.status}`);
  }
}
