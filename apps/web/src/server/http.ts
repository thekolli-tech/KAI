import { displayError } from "@kai/types";

import { localBearerToken } from "@/server/upstream";

export function jsonError(status: number): Response {
  const code = publicStatus(status);
  return Response.json(
    { message: displayError({ status: code }) },
    { status: code, headers: { "Cache-Control": "no-store" } },
  );
}

export async function authorizedFetch(url: string, init: RequestInit): Promise<Response> {
  const token = localBearerToken();
  if (token === "") {
    return jsonError(401);
  }
  try {
    return await fetch(url, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
        ...init.headers,
      },
    });
  } catch {
    return jsonError(503);
  }
}

export async function proxyJson(upstream: Response): Promise<Response> {
  if (!upstream.ok) {
    await upstream.body?.cancel();
    return jsonError(upstream.status);
  }
  return Response.json(await upstream.json(), {
    status: upstream.status,
    headers: { "Cache-Control": "no-store" },
  });
}

function publicStatus(status: number): number {
  if (status === 401 || status === 403 || status === 404 || status === 422 || status === 502 || status === 503) {
    return status;
  }
  return 500;
}
