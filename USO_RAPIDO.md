# Uso Rápido — VerificadordeSegurança

## Diário

```bash
cd ~/Projetos/VerificadordeSegurança
make test      # valida o projeto (258 passed)
make serve     # API + laboratório em loopback
make tui       # painel interativo de ferramentas
make help      # lista todos os targets
```

## Estrutura

- 8 ferramentas de stress test na raiz (slowloris/, ddoslayer/, etc.)
- VerificaLab/ — plataforma de orquestração (backend + frontend + docs)
- bootstrap.sh / Makefile — automação

## Documentação

- VerificaLab/docs/GUIA_DE_USO.md — como usar na prática
- VerificaLab/docs/PENDENCIAS.md — o que não funciona e por quê
- VerificaLab/docs/HOMOLOGACAO_FINAL.md — resultado da homologação
- VerificaLab/docs/STRESS_ORCHESTRATION.md — arquitetura

## Aviso legal

Use apenas contra sistemas próprios ou com autorização escrita.
Alvos externos exigem authorization.json assinado.

## Backup

- /tmp/VerificadordeSeguranca-backup-20261012-2045.tar.gz
- Não há remote. Para cópia off-machine, salve este tarball em HD
  externo ou serviço de sua escolha.
