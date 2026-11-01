#!/usr/bin/env python3
"""Lê o vault do Obsidian (somente leitura) e gera data/graph.json.

Uso:
  python3 build_graph.py [CAMINHO_DO_VAULT]          # gera uma vez
  python3 build_graph.py [CAMINHO_DO_VAULT] --watch  # regera quando notas mudam
"""
import json, os, re, sys, time
from pathlib import Path

_arg = next((a for a in sys.argv[1:] if not a.startswith('--')), None) or os.environ.get('VAULT_PATH')
if not _arg:
    sys.exit('Informe o caminho do vault: python3 build_graph.py /caminho/do/vault  (ou defina VAULT_PATH)')
VAULT = Path(_arg).expanduser()
OUT = Path(__file__).parent / 'data' / 'graph.json'
SKIP_DIRS = {'.obsidian', '.trash', '.git', 'node_modules'}

WIKI = re.compile(r'!?\[\[([^\]\|#\^]+)(?:[#\^][^\]\|]*)?(?:\|[^\]]*)?\]\]')
MDLINK = re.compile(r'\[[^\]]*\]\((?!https?:|mailto:|obsidian:)([^)#\s]+\.md)(?:#[^)]*)?\)')
TAG = re.compile(r'(?<![\w/&#])#([A-Za-zÀ-ÿ0-9_\-/]*[A-Za-zÀ-ÿ_\-/][A-Za-zÀ-ÿ0-9_\-/]*)')
FM = re.compile(r'^---\n(.*?)\n---\n?', re.S)
CODE = re.compile(r'```.*?```|`[^`\n]*`', re.S)


def notes():
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        for f in files:
            if f.endswith('.md'):
                yield Path(root) / f


def fm_tags(fm: str):
    tags = []
    m = re.search(r'^tags:[ \t]*(.*)$', fm, re.M)
    if not m:
        return tags
    inline = m.group(1).strip()
    if inline:
        tags += [t.strip(' "\'#') for t in inline.strip('[]').split(',') if t.strip(' "\'#')]
    else:
        tail = fm[m.end():]
        for line in tail.splitlines():
            lm = re.match(r'^\s*-\s*(.+)$', line)
            if not lm:
                break
            tags.append(lm.group(1).strip(' "\'#'))
    return tags


def build():
    paths = sorted(notes())
    by_rel = {p.relative_to(VAULT).with_suffix('').as_posix(): p for p in paths}
    by_name = {}
    for rel in by_rel:
        by_name.setdefault(Path(rel).name.lower(), []).append(rel)

    def resolve(target: str):
        t = target.strip().removesuffix('.md')
        if t in by_rel:
            return t
        cands = by_name.get(Path(t).name.lower(), [])
        if not cands:
            return None
        # Obsidian: prefere o caminho mais curto / que termina com o alvo
        cands = sorted(cands, key=lambda r: (not r.lower().endswith(t.lower()), len(r)))
        return cands[0]

    nodes, links, ghosts = {}, {}, {}
    for rel, p in by_rel.items():
        try:
            text = p.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        fm = FM.match(text)
        body = text[fm.end():] if fm else text
        clean = CODE.sub('', body)
        tags = set(fm_tags(fm.group(1)) if fm else [])
        tags |= {t.rstrip('/') for t in TAG.findall(clean)}
        parts = rel.split('/')
        excerpt = re.sub(r'\s+', ' ', re.sub(r'[#>*_`\[\]]', '', clean)).strip()[:280]
        st = p.stat()
        nodes[rel] = dict(id=rel, title=parts[-1], group=parts[0] if len(parts) > 1 else '(raiz)',
                          folder='/'.join(parts[:-1]), tags=sorted(t for t in tags if t),
                          words=len(clean.split()), mtime=int(st.st_mtime), excerpt=excerpt)
        targets = [m for m in WIKI.findall(clean)] + [m for m in MDLINK.findall(clean)]
        for t in targets:
            if re.search(r'\.(png|jpe?g|gif|svg|pdf|webp|excalidraw)$', t, re.I):
                continue
            dst = resolve(t)
            if dst is None:
                g = 'ghost:' + Path(t).name
                ghosts[g] = dict(id=g, title=Path(t).name, group='(não criada)', folder='', tags=[],
                                 words=0, mtime=0, excerpt='Nota referenciada mas inexistente.', ghost=True)
                dst = g
            if dst == rel:
                continue
            key = (rel, dst)
            links[key] = links.get(key, 0) + 1

    nodes.update(ghosts)
    data = dict(vault=os.environ.get('VAULT_NAME') or VAULT.name,
                generated=int(time.time()),
                nodes=list(nodes.values()),
                links=[dict(source=s, target=t, weight=w) for (s, t), w in links.items()])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    real = len(nodes) - len(ghosts)
    print(f'{real} notas, {len(ghosts)} não criadas, {len(links)} ligações -> {OUT}')


def snapshot():
    return {str(p): p.stat().st_mtime for p in notes()}


if __name__ == '__main__':
    if not VAULT.is_dir():
        sys.exit(f'Vault não encontrado: {VAULT}')
    build()
    if '--watch' in sys.argv:
        last = snapshot()
        print('Observando alterações (Ctrl+C para sair)...')
        while True:
            time.sleep(2)
            cur = snapshot()
            if cur != last:
                last = cur
                build()
