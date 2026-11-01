# Manifestos de deploy (exemplo)

O site e o indexador são estáticos: o kustomize da **raiz** transforma o `index.html`, o
`build_graph.py` e o `deploy/nginx.conf` em ConfigMaps (com hash no nome), e o Deployment monta um
pod com três containers:

| container | o que faz | precisa de |
| --- | --- | --- |
| `sync` | cliente headless do Obsidian Sync (`Dockerfile.sync`), só baixa: `pull-only` | credencial do Obsidian Sync |
| `indexer` | roda `build_graph.py <vault> --watch` e escreve `data/graph.json` | o clone do vault |
| `web` | nginx servindo `index.html` + `data/graph.json` | nada além dos arquivos |

    kubectl apply -k .        # da raiz do repo

Como o hash do ConfigMap entra no nome, editar `index.html` ou `build_graph.py` e reaplicar já faz
o pod rodar a versão nova — não existe passo de "regerar ConfigMap".

Os containers são independentes: quem só quer servir um `graph.json` que já tem na mão usa apenas
o `web`; quem quer o espelho do vault precisa também do `sync` (ou aponta o `indexer` para um
diretório do próprio PVC, por exemplo um volume NFS).

## O que você precisa providenciar

Cada um destes depende do seu ambiente, então não vêm no repo:

- **Storage**: o PVC pede 5Gi com `storageClassName: longhorn` — troque pela sua StorageClass.
- **ConfigMap `vault-galaxy-env`, chave `VAULT_NAME`**: o nome do vault. É ele que volta ao
  `graph.json`, e o duplo clique `obsidian://` no site precisa dele.
- **Secret `obsidian-sync`**: `auth_token` (saída do `ob login` do `obsidian-headless`) e, se o
  vault usa criptografia ponta a ponta, `encryption_password`. O pod tira newline dos valores, então
  `--from-file` funciona.
- **Exposição**: o `deploy/service.yaml` é um ClusterIP; escreva o Ingress/NodePort do seu ambiente.

## Atualizar a imagem do cliente headless

O `obsidian-headless` é a única peça que não é arquivo. Ao mudar `OB_VERSION` no `Dockerfile.sync`,
o workflow `.github/workflows/image.yaml` publica `ghcr.io/<owner>/vault-galaxy-sync:<versão>` no
GHCR; aponte a tag no `deploy/deployment.yaml` junto.
