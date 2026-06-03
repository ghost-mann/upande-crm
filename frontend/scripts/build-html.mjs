// Post-build: take the Vite-emitted index.html and write it to the Frappe www/
// template at upande_crm/www/customer-relationship-management.html, injecting the Jinja boot block (the page's
// `boot` dict is exposed on window.* for the SPA to read) and inlining the CSS.

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT  = path.resolve(__dirname, '..');
const BUILT = path.resolve(ROOT, '../upande_crm/public/frontend');
const WWW   = path.resolve(ROOT, '../upande_crm/www');

const SRC  = path.resolve(BUILT, 'index.html');
const DEST = path.resolve(WWW, 'customer-relationship-management.html');

const JINJA_BOOT = `
    <script>
      {% for key in boot %}
      window["{{ key }}"] = {{ boot[key] | tojson }};
      {% endfor %}
    </script>
`;

// Inline the emitted stylesheet into the HTML so styles are parsed with the
// document (no separate render-blocking request that can paint late).
async function inlineCss(html) {
  const linkRe = /<link rel="stylesheet"[^>]*href="(\/assets\/upande_crm\/frontend\/assets\/[^"]+\.css)"[^>]*>/g;
  let out = html;
  for (const m of html.matchAll(linkRe)) {
    const rel = m[1].replace('/assets/upande_crm/frontend/', '');
    try {
      const css = await readFile(path.resolve(BUILT, rel), 'utf8');
      out = out.replace(m[0], `<style>${css}</style>`);
    } catch {
      /* leave the link if the file can't be read */
    }
  }
  return out;
}

await mkdir(WWW, { recursive: true });

let html = await readFile(SRC, 'utf8');
if (!html.includes('</body>')) {
  console.error(`No </body> in ${SRC} — aborting.`);
  process.exit(1);
}
html = await inlineCss(html);
const out = html.replace('</body>', JINJA_BOOT + '\n  </body>');
await writeFile(DEST, out, 'utf8');
console.log(`✓ crm → www/customer-relationship-management.html`);
