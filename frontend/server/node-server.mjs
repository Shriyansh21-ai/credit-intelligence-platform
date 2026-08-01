// Production SSR server for the TanStack Start build (Phase 11, M2).
//
// The Vite/Nitro build emits a Web-standard fetch handler
// (`dist/server/server.js` → `export default { fetch(request, env, ctx) }`)
// plus hashed client assets in `dist/client/assets`. This adapter runs that
// handler on a plain Node HTTP server (Node >= 20 provides global
// Request/Response/ReadableStream), serving static assets directly and routing
// everything else through SSR. It has no framework-specific dependencies.
//
//   PORT   listen port (default 3000)
//   HOST   bind address (default 0.0.0.0)

import { createServer } from "node:http";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join, normalize, extname } from "node:path";
import { Readable } from "node:stream";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const CLIENT_DIR = join(ROOT, "dist", "client");

const PORT = Number(process.env.PORT || 3000);
const HOST = process.env.HOST || "0.0.0.0";

const { default: server } = await import(
  pathToFileURL(join(ROOT, "dist", "server", "server.js")).href
);

const MIME = {
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".map": "application/json",
};

/** Serve a hashed static asset, or return false if it does not exist. */
async function serveStatic(req, res, pathname) {
  // Prevent path traversal; only files physically under dist/client are served.
  const filePath = normalize(join(CLIENT_DIR, pathname));
  if (!filePath.startsWith(CLIENT_DIR)) return false;
  try {
    const info = await stat(filePath);
    if (!info.isFile()) return false;
    const type = MIME[extname(filePath)] || "application/octet-stream";
    // Hashed assets are immutable and safe to cache aggressively.
    res.writeHead(200, {
      "content-type": type,
      "cache-control": "public, max-age=31536000, immutable",
      "content-length": info.size,
    });
    createReadStream(filePath).pipe(res);
    return true;
  } catch {
    return false;
  }
}

/** Convert a Node request into a Web Request. */
function toWebRequest(req) {
  const proto = req.headers["x-forwarded-proto"] || "http";
  const host = req.headers.host || `localhost:${PORT}`;
  const url = `${proto}://${host}${req.url}`;
  const method = req.method || "GET";
  const headers = new Headers();
  for (const [k, v] of Object.entries(req.headers)) {
    if (Array.isArray(v)) v.forEach((val) => headers.append(k, val));
    else if (v != null) headers.set(k, v);
  }
  const hasBody = method !== "GET" && method !== "HEAD";
  return new Request(url, {
    method,
    headers,
    body: hasBody ? Readable.toWeb(req) : undefined,
    duplex: hasBody ? "half" : undefined,
  });
}

/** Stream a Web Response back through the Node response. */
async function sendWebResponse(res, webRes) {
  const headers = {};
  webRes.headers.forEach((value, key) => {
    headers[key] = value;
  });
  res.writeHead(webRes.status, headers);
  if (webRes.body) {
    Readable.fromWeb(webRes.body).pipe(res);
  } else {
    res.end(Buffer.from(await webRes.arrayBuffer()));
  }
}

const httpServer = createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent((req.url || "/").split("?")[0]);

    // Lightweight liveness/readiness endpoint for probes.
    if (pathname === "/healthz" || pathname === "/livez") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end('{"status":"ok"}');
      return;
    }

    // Static client assets are served directly (SSR handler does not).
    if (pathname.startsWith("/assets/") || pathname === "/favicon.ico") {
      if (await serveStatic(req, res, pathname)) return;
    }

    const webRes = await server.fetch(toWebRequest(req), {}, {});
    await sendWebResponse(res, webRes);
  } catch (err) {
    console.error("[ssr] request failed:", err);
    if (!res.headersSent) {
      res.writeHead(500, { "content-type": "text/plain" });
    }
    res.end("Internal Server Error");
  }
});

httpServer.listen(PORT, HOST, () => {
  console.log(`[ssr] frontend listening on http://${HOST}:${PORT}`);
});

// Graceful shutdown for container stop / k8s SIGTERM.
for (const sig of ["SIGTERM", "SIGINT"]) {
  process.on(sig, () => {
    console.log(`[ssr] received ${sig}; closing`);
    httpServer.close(() => process.exit(0));
  });
}
