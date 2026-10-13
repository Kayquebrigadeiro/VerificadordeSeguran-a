# Homologação Final — 2026-10-12

## Ambiente
- Branch: `feat/stress-orchestration`
- Commit HEAD: `cdd7b0ed7ebbfa7bd950815382ebbe1bc36b06f5`
- venv: `/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv`
- Lab: `labctl.start()` → `http://127.0.0.1:8477`
- API: `127.0.0.1:8400`

## Resultado por parte

| Parte | Descrição | Resultado |
|---|---|---|
| A | Estado inicial | PASS |
| B | Suíte de testes | PASS — 255 passed, 3 skipped |
| C | Verificação passiva contra lab | PASS |
| D | Stress autorizado em loopback | PASS — 2 funcionais, 4 fail-closed |
| E | Bloqueio de alvo externo | PASS |
| F | Cancelamento via API | PASS — state=cancelled, órfãos=0 |
| G | Comparação de execuções | PASS — 3 runs persistidas; comparação automática indisponível |
| H | TUI interativa | PASS |

## Detalhes

### A — Estado inicial
```text
$ git branch --show-current
feat/stress-orchestration
$ git rev-parse HEAD | head -c 12
cdd7b0ed7ebb
$ git status --short
?? docs/HOMOLOGACAO_FINAL.md
$ ps aux | grep -E 'slowloris|ddoslayer|mhddos|impulse|overload|pyddos|ufonet|mikumi|verificalab' | grep -v grep | wc -l
0
```

### B — Suíte
Últimas 5 linhas:
```text
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================== warnings summary ===============================
SKIPPED [3] tests/test_adapters_all.py:179: ferramenta não requer root
================== 255 passed, 3 skipped, 1 warning in 41.31s ==================
```
Resultado: **255 passed, 3 skipped, 0 failed**.

### C — Verificação passiva
Saída:
```text
lab start: {'running': True, 'pid': 480393, 'endpoint': 'http://127.0.0.1:8477', 'managed_by': 'verificalab', 'message': 'lab iniciado'}
state: None
summary: 4 verificações executadas contra http://127.0.0.1:8477.
checks:
  ok200: pass — Status 200 conforme esperado.
  json: pass — 1 campo(s) conforme esperado.
  slow200: pass — Resposta em 2044ms dentro do limite.
  observacao_cabecalhos_configuracao: unknown — Conclusão contextualizada registrada em Achados: ausência de cabeçalho não é vulnerabilidade comprovada.
findings: 5
metrics: [{"value": 44.27811799905612, "unit": "ms", "samples": 3, "population": "requisi\u00e7\u00f5es conclu\u00eddas pelos checks (ida e volta observada pelo cliente VerificaLab)", "discarded": 0, "details": {"min_ms": 2.06, "max_ms": 2043.831, "mean_ms": 696.723, "p50_ms": 44.278, "p90_ms": 2043.831, "p95_ms": 2043.831, "p99_ms": 2043.831, "method": "nearest-rank sobre amostras conclu\u00eddas"}, "name
orfaos: 0
lab stop: {'running': False, 'pid': None, 'endpoint': 'http://127.0.0.1:8477', 'managed_by': None, 'message': 'lab encerrado'}
$ ps aux | grep -E "slowloris|ddoslayer|mhddos|impulse|overload|pyddos|ufonet|mikumi|verificalab" | grep -v grep | wc -l
0
```
- ok200: pass
- json: pass
- slow200: pass
- findings: 5

### D — Stress autorizado
| Ferramenta | Resultado | Observação |
|---|---|---|
| slowloris | ok | `run_id=stress_1a131ded1e43c6437fd161a0ec9`; execução passou e artefato foi criado |
| mikumikubeam | ok | `run_id=stress_1a131dee76a6cc25f2726117563`; execução passou e artefato foi criado |
| ddoslayer | fail-closed | `PermissionError: ddoslayer requer privilégios de root` |
| overload | fail-closed | `PermissionError: overload requer privilégios de root` |
| ufonet | fail-closed | `AdapterExecutionError: UFONet está catalogado para análise estática; execução de tráfego está desabilitada` |
| pyddos | fail-closed | `PermissionError: pyddos requer privilégios de root` |
| mhddos | não testado E2E | tentativa recusada: `PermissionError: mhddos requer privilégios de root`; `requires_root: true` |
| impulse | não testado E2E | tentativa recusada: `PermissionError: impulse requer privilégios de root`; `requires_root: true` |

