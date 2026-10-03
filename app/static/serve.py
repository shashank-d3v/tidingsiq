"""Loopback-only static preview with gzip negotiation. No database or API access."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class Handler(SimpleHTTPRequestHandler):
    def list_directory(self, path):
        self.send_error(404)
        return None

    def send_head(self):
        path = Path(self.translate_path(self.path)).resolve()
        if not path.is_relative_to(ROOT) or path.suffix in {'.py', '.mjs'} and 'tests' in path.parts:
            self.send_error(404)
            return None
        if path.suffix == '.py':
            self.send_error(404)
            return None
        encodings = self.headers.get('Accept-Encoding', '')
        gzip_ok = any(part.strip().split(';')[0] == 'gzip' and not any(
            param.strip().startswith('q=') and float(param.strip()[2:]) == 0
            for param in part.split(';')[1:]) for part in encodings.split(','))
        zipped = Path(str(path) + '.gz')
        if path.is_file() and gzip_ok and zipped.is_file():
            self.send_response(200)
            self.send_header('Content-Type', self.guess_type(str(path)))
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Content-Length', str(zipped.stat().st_size))
            self.end_headers()
            return zipped.open('rb')
        return super().send_head()

    def end_headers(self):
        self.send_header('Vary', 'Accept-Encoding')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        super().end_headers()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4173)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(ROOT)))
    print(f'TidingsIQ local preview: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()
