# Changelog — VerificaLab

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento: [SemVer](https://semver.org/lang/pt-BR/).

## [0.2.0] — 2026-10-12 — Stress orchestration

### Adicionado
- Gate de autorização obrigatório (`require_authorization`): libera loopback,
  exige `authorization.json` para alvos externos.
- Registry declarativo de ferramentas (`config/tools.yaml` +
  `stress/registry.py`).
- Runner seguro de subprocessos com kill-tree (`core/runner.py`).
- 8 adapters de ferramentas de stress (slowloris, mikumikubeam, ddoslayer,
  overload, ufonet, pyddos, mhddos, impulse).
- Orchestrator com persistência SQLite e relatórios JSON/MD/HTML
  (`core/orchestrator.py`, `core/report.py`).
- TUI Textual com painel de ferramentas e execução em loopback.
- `Orchestrator.cancel(run_id)` delegando a `Worker.request_cancel()`.

### Documentação
- `docs/PENDENCIAS.md` — bugs vs limitações vs trabalho futuro.
- `docs/GUIA_DE_USO.md` — como usar na prática.
- `docs/HOMOLOGACAO_FINAL.md` — resultado da homologação (8 partes).
- `docs/SPRINTS.md` — histórico de desenvolvimento.
- `docs/STRESS_ORCHESTRATION.md` — arquitetura da orquestração.

### Segurança
- Alvos externos exigem autorização válida em `authorization.json`.
- Adapters limitam duração e threads aos valores de `tools.yaml`.
- Ferramentas com `requires_root: true` recusam sem privilégio.
- UFONet está catalogado apenas para análise estática.

### Homologação
- A: estado inicial — PASS
- B: suíte — 258 passed, 3 skipped
- C: verificação passiva — PASS
- D: stress autorizado — PASS (2 funcionais; 6 recusam ou não foram
  homologadas para execução E2E por design/requisito de root)
- E: bloqueio de alvo externo sem autorização válida — PASS
- F: cancelamento via API — PASS
- G: comparação de execuções — três runs persistidas; comparação automática
  indisponível
- H: TUI interativa — PASS
- Sprint 9: `Orchestrator.cancel()` delega ao Worker; testes e cancelamento
  E2E de uma execução gerenciada pelo Worker aprovados.

### Limitações conhecidas
Consulte `docs/PENDENCIAS.md`. Resumo:
- 4 ferramentas fail-closed (ddoslayer, overload, ufonet, pyddos).
- 2 ferramentas `requires_root` (mhddos, impulse), sem homologação E2E.
- MikuMikuBeam sem importador de relatório homologado.
- Frontend sem tela de stress test.
- `Orchestrator.run()` é síncrono; `Orchestrator.cancel()` delega ao Worker e
  cancela runs que esse Worker gerencia; não interrompe diretamente uma
  execução síncrona iniciada por `Orchestrator.run()`.

## [0.1.0] — anterior
- Versão piloto: verificação passiva, carga leve, suíte pytest,
  importadores JUnit/JSON, correlação de logs e frontend React.
