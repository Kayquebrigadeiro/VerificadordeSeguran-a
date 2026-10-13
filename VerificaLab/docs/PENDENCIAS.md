# Pendências e Limitações — VerificaLab

> Este documento separa **bugs** de **limitações conhecidas** de
> **trabalho futuro**. Se algo não funciona, verifique aqui antes
> de abrir sprint de correção.

## 1. Ferramentas que não executam (por design)

### 1.1 Fail-closed (upstream limita)

Ferramentas que recusam executar por limitações do próprio upstream ou
porque o adapter não consegue garantir execução restrita. Não é bug do
VerificaLab: a recusa é o comportamento seguro esperado.

| Ferramenta | Motivo | Mensagem observada |
|---|---|---|
| ddoslayer | A execução disponível é interativa e requer privilégios de root; o adapter não inicia a interface sem controle dos parâmetros. | `PermissionError: ddoslayer requer privilégios de root` |
| overload | A execução disponível é interativa e requer privilégios de root; o projeto também está arquivado. | `PermissionError: overload requer privilégios de root` |
| ufonet | Catalogado somente para análise estática; tráfego, amplificação e recursos distribuídos estão desabilitados. | `AdapterExecutionError: UFONet está catalogado para análise estática; execução de tráfego está desabilitada` |

Fonte: `docs/HOMOLOGACAO_FINAL.md`, parte D; motivos complementares:
`docs/SPRINTS.md`, Sprint 6.

### 1.2 Requer root (fora do escopo do piloto)

| Ferramenta | Motivo | Como testar (futuro) |
|---|---|---|
| mhddos | `requires_root: true`; a tentativa foi recusada antes de uma execução E2E. | VM isolada, método HTTP revisado e autorização explícita; avaliar privilégios somente se indispensáveis. |
| impulse | `requires_root: true`; a tentativa foi recusada antes de uma execução E2E. | VM isolada, método HTTP revisado e autorização explícita; avaliar privilégios somente se indispensáveis. |

## 2. Lacunas conhecidas (não bloqueantes)

### 2.1 Orchestrator sem cancelamento — RESOLVIDO (Sprint 9)

- **Resolvido em**: 2026-10-12, via `Orchestrator.cancel(run_id)`.
- **Como funciona**: delega a `Worker.request_cancel()`; instancie o
  `Orchestrator` com o mesmo worker que gerencia a execução.

### 2.2 MikuMikuBeam sem importador

- **O que é**: as estatísticas de execução são expostas como stream; não há
  formato de arquivo exportável homologado para importação.
- **Impacto**: não é possível importar relatórios dessa ferramenta.
- **Status**: Sprint 11 planejado, caso o formato seja confirmado.

### 2.3 Frontend sem tela de stress

- **O que é**: a UI React cobre verificações passivas, execuções e relatórios,
  mas não oferece uma tela para selecionar ferramentas de stress.
- **Impacto**: o acesso às execuções de stress é pela TUI ou pelo
  `Orchestrator` programático.
- **Status**: Sprint 12 planejado; não urgente.

### 2.4 Alvos externos exigem autorização

- **O que é**: o gate `require_authorization()` libera loopback; qualquer outro
  alvo exige `data/secrets/authorization.json` com `target`, `owner`, `reason`
  e `expires_at` válidos.
- **Impacto**: um alvo externo só pode ser testado após criar uma autorização
  válida, correspondente ao alvo e dentro da validade.
- **Status**: por design. Não vai mudar.

## 3. Trabalho futuro (sprints 10–12, opcionais)

| Sprint | Escopo | Risco |
|---|---|---|
| 10 | MHDDoS/Impulse com sudo em VM isolada | ALTO |
| 11 | Importador MikuMikuBeam | baixo |
| 12 | Tela de stress no frontend React | baixo |

## 4. Como saber se algo é bug

- **É bug** se: uma ferramenta homologada para execução (Slowloris ou
  MikuMikuBeam) não funciona no cenário autorizado; o gate libera alvo externo
  sem autorização válida; um subprocesso fica órfão; ou um teste da suíte falha.
- **NÃO é bug** se: uma ferramenta fail-closed recusa; um teste `requires_root`
  é skipado; o `Orchestrator` não cancela diretamente (limitação registrada
  acima); HSTS está ausente em HTTP (é esperado).

## 5. Estado da suíte

- Resultado da homologação: 255 passed, 3 skipped, 1 warning preexistente
  (Starlette/httpx).
- Comando: `.venv/bin/python -m pytest backend/tests -o addopts='' -ra`

## 6. Estado da branch

- Branch homologada: `master`.
- HEAD no momento da consolidação documental: `96209bb1e284f0fd017b2df2aac3a280c1b7e683`.

### 1.2 Ferramentas funcionais (atualizado v0.2.2)

| Ferramenta | Camada | Modo |
|---|---|---|
| slowloris | L7 | conexões incompletas |
| mikumikubeam | L7 | HTTP flood em Go |
| pyddos | L7 | HTTP flood com rotação de User-Agent |

O pyddos foi habilitado em v0.2.2 após correção do `buffer()`,
instalação de dependências no venv, correção de cwd e suporte a
porta no modo `-Request`. Ver commit `eaae25e`.
