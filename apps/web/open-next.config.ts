import { defineCloudflareConfig } from "@opennextjs/cloudflare";

// Minimal config — OpenNext picks sane defaults for the Cloudflare Workers
// target. The KV/R2 caches are skipped intentionally for Phase 2; we run a
// single Worker without ISR.
export default defineCloudflareConfig({});
