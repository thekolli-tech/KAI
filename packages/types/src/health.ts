export const checkStates = [
  "ok",
  "interface_only",
  "mock",
  "not_configured",
  "configured_unchecked",
] as const;

export type CheckState = (typeof checkStates)[number];

export const environments = ["development", "test", "production"] as const;

export type EnvironmentName = (typeof environments)[number];

export interface HealthChecks {
  api: CheckState;
  engine: CheckState;
  model_runtime: CheckState;
  postgres: CheckState;
  redis: CheckState;
  qdrant: CheckState;
  minio: CheckState;
}

export interface HealthReport {
  status: "ok";
  service: "kai-api";
  version: string;
  phase: number;
  environment: EnvironmentName;
  checks: HealthChecks;
}

export class HealthReportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "HealthReportError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readCheck(value: unknown, key: keyof HealthChecks): CheckState {
  if (!isRecord(value) || !(key in value)) {
    throw new HealthReportError(`Health check "${key}" is missing.`);
  }
  const state = value[key];
  if (typeof state !== "string" || !checkStates.includes(state as CheckState)) {
    throw new HealthReportError(`Health check "${key}" is invalid.`);
  }
  return state as CheckState;
}

export function parseHealthReport(value: unknown): HealthReport {
  if (!isRecord(value)) {
    throw new HealthReportError("Health report must be an object.");
  }
  if (value.status !== "ok" || value.service !== "kai-api") {
    throw new HealthReportError("Health report identity is invalid.");
  }
  if (typeof value.version !== "string" || value.version.length === 0) {
    throw new HealthReportError("Health report version is invalid.");
  }
  if (typeof value.phase !== "number" || !Number.isInteger(value.phase)) {
    throw new HealthReportError("Health report phase is invalid.");
  }
  if (
    typeof value.environment !== "string" ||
    !environments.includes(value.environment as EnvironmentName)
  ) {
    throw new HealthReportError("Health report environment is invalid.");
  }
  if (!isRecord(value.checks)) {
    throw new HealthReportError("Health report checks are missing.");
  }

  const checks: HealthChecks = {
    api: readCheck(value.checks, "api"),
    engine: readCheck(value.checks, "engine"),
    model_runtime: readCheck(value.checks, "model_runtime"),
    postgres: readCheck(value.checks, "postgres"),
    redis: readCheck(value.checks, "redis"),
    qdrant: readCheck(value.checks, "qdrant"),
    minio: readCheck(value.checks, "minio"),
  };

  return {
    status: "ok",
    service: "kai-api",
    version: value.version,
    phase: value.phase,
    environment: value.environment as EnvironmentName,
    checks,
  };
}
