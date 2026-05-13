const JARVIS_PWA_CACHE = "jarvis-dashboard-shell-v1";
const JARVIS_PWA_SHELL = [
  "/dashboard/app",
  "/dashboard/manifest.json",
];
const JARVIS_OFFLINE_HTML = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>JARVIS Offline</title><style>body{margin:0;min-height:100dvh;display:grid;place-items:center;background:#050e17;color:#e4f2ff;font-family:system-ui,-apple-system,Segoe UI,sans-serif}.box{max-width:360px;padding:24px;text-align:center}.k{color:#44f0ff;font-weight:800}.s{color:#8db3c8;font-size:14px;line-height:1.5}</style></head><body><div class="box"><div class="k">JARVIS Golf</div><p class="s">Offline shell loaded. Reconnect to resume live coaching, camera analysis, and profile sync.</p></div></body></html>`;

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(JARVIS_PWA_CACHE)
      .then(cache => cache.addAll(JARVIS_PWA_SHELL))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys
        .filter(key => key.startsWith("jarvis-dashboard-shell-") && key !== JARVIS_PWA_CACHE)
        .map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET" || req.mode !== "navigate") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith("/dashboard/")) return;

  event.respondWith(
    fetch(req)
      .then(res => {
        if (res && res.ok && res.headers.get("content-type")?.includes("text/html")) {
          const copy = res.clone();
          caches.open(JARVIS_PWA_CACHE).then(cache => cache.put("/dashboard/app", copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match("/dashboard/app")
        .then(cached => cached || new Response(JARVIS_OFFLINE_HTML, {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        })))
  );
});
