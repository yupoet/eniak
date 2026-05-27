import { NextResponse } from "next/server";
import { createBookServer } from "@/lib/server-api";

export async function POST(req: Request) {
  let body: { topic?: string; chapter_count?: number };
  try {
    body = (await req.json()) as { topic?: string; chapter_count?: number };
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const topic = (body.topic ?? "").trim();
  const count = Number.isFinite(body.chapter_count) ? Number(body.chapter_count) : 3;
  if (topic.length < 3) {
    return NextResponse.json(
      { error: "Topic must be at least 3 characters." },
      { status: 422 },
    );
  }
  try {
    const book = await createBookServer(topic, Math.max(1, Math.min(8, count)));
    return NextResponse.json(book, { status: 202 });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : String(err) },
      { status: 502 },
    );
  }
}
