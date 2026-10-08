import { connection } from "next/server";

import { sessions } from "@/server/sessions";
import { displayError } from "@kai/types";

type Context = { params: Promise<{ id: string }> };

export async function GET(_request: Request, context: Context) {
  await connection();
  const { id } = await context.params;
  const conversation = sessions.get(id);
  if (conversation === undefined) {
    return Response.json(
      { message: displayError({ status: 404 }) },
      { status: 404, headers: { "Cache-Control": "no-store" } },
    );
  }
  return Response.json(conversation, { headers: { "Cache-Control": "no-store" } });
}
