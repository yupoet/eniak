// Tiny edge proxy: api.eniak.org -> eniak-api-production.up.railway.app
// Rewrites Host so Railway's router recognises the service.
// Deployed via the Workers API; bound to api.eniak.org/* via a Worker Route.

const ORIGIN_HOST = "eniak-api-production.up.railway.app";

export default {
  async fetch(request) {
    const inUrl = new URL(request.url);
    const outUrl = new URL(inUrl.pathname + inUrl.search, `https://${ORIGIN_HOST}`);

    const headers = new Headers(request.headers);
    headers.set("Host", ORIGIN_HOST);
    headers.set("X-Forwarded-Host", inUrl.hostname);
    headers.set("X-Forwarded-Proto", "https");

    const init = {
      method: request.method,
      headers,
      redirect: "manual",
    };
    if (!["GET", "HEAD"].includes(request.method)) {
      init.body = request.body;
    }

    const response = await fetch(outUrl.toString(), init);
    // Pass through; do not buffer (the dry-run endpoint can stream long responses).
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  },
};
