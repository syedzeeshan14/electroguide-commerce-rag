"""Development-only read API, bound to localhost. No checkout or authentication yet."""
import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from app.catalog import Catalog

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/health':
            return self.respond(200, {'status':'ok','mode':'synthetic-local-baseline'})
        if url.path != '/products':
            return self.respond(404, {'error':'Not found'})
        args = parse_qs(url.query)
        def value(key, default=None):
            return args.get(key, [default])[0]
        try:
            price = float(value('max_price')) if value('max_price') is not None else None
            if price is not None and not math.isfinite(price):
                raise ValueError('max_price must be finite')
            products = self.catalog.search(query=value('q',''), category=value('category'), max_price=price, limit=int(value('limit',10)))
            return self.respond(200, {'products':products, 'count':len(products), 'synthetic':True,'retrieval':'lexical-fts5'})
        except (ValueError, OverflowError):
            return self.respond(400, {'error':'Invalid numeric filter'})

    def respond(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == '__main__':
    Handler.catalog = Catalog()
    print('Local catalog API: http://127.0.0.1:8000', flush=True)
    HTTPServer(('127.0.0.1',8000),Handler).serve_forever()
