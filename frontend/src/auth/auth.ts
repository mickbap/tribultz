/**
 * Token management for Tribultz Console.
 *
 * ⚠️ XSS WARNING: sessionStorage is accessible to any JS running on this
 * origin. This is an interim solution — migrate to HttpOnly cookies or a
 * server-side session once the auth layer matures.
 */

const TOKEN_KEY = "TRIBULTZ_TOKEN";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}
