import { NextResponse } from "next/server";
import { updateCardServer } from "@/lib/server-api";
import type { ReviewState } from "@/lib/api-types";

const ALLOWED: ReviewState[] = [
  "draft",
  "in_review",
  "approved",
  "published",
  "rejected",
];

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string; cardId: string }> },
) {
  const { id, cardId } = await params;
  let body: { review_state?: ReviewState };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  if (!body.review_state || !ALLOWED.includes(body.review_state)) {
    return NextResponse.json(
      { error: `review_state must be one of ${ALLOWED.join(", ")}` },
      { status: 422 },
    );
  }
  try {
    const result = await updateCardServer(id, cardId, body.review_state);
    return NextResponse.json(result);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : String(err) },
      { status: 502 },
    );
  }
}
