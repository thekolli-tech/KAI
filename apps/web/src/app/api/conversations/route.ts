import { connection } from "next/server";

import { sessions } from "@/server/sessions";

export async function GET() {
  await connection();
  return Response.json(
    { conversations: sessions.list() },
    { headers: { "Cache-Control": "no-store" } },
  );
}

export async function POST() {
  await connection();
  const conversation = sessions.create();
  return Response.json(
    { id: conversation.id, title: conversation.title, updatedAt: conversation.updatedAt },
    { status: 201, headers: { "Cache-Control": "no-store" } },
  );
}
