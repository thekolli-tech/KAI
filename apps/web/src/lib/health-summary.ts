import type { CheckState, HealthReport } from "@kai/types";

const checkLabels: Record<keyof HealthReport["checks"], string> = {
  api: "API",
  engine: "Engine",
  model_runtime: "Model runtime",
  postgres: "PostgreSQL",
  redis: "Redis",
  qdrant: "Qdrant",
  minio: "MinIO",
};

export function checkLabel(key: keyof HealthReport["checks"]): string {
  return checkLabels[key];
}

export function describeCheck(state: CheckState): string {
  switch (state) {
    case "ok":
      return "Responding";
    case "interface_only":
      return "Interface only";
    case "mock":
      return "Local mock";
    case "not_configured":
      return "Not configured";
    case "configured_unchecked":
      return "Configured, not checked";
  }
}

export function checkEntries(report: HealthReport): { key: keyof HealthReport["checks"]; state: CheckState }[] {
  return (Object.keys(report.checks) as (keyof HealthReport["checks"])[]).map((key) => ({
    key,
    state: report.checks[key],
  }));
}

export function statusMessage(report: HealthReport): string {
  const runtime =
    report.checks.model_runtime === "mock"
      ? "The model runtime is a local mock for development. This note is written by the workspace. It is not a model response."
      : "The model runtime is an interface only, so this note is written by the workspace from the health check. It is not a model response.";
  return [`**API** is responding on phase ${report.phase}.`, "", runtime].join("\n");
}
