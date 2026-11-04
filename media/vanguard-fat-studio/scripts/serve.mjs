import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { stat, realpath } from 'node:fs/promises';
import { resolve, sep, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

export const studioRoot = fileURLToPath(new URL('../', import.meta.url));
const types = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf',
  '.mp4': 'video/mp4', '.wav': 'audio/wav',
};

/** Serve only this isolated project on the loopback interface. */
export async function startServer({ port = 4173 } = {}) {
  const root = await realpath(studioRoot);
  const server = createServer(async (req, res) => {
    try {
      if (!['GET', 'HEAD'].includes(req.method)) {
        res.writeHead(405, { Allow: 'GET, HEAD' }); res.end(); return;
      }
      const url = new URL(req.url, 'http://127.0.0.1');
      const pathname = decodeURIComponent(url.pathname);
      const relative = pathname === '/' ? 'index.html' : pathname.slice(1);
      const segments = relative.split('/');
      if (segments.some(s => s.startsWith('.') || s === 'node_modules') || relative.includes('\\')) {
        res.writeHead(403); res.end('Forbidden'); return;
      }
      const file = resolve(root, relative);
      if (!file.startsWith(root + sep)) { res.writeHead(403); res.end('Forbidden'); return; }
      const actual = await realpath(file);
      if (!actual.startsWith(root + sep)) { res.writeHead(403); res.end('Forbidden'); return; }
      const info = await stat(actual);
      if (!info.isFile()) { res.writeHead(404); res.end('Not found'); return; }
      const headers = {
        'Content-Type': types[extname(file).toLowerCase()] ?? 'application/octet-stream',
        'Content-Length': info.size, 'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
      };
      const range = req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
      if (range) {
        const start = Number(range[1]);
        const end = Math.min(range[2] ? Number(range[2]) : info.size - 1, info.size - 1);
        if (start > end || start >= info.size) {
          res.writeHead(416, { 'Content-Range': `bytes */${info.size}` }); res.end(); return;
        }
        res.writeHead(206, { ...headers, 'Content-Length': end - start + 1,
          'Content-Range': `bytes ${start}-${end}/${info.size}`, 'Accept-Ranges': 'bytes' });
        if (req.method === 'HEAD') { res.end(); return; }
        createReadStream(actual, { start, end }).on('error', () => res.destroy()).pipe(res);
      } else {
        res.writeHead(200, { ...headers, 'Accept-Ranges': 'bytes' });
        if (req.method === 'HEAD') { res.end(); return; }
        createReadStream(actual).on('error', () => res.destroy()).pipe(res);
      }
    } catch (error) {
      const code = error.code === 'ENOENT' ? 404 : error instanceof URIError ? 400 : 500;
      if (!res.headersSent) res.writeHead(code);
      res.end(code === 404 ? 'Not found' : 'Unable to serve local file');
    }
  });
  await new Promise((accept, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', accept);
  });
  return {
    url: `http://127.0.0.1:${server.address().port}`,
    close: () => new Promise((accept, reject) => {
      server.closeAllConnections(); server.close(error => error ? reject(error) : accept());
    }),
  };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const server = await startServer({ port: Number(process.env.MOTION_PORT ?? 4173) });
    console.log(`Motion preview: ${server.url}`);
    const stop = async () => { await server.close(); process.exit(0); };
    process.once('SIGINT', stop); process.once('SIGTERM', stop);
  } catch (error) {
    console.error(error.message); process.exitCode = 1;
  }
}