Saída do resumo dos resultados:
```text
slowloris -> {'ok': True, 'run_id': 'stress_1a131ded1e43c6437fd161a0ec9'}
mikumikubeam -> {'ok': True, 'run_id': 'stress_1a131dee76a6cc25f2726117563'}
ddoslayer -> {'ok': False, 'run_id': 'stress_1a131defd5ef0151bf5afe11def'}
overload -> {'ok': False, 'run_id': 'stress_1a131defec15b935212d40cfa2c'}
ufonet -> {'ok': False, 'run_id': 'stress_1a131df0027c98b61f4aeb7bd12'}
pyddos -> {'ok': False, 'run_id': 'stress_1a131df01ac3c7398617ab24af4'}
mhddos -> {'ok': False, 'run_id': 'stress_1a131df0349c98d165995710d64'}
impulse -> {'ok': False, 'run_id': 'stress_1a131df04d03faade0d71e96a0b'}
ORFAOS: 0
lab stop: {'running': False, 'pid': None, 'endpoint': 'http://127.0.0.1:8477', 'managed_by': None, 'message': 'lab encerrado'}
$ ps aux | grep -E "slowloris|ddoslayer|mhddos|impulse|overload|pyddos|ufonet|mikumi|verificalab" | grep -v grep | wc -l
0
```

Artefatos gerados:
```text
$ ls -la data/artifacts/ | tail -10
drwx------  2 grekas grekas 4096 out 12 15:25 stress_1a1315d1b774e5959629cf0f13f
drwx------  2 grekas grekas 4096 out 12 15:38 stress_1a131689d8a531ca62e5bb3a014
drwx------  2 grekas grekas 4096 out 12 17:47 stress_1a131ded1e43c6437fd161a0ec9
drwx------  2 grekas grekas 4096 out 12 17:47 stress_1a131dee76a6cc25f2726117563
drwx------  2 grekas grekas 4096 out 12 17:47 stress_1a131defd5ef0151bf5afe11def
drwx------  2 grekas grekas 4096 out 12 17:47 stress_1a131defec15b935212d40cfa2c
drwx------  2 grekas grekas 4096 out 12 17:47 stress_1a131df0027c98b61f4aeb7bd12
drwx------  2 grekas grekas 4096 out 12 17:47 stress_1a131df01ac3c7398617ab24af4
drwx------  2 grekas grekas 4096 out 12 17:47 stress_1a131df0349c98d165995710d64
drwx------  2 grekas grekas 4096 out 12 17:47 stress_1a131df04d03faade0d71e96a0b
$ ls -la data/exports/ | tail -10
-rw------- 1 grekas grekas  690 out 12 17:47 stress_1a131df0027c98b61f4aeb7bd12.md
-rw------- 1 grekas grekas 1477 out 12 17:47 stress_1a131df01ac3c7398617ab24af4.html
-rw------- 1 grekas grekas 1153 out 12 17:47 stress_1a131df01ac3c7398617ab24af4.json
-rw------- 1 grekas grekas  690 out 12 17:47 stress_1a131df01ac3c7398617ab24af4.md
-rw------- 1 grekas grekas 1477 out 12 17:47 stress_1a131df0349c98d165995710d64.html
-rw------- 1 grekas grekas 1153 out 12 17:47 stress_1a131df0349c98d165995710d64.json
-rw------- 1 grekas grekas  690 out 12 17:47 stress_1a131df0349c98b61f4aeb7bd12.md
-rw------- 1 grekas grekas 1478 out 12 17:47 stress_1a131df04d03faade0d71e96a0b.html
-rw------- 1 grekas grekas 1157 out 12 17:47 stress_1a131df04d03faade0d71e96a0b.json
-rw------- 1 grekas grekas  691 out 12 17:47 stress_1a131df04d03faade0d71e96a0b.md
```
Órfãos após D: **0**.

### E — Bloqueio de alvo externo
- `require_authorization("example.com")` → `AuthorizationError`.
- `Orchestrator.plan("example.com", ["slowloris"])` → `AuthorizationError` antes de subprocess.
- órfãos: `0`.

Saída:
```text
OK bloqueou (direct): AuthorizationError
OK bloqueou (orchestrator): AuthorizationError
orfaos: 0
```

