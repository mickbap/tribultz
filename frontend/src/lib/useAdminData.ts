"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";
import { getToken } from "@/lib/storage";

/** Busca autenticada de dados do admin BFF. O acesso é garantido pelo guard do layout /admin. */
export function useAdminData<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}${path}`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!alive) return;
        if (!res.ok) setError(`Erro ${res.status}`);
        else setData((await res.json()) as T);
      } catch {
        if (alive) setError("Erro de conexão.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [path]);

  return { data, error, loading };
}
