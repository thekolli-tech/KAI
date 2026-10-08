import assert from "node:assert/strict";
import test from "node:test";

import { HealthReportError, parseHealthReport } from "./health.ts";

const validReport = {
  status: "ok",
  service: "kai-api",
  version: "0.1.0",
  phase: 1,
  environment: "development",
  checks: {
    api: "ok",
    engine: "interface_only",
    model_runtime: "interface_only",
    postgres: "not_configured",
    redis: "not_configured",
    qdrant: "not_configured",
    minio: "configured_unchecked",
  },
};

test("parseHealthReport accepts the Phase 1 contract", () => {
  const report = parseHealthReport(validReport);
  assert.equal(report.phase, 1);
  assert.equal(report.checks.model_runtime, "interface_only");
});

test("parseHealthReport rejects an unknown service", () => {
  assert.throws(
    () => parseHealthReport({ ...validReport, service: "openai" }),
    HealthReportError,
  );
});

test("parseHealthReport rejects an unknown check state", () => {
  assert.throws(
    () =>
      parseHealthReport({
        ...validReport,
        checks: { ...validReport.checks, api: "healthy" },
      }),
    HealthReportError,
  );
});
