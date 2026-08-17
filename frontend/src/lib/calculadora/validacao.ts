/**
 * Validação client-side da calculadora CBS/IBS (#657, L2.1 do Lote 2).
 *
 * A validação server-side existe e está correta (`calculadora.py:73-95`, devolve
 * 422 com mensagem) — o diagnóstico externo errou ao dizer que faltava. O que
 * faltava era a do cliente: o botão está fora de `<form>`, os `min` são
 * decorativos e não há `required`, então requisição inválida saía e o usuário só
 * descobria depois da ida ao servidor.
 *
 * As regras aqui espelham as do backend de propósito. Divergir seria pior que
 * não validar: o cliente recusaria o que o servidor aceita, ou o contrário.
 */

export type CamposCalculadora = {
  baseValue: string;
  quantity: string;
  /** Opcional; quando preenchido, precisa ter 8 dígitos. */
  ncm: string;
};

export type ErrosCalculadora = Partial<Record<keyof CamposCalculadora, string>>;

/** Espelha `calculadora.py`: base > 0, quantidade > 0, NCM de 8 dígitos. */
export function validarCalculadora(campos: CamposCalculadora): ErrosCalculadora {
  const erros: ErrosCalculadora = {};

  const base = Number(String(campos.baseValue).replace(",", "."));
  if (!String(campos.baseValue).trim()) {
    erros.baseValue = "Informe o valor base da operação.";
  } else if (!Number.isFinite(base) || base <= 0) {
    erros.baseValue = "O valor base precisa ser maior que zero.";
  }

  const qtd = Number(campos.quantity);
  if (!String(campos.quantity).trim()) {
    erros.quantity = "Informe a quantidade.";
  } else if (!Number.isInteger(qtd) || qtd < 1) {
    erros.quantity = "A quantidade precisa ser um número inteiro a partir de 1.";
  }

  const ncm = String(campos.ncm ?? "").trim();
  if (ncm && !/^\d{8}$/.test(ncm)) {
    erros.ncm = "O NCM tem 8 dígitos — deixe em branco se não souber.";
  }

  return erros;
}

export function temErro(erros: ErrosCalculadora): boolean {
  return Object.keys(erros).length > 0;
}
