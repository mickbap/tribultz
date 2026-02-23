const KEY_MOCK_MODE = "tribultz.mock_mode";
const KEY_TENANT = "tribultz.tenant";
const KEY_TOKEN = "tribultz.token";

export const DEFAULT_TENANT = "tenant-a";

function safeLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

export function getMockMode(): boolean {
  const store = safeLocalStorage();
  if (!store) return true;
  const raw = store.getItem(KEY_MOCK_MODE);
  if (raw === null) return true;
  return raw === "true";
}

export function setMockMode(value: boolean): void {
  const store = safeLocalStorage();
  if (!store) return;
  store.setItem(KEY_MOCK_MODE, String(value));
}

export function getTenantId(): string {
  const store = safeLocalStorage();
  if (!store) return DEFAULT_TENANT;
  return store.getItem(KEY_TENANT) ?? DEFAULT_TENANT;
}

export function setTenantId(tenantId: string): void {
  const store = safeLocalStorage();
  if (!store) return;
  store.setItem(KEY_TENANT, tenantId);
}

export function getToken(): string {
  const store = safeLocalStorage();
  if (!store) return "demo-token";
  return store.getItem(KEY_TOKEN) ?? "demo-token";
}

export function setToken(token: string): void {
  const store = safeLocalStorage();
  if (!store) return;
  store.setItem(KEY_TOKEN, token);
}

export function clearSession(): void {
  const store = safeLocalStorage();
  if (!store) return;
  store.removeItem(KEY_TOKEN);
}