### F — Cancelamento via API
F1 executado via API/worker usando o fluxo de projeto, ambiente, perfil, run e endpoint de cancelamento. Saída bruta:
```text
lab start: {'running': True, 'pid': 522245, 'endpoint': 'http://127.0.0.1:8477', 'managed_by': 'verificalab', 'message': 'lab iniciado'}
project: prj_1a131eabf2495d22683c3a48e8d
environment: env_1a131eabfd282bc92d9713adeec
profile load: prf_1a131eac04b4116e78cc4f58294
run criada: run_1a131eac0bcaa93c5f70a2dd342 state: queued
state antes do cancel: running
POST cancel -> 200 {'status': 'cancelling', 'message': 'cancelamento solicitado; aguardando interrupção'}
final state: cancelled
final summary: Cancelado após 0 tentativas (cancelamento solicitado).
orfaos de stress: 0
linha no DB: ('run_1a131eac0bcaa93c5f70a2dd342', 'cancelled', 'Cancelado após 0 tentativas (cancelamento solicitado).')
lab stop: {'running': False, 'pid': None, 'endpoint': 'http://127.0.0.1:8477', 'managed_by': None, 'message': 'lab encerrado'}
orfaos finais: 0
```
- run criada: `run_1a131eac0bcaa93c5f70a2dd342`
- state antes do cancel: `running`
- POST cancel: `200`, status `cancelling`
- final state e DB: `cancelled`
- órfãos finais: `0`

### G — Comparação
Três runs slowloris foram concluídas com sucesso:
```text
run 0: run_id=stress_1a131df9198b9951406b9ae4c31, ok=True
run 1: run_id=stress_1a131dfa738e326446c78ecd42f, ok=True
run 2: run_id=stress_1a131dfbc71bdc9447211ad1599, ok=True
tabelas: ['schema_migrations', 'projects', 'environments', 'tools', 'test_profiles', 'runs', 'run_events', 'sqlite_sequence', 'check_results', 'metrics', 'findings', 'artifacts', 'audit_events', 'log_entries', 'imports']
runs cols: ['id', 'project_id', 'environment_id', 'profile_id', 'kind', 'state', 'queued_at', 'started_at', 'finished_at', 'cancel_requested', 'exit_code', 'tool_version', 'config_json', 'summary', 'error_detail', 'progress', 'interrupted_reason', 'tool_id', 'target', 'ended_at', 'returncode', 'ok', 'orchestrator_id']
comparação disponível: nenhuma
lab stop: {'running': False, 'pid': None, 'endpoint': 'http://127.0.0.1:8477', 'managed_by': None, 'message': 'lab encerrado'}
```
Runs persistidas com timestamps distintos; não há função automática de comparação no `Orchestrator`.

### H — TUI
Interação em pseudo-terminal: navegação com seta para baixo atualizou a seleção/painel lateral; `q` encerrou com código 0. Dump:
```text
│  DDoSlayer (ddoslayer)                        │
│  Descrição                                    │
│   Framework interativo com métodos HTTP,      │
│   conexões lentas e opções de camada de rede  │
│   que usam pacotes raw. Exige revisão do      │
│   método escolhido antes de qualquer teste.   │
│  Quando usar                                  │
│   Apenas para testes autorizados e isolados   │
│   no laboratório local, escolhendo HTTP e     │
│   mantendo duração e threads nos limites      │
│   abaixo.                                     │
│  Exemplo                                      │
│   python3 ddoslayer/DDoSlayer.py              │
│  Riscos                                       │
│   • Métodos SYN e UDP podem exigir            │
│   privilégios elevados e afetar redes.        │
│   • A interface interativa não aplica os      │
│   limites do VerificaLab.                     │
│  Limites padrão                               │
│   5s · 1 thread(s) · rate limit low           │
╰───────────────────────────────────────────────╯
```
- 8 ferramentas listadas: slowloris, mikumikubeam, ddoslayer, overload, ufonet, pyddos, mhddos, impulse.
- navegação funciona; painel exibe descrição, quando usar, exemplo, riscos e limites.
- `q` sai com código 0.
- Dump textual completo: `/tmp/homolog4_H_pty.raw`.

## Pendências conhecidas (não bloqueantes)

1. **ddoslayer, overload, ufonet e pyddos** — recusas explícitas/fail-closed confirmadas.
2. **mhddos e impulse** — `requires_root: true`; não executados E2E sem privilégios elevados.
3. **MikuMikuBeam** — executou com sucesso. O formato de importação permanece não homologado (somente stream), conforme limitação documentada.
4. **Frontend React** — a UI web não tem tela de stress test; acesso às ferramentas de stress é via TUI e Orchestrator programático.
5. **Comparação automática** — as três execuções foram persistidas, mas não foi encontrada função de comparação no `Orchestrator`.

## Riscos residuais

- O `Orchestrator` é síncrono e não expõe cancelamento; cancelamento de runs de perfil é feito pela API/worker. O fluxo API foi confirmado com estado final `cancelled` e zero órfãos.
- O gate de autorização do Orchestrator só libera loopback literal; alvos externos exigem `authorization.json` assinado.

## Veredito

**HOMOLOGADO para uso em loopback**, com pendências conhecidas documentadas. A autorização de alvos externos foi verificada como bloqueio sem autorização válida; uso externo depende de `authorization.json` válido.
