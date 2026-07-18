import test from "node:test";
import assert from "node:assert/strict";
import { formatDateTimeBR } from "./formatDateTimeBR";

test("#419 formatDateTimeBR: instante UTC vira horário de Brasília (UTC-3, sem DST)", () => {
  assert.equal(formatDateTimeBR("2026-06-15T12:00:00.000Z"), "15/06/2026, 09:00");
});

test("#419 formatDateTimeBR: aceita Date além de string ISO", () => {
  assert.equal(
    formatDateTimeBR(new Date("2026-06-15T12:00:00.000Z")),
    "15/06/2026, 09:00",
  );
});

test("#419 formatDateTimeBR: dia muda na conversão (não só a hora) — o bug original", () => {
  assert.equal(formatDateTimeBR("2026-03-01T02:00:00.000Z"), "28/02/2026, 23:00");
});

test("#419 formatDateTimeBR: determinístico independente do TZ do processo", () => {
  const original = process.env.TZ;
  try {
    process.env.TZ = "America/Los_Angeles";
    assert.equal(formatDateTimeBR("2026-06-15T12:00:00.000Z"), "15/06/2026, 09:00");
  } finally {
    process.env.TZ = original;
  }
});
