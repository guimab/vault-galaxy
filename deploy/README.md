# Deploy no cluster (k3s)

O repo é a **fonte única**: o kustomize da raiz gera os ConfigMaps a partir do `index.html`,
do `build_graph.py` e do `nginx.conf` daqui, com hash no nome. Editar qualquer um desses
arquivos e dar `kubectl apply -k .` (ou deixar o Argo CD sincronizar) já coloca a versão nova
no ar — o hash muda, o Deployment muda e o pod roda.

## Arquitetura

Um PVC (`vault-galaxy-data`, 5Gi, Longhorn) com três pastas, um pod com três containers e um
Ingress só de LAN:

    /data/vault   clone do vault (espelho)   <- container `sync`  (ob sync --continuous)
    /data/config  estado do cliente headless <- container `sync`  (XDG_CONFIG_HOME)
    /data/www     index.html + graph.json    <- `indexer` (gera) e `web` (serve)

- `sync` — imagem `ghcr.io/guimab/vault-galaxy-sync` (`Dockerfile.sync`), cliente oficial
  Obsidian Headless (`obsidian-headless`). Primeiro start: `ob sync-setup` →
  `ob sync-config --mode pull-only` → `ob sync --continuous`. **O cluster nunca escreve no
  vault** (`--mode` é do `sync-config`, não do `sync-setup`).
- `indexer` — `python:3.12-slim` rodando `build_graph.py /data/vault --watch`.
- `web` — `nginx:1.27-alpine` servindo `/data/www`, sem cache no `graph.json`.

## O que é específico do cluster (não está no repo)

O repo é público, então dado pessoal não entra nele. O que é do cluster vive em
`Overnit/vault-galaxy-cluster` (privado), aplicado pela Application `vault-galaxy-cluster`:

1. **Nome do vault** — ConfigMap `vault-galaxy-env` (modelo em
   `examples/vault-galaxy-env.example.yaml`). Sem ele o container `sync` não sobe.

2. **Credenciais do Obsidian Sync** — Secret `obsidian-sync` com as chaves `auth_token` e
   `encryption_password`, criado fora do git (nunca por Argo CD). O token sai do `ob login`;
   grave a senha E2E num arquivo seu e deixe o kubectl ler dele:

       docker run --rm -it -v /root/ob-login:/data/config \
         -e XDG_CONFIG_HOME=/data/config ghcr.io/guimab/vault-galaxy-sync:0.0.14 ob login

       printf '%s' 'SUA_SENHA_E2E' > /root/ob-e2e.txt && chmod 600 /root/ob-e2e.txt

       kubectl -n vault-galaxy create secret generic obsidian-sync \
         --from-file=auth_token=/root/ob-login/obsidian-headless/auth_token \
         --from-file=encryption_password=/root/ob-e2e.txt

   O pod tira newline dos dois valores, então `--from-file` é seguro. Apague os arquivos depois:
   o mesmo token pode ser relido do Secret com
   `kubectl -n vault-galaxy get secret obsidian-sync -o jsonpath='{.data.auth_token}' | base64 -d`.

## DNS e acesso

`vault-galaxy.local` e `vault-galaxy.lan` apontam para o VIP do kube-vip, servido pelo traefik
(registros estáticos no MikroTik; clientes DHCP usam o roteador como DNS). O Ingress responde
pelos dois nomes porque macOS/iOS tratam `.local` como mDNS. **Por IP não responde** (o Ingress
é por Host) — o que é bom: o `graph.json` tem trechos das notas.

## Atualizar a imagem do cliente headless

O `obsidian-headless` é a única peça que não é arquivo. Ao mudar `OB_VERSION` no
`Dockerfile.sync`, o workflow `.github/workflows/image.yaml` publica
`ghcr.io/guimab/vault-galaxy-sync:<versão>` e o Deployment usa essa tag (ajuste-a junto).
Sem registry no cluster, os nós puxam do GHCR.

## Argo CD

Duas Applications no projeto `vault-galaxy`, cada uma dona da sua parte:

| Application | Fonte | Entrega |
| --- | --- | --- |
| `vault-galaxy` | repo público, path `.` | Namespace, PVC, Deployment, Service, Ingress e os ConfigMaps do site |
| `vault-galaxy-cluster` | `Overnit/vault-galaxy-cluster` (privado) | ConfigMap `vault-galaxy-env` (nome do vault) |

Ambas com sync automático (`prune` + `selfHeal`). Separadas de propósito: se o overlay privado
fosse a única fonte, uma mudança no repo público só apareceria depois de um commit no overlay.
O que o Argo não gerencia (Secret `obsidian-sync`) nunca é podado.

Os manifestos das Applications ficam aqui em `argocd/` e são aplicados uma vez:

    kubectl apply -f deploy/argocd/

## Operação

    kubectl -n vault-galaxy logs deploy/vault-galaxy -c sync -f
    kubectl -n vault-galaxy logs deploy/vault-galaxy -c indexer -f
    kubectl -n vault-galaxy exec deploy/vault-galaxy -c sync -- \
      sh -c 'XDG_CONFIG_HOME=/data/config ob sync-status --path /data/vault'

Reler após editar arquivo no cluster: `kubectl delete -k . && kubectl apply -k .` só é
necessário se um ConfigMap antigo ficar órfão; o normal é o hash cuidar de tudo.

Recomeçar o sync do zero: apagar `/data/config/obsidian-headless/sync` dentro do PVC.
