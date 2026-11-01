# Vault Galaxy

Visualização 3D (Three.js) do vault do Obsidian: cada nota é uma estrela, cada pasta de topo é uma
constelação com cor própria, e os links `[[...]]` são feixes de luz com partículas fluindo
na direção da citação.

O vault é lido em **modo somente leitura**.

## Rodar

```bash
cd ~/vault-galaxy
python3 build_graph.py /caminho/do/vault   # gera data/graph.json (ou defina VAULT_PATH)
python3 -m http.server 8777            # abrir http://localhost:8777
```

Para atualizar sozinho enquanto edita notas: `python3 build_graph.py --watch` (e recarregar a página).
Outro vault: `python3 build_graph.py /caminho/do/vault`.

## Interação

- Clique numa estrela: câmera voa até ela, painel com tags, resumo, **cita →** (ciano) e **← citada por** (magenta).
- Itens do painel navegam para a nota; tags filtram todas as notas com a tag.
- Duplo clique: abre a nota no Obsidian (`obsidian://`).
- `/` busca por título; `#tag` busca tags. `Esc` limpa.
- Legenda: clique esconde/mostra pasta, Alt+clique isola, duplo clique voa até a constelação.
- Opções: esconder órfãs, esconder links para notas inexistentes (cinza), rotação automática.

## Como os dados são extraídos

`build_graph.py` (só stdlib):
- Ignora `.obsidian`, `.trash`, `.git` e pastas ocultas.
- Links: `[[nota]]`, `[[nota|alias]]`, `[[nota#seção]]`, `![[embed]]` e `[txt](nota.md)`; anexos de imagem/PDF ignorados.
- Resolução como no Obsidian: caminho exato, senão nome do arquivo (caminho mais curto).
- Tags: `#tag` no corpo (fora de código) e `tags:` do frontmatter.
- Links para notas inexistentes viram nós cinza "(não criada)".

`data/graph.json` contém trechos das notas: não publique a pasta.

## Stack

Three.js 0.160 (InstancedMesh, LineSegments com gradiente, Points, UnrealBloom, CSS2DRenderer),
d3-force-3d para o layout (força de atração por pasta), sem build. Depende de CDN (unpkg/esm.sh).
