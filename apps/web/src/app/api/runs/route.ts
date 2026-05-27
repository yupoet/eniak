import { NextResponse } from "next/server";
import { createRunServer } from "@/lib/server-api";

export async function POST(req: Request) {
  let body: { topic?: string };
  try {
    body = (await req.json()) as { topic?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const topic = (body.topic ?? "").trim();
  if (topic.length < 3) {
    return NextResponse.json(
      { error: "Topic must be at least 3 characters." },
      { status: 422 },
    );
  }
  try {
    const run = await createRunServer(topic);
    return NextResponse.json(run, { status: 202 });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: message },
      { status: 502 },
    );
  }
}
