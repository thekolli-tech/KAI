"use client";

import { useCallback, useEffect, useState } from "react";
import { defaultApiOrigin } from "@kai/config";
import { apiRoutes } from "@kai/shared";
import { parseHealthReport, type HealthReport } from "@kai/types";

export type HealthView =
  | { status: "loading" }
  | { status: "ready"; report: HealthReport }
  | { status: "error"; detail: string };

export function useHealth(): { view: HealthView; reload: () => void } {
  const [view, setView] = useState<HealthView>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => {
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const origin = process.env.NEXT_PUBLIC_KAI_API_URL ?? defaultApiOrigin;

    fetch(`${origin}${apiRoutes.health}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Health check returned ${response.status}.`);
        }
        return parseHealthReport(await response.json());
      })
      .then((report) => {
        if (!controller.signal.aborted) {
          setView({ status: "ready", report });
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        const detail = error instanceof Error ? error.message : "Health check failed.";
        setView({ status: "error", detail });
      });

    return () => controller.abort();
  }, [attempt]);

  return { view, reload };
}
