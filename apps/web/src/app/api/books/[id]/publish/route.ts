import { NextResponse } from "next/server";
import { publishChapterServer } from "@/lib/server-api";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  let body: { chapter_id?: string; target?: "markdown" | "feishu"; mode?: "dry_run" | "live" };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const chapterId = (body.chapter_id ?? "").trim();
  if (!chapterId) {
    return NextResponse.json({ error: "chapter_id is required" }, { status: 422 });
  }
  const target = body.target === "feishu" ? "feishu" : "markdown";
  const mode = body.mode === "live" ? "live" : "dry_run";
  try {
    const record = await publishChapterServer(id, chapterId, target, mode);
    return NextResponse.json(record, { status: 200 });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : String(err) },
      { status: 502 },
    );
  }
}
