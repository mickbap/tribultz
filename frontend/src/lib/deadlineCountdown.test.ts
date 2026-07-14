import test from "node:test";
import assert from "node:assert/strict";
import { daysUntilDeadline } from "./deadlineCountdown";

test("#407 daysUntilDeadline: dias antes do prazo → positivo", () => {
  assert.equal(daysUntilDeadline(new Date("2026-08-02T00:00:00-03:00")), 1);
  assert.equal(daysUntilDeadline(new Date("2026-07-14T00:00:00-03:00")), 20);
});

test("#407 daysUntilDeadline: no dia do prazo → 0 (banner some)", () => {
  assert.equal(daysUntilDeadline(new Date("2026-08-03T00:00:00-03:00")), 0);
});

test("#407 daysUntilDeadline: depois do prazo → negativo (banner some)", () => {
  assert.ok(daysUntilDeadline(new Date("2026-08-04T00:00:00-03:00")) < 0);
  assert.ok(daysUntilDeadline(new Date("2027-01-01T00:00:00-03:00")) < 0);
});
