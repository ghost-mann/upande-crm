// Shared Vite dev-server proxy config for the Upande CRM frontend.
//
// Everything is derived at runtime from the bench, so there are no hardcoded
// ports or site names:
//   - webserver/socketio ports come from sites/common_site_config.json
//   - the bench root is found by walking up from the current working dir
//   - the Frappe site is resolved per-request from the Host header, falling
//     back to the default site when accessed via localhost/127.0.0.1
//
// Usage in a frontend's vite.config.js:
//   import proxyOptions from '../proxyOptions.js';
//   ...
//   server: { port: 8084, proxy: proxyOptions('/assets/customer_portal/site/') }

import { readFileSync, existsSync, readdirSync, statSync } from 'fs';
import { resolve, dirname } from 'path';

function findBenchRoot(start) {
  let dir = start;
  while (dir !== dirname(dir)) {
    if (existsSync(resolve(dir, 'sites/common_site_config.json'))) return dir;
    dir = dirname(dir);
  }
  throw new Error('proxyOptions: could not locate bench root (sites/common_site_config.json)');
}

const benchRoot = findBenchRoot(process.cwd());
const commonSiteConfig = JSON.parse(
  readFileSync(resolve(benchRoot, 'sites/common_site_config.json'), 'utf-8')
);

const webserverPort = commonSiteConfig.webserver_port || 8000;
const socketioPort = commonSiteConfig.socketio_port || 9000;

function defaultSite() {
  // Prefer an explicit default site, else the lone non-"assets" site directory.
  try {
    const cur = readFileSync(resolve(benchRoot, 'sites/currentsite.txt'), 'utf-8').trim();
    if (cur) return cur;
  } catch {
    /* no currentsite.txt — fall through */
  }
  const sites = readdirSync(resolve(benchRoot, 'sites')).filter(
    (name) => name !== 'assets' && statSync(resolve(benchRoot, 'sites', name)).isDirectory()
  );
  return sites[0]; // single-site bench
}

function resolveSite(req) {
  let host = (req.headers.host || '').split(':')[0];
  if (!host || host === 'localhost' || host === '127.0.0.1') host = defaultSite();
  return host;
}

// Rewrite the outgoing Host header so Frappe's multi-tenant router resolves the
// correct site regardless of how the browser reached the dev server.
function withSiteHost(proxy) {
  proxy.on('proxyReq', (proxyReq, req) => {
    proxyReq.setHeader('Host', resolveSite(req));
  });
}

export default function proxyOptions(base) {
  const backend = `http://127.0.0.1:${webserverPort}`;
  const common = { target: backend, ws: true, configure: withSiteHost };

  return {
    '/api': { ...common },
    '/files': { ...common },
    '/private': { ...common },
    '/socket.io': {
      target: `http://127.0.0.1:${socketioPort}`,
      ws: true,
      configure: withSiteHost,
    },
    '/assets': {
      ...common,
      // Let Vite serve this app's own dev bundle; proxy everything else under
      // /assets (Frappe framework assets, other apps) to the backend.
      bypass(req) {
        if (base && req.url.startsWith(base)) return req.url;
      },
    },
  };
}
