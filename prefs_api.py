#!/usr/bin/env python3
"""Preferências da interface, compartilhadas entre dispositivos.

Um JSON por vault, guardado no volume de dados (ao lado do graph.json), servido
em /api/prefs e proxiado pelo nginx. Assim o ajuste fino (brilho, física, cores
das pastas, pastas escondidas, caixas de opção) vale no celular e no desktop, sem
conta e sem login — o site é de um dono só, dentro da rede.

Rotas:
  GET  /api/prefs        -> {"version": n, "updated": ts, "device": "...", "cfg": {...}, ...}
  PUT  /api/prefs        -> corpo {"device": "...", "cfg": {...}, "hidden": [...], ...}
                            grava e devolve o documento novo (version + 1)

Só stdlib. Escrita atômica (arquivo temporário + rename): outro device nunca lê
JSON pela metade.
"""
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FILE = Path(os.environ.get('PREFS_FILE', '/data/prefs.json'))
PORT = int(os.environ.get('PREFS_PORT', '8791'))
HOST = os.environ.get('PREFS_HOST', '127.0.0.1')
MAX_BODY = 64 * 1024
CAMPOS = ('cfg', 'hidden', 'showOrph', 'showGhost', 'autoRotate')

_locks = threading.Lock()


def _vazio():
    return {'version': 0, 'updated': 0, 'device': None, 'cfg': {}, 'hidden': []}


def ler():
    try:
        doc = json.loads(FILE.read_text(encoding='utf-8'))
        return doc if isinstance(doc, dict) else _vazio()
    except FileNotFoundError:
        return _vazio()
    except Exception as e:  # arquivo corrompido não derruba a API
        print(f'prefs: arquivo ilegível ({e.__class__.__name__}), recomeçando', flush=True)
        return _vazio()


def gravar(doc):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(FILE.parent), prefix='.prefs-', suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, FILE)


class Handler(BaseHTTPRequestHandler):
    server_version = 'vault-galaxy-prefs'
    protocol_version = 'HTTP/1.1'

    def _responder(self, codigo, corpo):
        dados = corpo.encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(dados)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(dados)

    def _rota(self):
        return self.path.split('?', 1)[0].rstrip('/') or '/'

    def do_GET(self):
        if self._rota() not in ('/api/prefs', '/'):
            return self._responder(404, '{"erro":"rota desconhecida"}')
        with _locks:
            doc = ler()
        self._responder(200, json.dumps(doc, ensure_ascii=False))

    def do_PUT(self):
        if self._rota() != '/api/prefs':
            return self._responder(404, '{"erro":"rota desconhecida"}')
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_BODY:
            return self._responder(413, '{"erro":"corpo vazio ou grande demais"}')
        try:
            payload = json.loads(self.rfile.read(n).decode('utf-8'))
            if not isinstance(payload, dict):
                raise ValueError
        except Exception:
            return self._responder(400, '{"erro":"json invalido"}')
        with _locks:
            doc = ler()
            novo = {'version': int(doc.get('version', 0)) + 1, 'updated': int(time.time()),
                    'device': str(payload.get('device') or '')[:48]}
            for campo in CAMPOS:
                if campo in payload:
                    novo[campo] = payload[campo]
                elif campo in doc:            # não apaga o que o cliente não mandou
                    novo[campo] = doc[campo]
            gravar(novo)
        print(f"prefs: v{novo['version']} de {novo['device']!r}", flush=True)
        self._responder(200, json.dumps(novo, ensure_ascii=False))

    def do_POST(self):
        self.do_PUT()

    def log_message(self, format, *args):            # sem ruído no log do pod
        pass


if __name__ == '__main__':
    print(f'prefs: ouvindo em {HOST}:{PORT}, arquivo {FILE}', flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
