0-Sprint 0 concluído: a branch está ativa, os arquivos novos foram criados sem modificar o catálogo, e a suíte passou com 87 testes.

Saída de  pytest backend/tests -q :

........................................................................ [ 82%]
...............                                                          [100%]

Para confirmar a contagem, a execução com resumo explícito retornou:

........................................................................ [ 82%]
...............                                                          [100%]
87 passed in 23.79s

Saída de  git status --short :

?? backend/config/
?? backend/verificalab/core/
?? backend/verificalab/stress/
?? backend/verificalab/tui/
?? docs/SPRINTS.md

Saída de  git branch --show-current :

feat/stress-orchestration

Conteúdo de  docs/SPRINTS.md :

# Sprints — Orquestração de stress test

| Sprint | Escopo | Status | Evidência |
|---|---|---|---|
| 0 | Preparar branch, estrutura inicial e tracker sem alterar o catálogo existente | Concluído | `python -m pytest tests -q -o addopts=''`: `87 passed in 23.79s`; `git diff --exit-code -- backend/verificalab/catalog.py`: sem diferenças |
| 1 | Definir autorização explícita dos alvos | Não iniciado | — |
| 2 | Catalogar as ferramentas em `backend/config/tools.yaml` | Não iniciado | — |
| 3 | Implementar adaptadores das ferramentas de stress test | Não iniciado | — |
| 4 | Orquestrar execuções autorizadas | Não iniciado | — |
| 5 | Integrar resultados e métricas | Não iniciado | — |
| 6 | Integrar fluxos de interface TUI | Não iniciado | — |
| 7 | Cobrir fluxos e limites com testes | Não iniciado | — |
| 8 | Validar documentação e execução integrada | Não iniciado | — |


1-Sprint 1 concluído e commitado como  2e7cc50  ( feat(auth): authorization gate for stress adapters ). O gate libera apenas  127.0.0.1 ,  ::1  e  localhost ; para outros alvos, exige  authorization.json  com campos válidos, alvo correspondente e autorização não expirada. O worktree ficou limpo.

Evidências

$ cd backend && python -m pytest tests/test_authorization.py -v
collected 19 items
tests/test_authorization.py ...................                          [100%]
============================== 19 passed in 0.06s ==============================

$ cd backend && python -m pytest tests -q -o addopts=''
........................................................................ [ 67%]
..................................                                       [100%]
106 passed in 24.81s

$ cd backend && python -c "from verificalab.core.authorization import require_authorization; print(require_authorization('127.0.0.1:8080'))"
Authorization(target='127.0.0.1:8080', owner='local', reason='alvo loopback', expires_at=None, signature=None)

$ cd backend && python -c "from verificalab.core.authorization import require_authorization; require_authorization('example.com')"
verificalab.core.authorization.AuthorizationError: não foi possível ler uma autorização válida: [Errno 2] No such file or directory: '/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/data/secrets/authorization.json'

O último comando terminou com código 1, como esperado: o alvo externo sem arquivo de autorização foi recusado. As evidências também estão registradas em  docs/SPRINTS.md .
# 2- 
Sprint concluído e commitado como  93795df  ( feat(stress): tool registry and declarative catalog ). O registry carrega as oito ferramentas, oferece  all() ,  get()  e  installed() , filtra por camada e mantém caminhos ausentes ou inválidos como não instalados. O status e as evidências foram registrados em  docs/SPRINTS.md ; a suíte global passou. Há um aviso de depreciação preexistente do  Starlette TestClient .

Saída do catálogo:

8

Todas as ferramentas têm  when_to_use  preenchido:

mikumikubeam True
ddoslayer True
slowloris True
mhddos True
impulse True
pyddos True
overload True
ufonet True

Testes específicos:

collected 25 items

tests/test_registry.py .........................                         [100%]

============================== 25 passed in 0.35s ==============================

Suíte global:

........................................................................ [ 54%]
...........................................................              [100%]
=============================== warnings summary ===============================
tests/test_api_data.py::test_log_upload_parse_and_correlation
  /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
131 passed, 1 warning in 24.32s

# 3 -
Sprint 3 implementado e registrado em  docs/SPRINTS.md . O runner usa  Popen  com lista de argumentos, sessão própria, ambiente mínimo, allowlist de  cwd , limite agregado de saída e encerramento do grupo em timeout ou cancelamento. Os 12 testes específicos passaram; a suíte global passou. Commit:  1077184 feat(core): safe subprocess runner with kill-tree . Worktree limpo.

Evidências reais:

$ cd backend && python -m pytest tests/test_runner.py -v
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/backend
configfile: pytest.ini
plugins: anyio-4.12.1, typeguard-4.4.4
collected 12 items

tests/test_runner.py ............                                        [100%]

============================== 12 passed in 2.60s ==============================

$ cd backend && python -c "from verificalab.core.runner import run_subprocess; r=run_subprocess(['bash','-c','sleep 30 & wait'], cwd='.', timeout_s=2); print(r)"
RunResult(started_at=datetime.datetime(2026, 10, 12, 17, 30, 38, 12375, tzinfo=datetime.timezone.utc), ended_at=datetime.datetime(2026, 10, 12, 17, 30, 40, 18593, tzinfo=datetime.timezone.utc), returncode=-15, stdout='', stderr='', timeout=True, cancelled=False, truncated=False)
$ ps aux | grep 'sleep 30' | grep -v grep

$ grep -rn "shell=True" backend/verificalab/

$ cd backend && python -m pytest tests -q
........................................................................ [ 50%]
.......................................................................  [100%]

As verificações de  ps  e  grep  não produziram saída;  pytest tests -q  terminou com código 0.

# 4 -
Sprint 4 concluído e commitado em  dc3d70f  ( feat(stress): slowloris adapter end-to-end ). O adapter mantém o Slowloris original intacto, exige autorização antes da execução, aplica os limites configurados (30 s e 50 sockets) e encerra a execução no tempo solicitado. O E2E usou o lab real em loopback; o laboratório foi parado depois.  docs/SPRINTS.md  registra o status e as evidências.

Testes do adapter:

$ python -m pytest tests/test_adapter_slowloris.py -v
collected 9 items

tests/test_adapter_slowloris.py .........                                [100%]

============================== 9 passed in 3.68s ==============================

Execução E2E real e log do laboratório:

RunResult: RunResult(started_at=datetime.datetime(2026, 10, 12, 17, 38, 20, 392820, tzinfo=datetime.timezone.utc), ended_at=datetime.datetime(2026, 10, 12, 17, 38, 23, 450108, tzinfo=datetime.timezone.utc), returncode=0, stdout='', stderr='[12-10-2026 14:38:20] Attacking 127.0.0.1 with 10 sockets.\n[12-10-2026 14:38:20] Creating sockets...\n[12-10-2026 14:38:21] Sending keep-alive headers...\n[12-10-2026 14:38:21] Socket count: 10\n', timeout=False, cancelled=False, truncated=False)
LAB_LOG_TAIL:
[lab] TCP 127.0.0.1
[lab] TCP 127.0.0.1
[lab] GET /[lab] GET /
[lab] GET /[lab] GET /
[lab] GET /
[lab] GET /
[lab] GET /

[lab] GET /[lab] GET /

[lab] GET /

Suíte global:

$ python -m pytest tests -q
........................................................................ [ 47%]
........................................................................ [ 94%]
........                                                                 [100%]

$ python -m pytest tests -q -o addopts=''
........................................................................ [ 47%]
........................................................................ [ 94%]
........                                                                 [100%]
152 passed in 31.21s

A worktree ficou limpa após o commit.

# 5 -
Sprint 5 implementado e commitado em  a911c38  ( feat(tui): tools panel with descriptions and run screen ). A TUI lista as oito ferramentas, atualiza o painel lateral ao navegar, mostra detalhes com  i , abre a tela de execução com  r  e sai com  q . Por segurança, a execução está habilitada apenas para o adapter Slowloris revisado, contra loopback na porta do laboratório; ferramentas sem adapter revisado ficam indisponíveis para execução. O registro e o dump também estão em  docs/SPRINTS.md .

Verificações reais:

$ python -m pytest tests/test_tui_smoke.py -v
tests/test_tui_smoke.py .........                                        [100%]
============================== 9 passed in 3.78s ===============================

$ python -m pytest tests -q
........................................................................ [ 44%]
........................................................................ [ 89%]
.................                                                        [100%]

A suíte global terminou com código 0; a execução detalhada contou 161 passed, 1 warning (aviso preexistente de depreciação Starlette/httpx).

Dump do terminal real, após mover a seleção para DDoSlayer:

ID            Nome          Camada  Root?  Status
mikumikubeam  MikuMikuBeam  L7      Não    ✓ instalado
ddoslayer     DDoSlayer     L4+L7   Sim    ✓ instalado
slowloris     Slowloris     L7      Não    ✓ instalado
mhddos        MHDDoS        L4+L7   Sim    ✓ instalado
impulse       Impulse       L4+L7   Sim    ✓ instalado
pyddos        PyDDoS        L4+L7   Sim    ✓ instalado
overload      Overload      L4+L2   Sim    ✓ instalado
ufonet        UFONet        L3      Não    ✓ instalado

DDoSlayer (ddoslayer)
Descrição: Framework interativo com métodos HTTP, conexões lentas e opções
           de camada de rede que usam pacotes raw.
Quando usar: Apenas para testes autorizados e isolados no laboratório local.
Exemplo: python3 ddoslayer/DDoSlayer.py
Riscos: Métodos SYN e UDP podem exigir privilégios elevados e afetar redes.
Limites padrão: 5s · 1 thread(s) · rate limit low

A TUI encerrou com  q  e código 0; a worktree ficou limpa após o commit.

# 6 -
Sprint 6 registrada como “Concluída com bloqueios explícitos” em  docs/SPRINTS.md . Os oito adapters instanciam e há pelo menos seis testes por adapter. DDoSlayer, Overload e UFONet falham fechado por limitações do upstream; PyDDoS também, pois não respeita a porta solicitada. Nenhuma ferramenta que exige root foi executada nos testes.

Evidências reais: a suíte dos adapters passou com 65 testes e 3 skips; os skips são do teste de root para ferramentas que não exigem root. MikuMikuBeam também foi executado sem mock contra o laboratório HTTP em loopback. O comando de instanciação listou os oito adapters.

$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -m pytest tests/test_adapters_all.py -v
collected 68 items

tests/test_adapters_all.py ............................................. [ 66%]
................sss....                                                  [100%]

======================== 65 passed, 3 skipped in 3.42s =========================

$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -c "from verificalab.stress.registry import ToolRegistry; r=ToolRegistry.load(); [print(t.id, r.adapter_for(t.id)) for t in r.all()]"
mikumikubeam <verificalab.stress.adapters.mikumikubeam.MikuMikuBeamAdapter object at 0x7fc16c966ba0>
ddoslayer <verificalab.stress.adapters.ddoslayer.DDoSlayerAdapter object at 0x7fc16c966ba0>
slowloris <verificalab.stress.adapters.slowloris.SlowlorisAdapter object at 0x7fc16c966ba0>
mhddos <verificalab.stress.adapters.mhddos.MHDDOSAdapter object at 0x7fc16c966ba0>
impulse <verificalab.stress.adapters.impulse.ImpulseAdapter object at 0x7fc16c966ba0>
pyddos <verificalab.stress.adapters.pyddos.PyDDoSAdapter object at 0x7fc16c966ba0>
overload <verificalab.stress.adapters.overload.OverloadAdapter object at 0x7fc16c966ba0>
ufonet <verificalab.stress.adapters.ufonet.UFONetAdapter object at 0x7fc16c966ba0>

$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -m pytest tests -q
......................................................................ss [ 31%]
s....................................................................... [ 62%]
........................................................................ [ 94%]
.............                                                            [100%]

A suíte global terminou com código 0; a execução com contagem confirmou 226 passed, 3 skipped, 1 warning. O  python  do sistema não tinha  textual , então a verificação global foi feita com o  .venv  do projeto.

Foram criados os oito commits solicitados:  8036a24  DDoSlayer,  02e8c2d  MHDDoS,  1781b65  Impulse,  5a67b2b  Overload,  5adae1a  PyDDoS,  dd0d88d  UFONet,  bf205d2  MikuMikuBeam e  58dfa0f  Slowloris. Worktree limpa.

# 7 -
Sprint 7 concluído e commitado ( 86389a8 ,  feat(core): orchestrator and multi-format reports ). O orchestrator valida autorização antes da execução, aplica os limites do catálogo, persiste execuções e artefatos no SQLite e gera relatórios JSON, Markdown e HTML com redação de segredos. As evidências foram registradas em  docs/SPRINTS.md .

Testes focados:

collected 23 items

tests/test_orchestrator.py .............                                 [ 56%]
tests/test_report.py ..........                                          [100%]

============================== 23 passed in 0.44s ==============================

Suíte completa, usando o  .venv  existente:

......................................................................ss [ 28%]
s....................................................................... [ 57%]
........................................................................ [ 85%]
....................................                                     [100%]
249 passed, 3 skipped, 1 warning in 36.52s

O teste ponta a ponta real no lab local retornou  returncode=0, ok=True ;  slowloris.log  e os três relatórios foram criados. O HTML foi aberto no Chromium e mostrou o resultado, o alvo, a ferramenta executada e as limitações. A verificação visual, as listagens dos diretórios e as primeiras 30 linhas do HTML também estão documentadas em  docs/SPRINTS.md .

A suíte completa com o Python do sistema não coletou por falta de  textual ; a repetição com o ambiente virtual do projeto passou.

# 8 -
SPRINT 8 — DONE. O fluxo real em loopback, os relatórios, o build e a suíte global passaram; as contagens de processos ficaram em zero. Commits:  9a6e056  ( feat: end-to-end stress orchestration ) e  cdd7b0e  ( docs: mark sprint 8 verified ).

Nota: o primeiro  python -m pytest tests -q  usou o Python do sistema, que não tem  textual , e falhou na coleta. Reexecutei a suíte completa com o ambiente virtual do projeto; o resultado aprovado está em [6].

=== SPRINT 8 — EVIDÊNCIA ===

[1] Contagem de processos ANTES:

0

[2] pytest test_e2e_stress.py:

============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/backend
configfile: pytest.ini
plugins: anyio-4.12.1, typeguard-4.4.4
collected 1 item

tests/test_e2e_stress.py .                                               [100%]

============================== 1 passed in 5.37s ===============================

[3] Contagem de processos DEPOIS (imediato):

0

[4] Contagem de processos DEPOIS (após 2s):

0

[5] Artefatos gerados:

-rw------- 1 grekas grekas 1110 out 12 15:25 stress_1a1315d1b774e5959629cf0f13f.json
-rw------- 1 grekas grekas  686 out 12 15:25 stress_1a1315d1b774e5959629cf0f13f.md
-rw------- 1 grekas grekas 1474 out 12 15:38 stress_1a131689d8a531ca62e5bb3a014.html
-rw------- 1 grekas grekas 1112 out 12 15:38 stress_1a131689d8a531ca62e5bb3a014.json
-rw------- 1 grekas grekas  687 out 12 15:38 stress_1a131689d8a531ca62e5bb3a014.md
drwx------ 5 grekas grekas 4096 out 12 15:38 .
drwx------ 7 grekas grekas 4096 out 12 15:38 ..
drwx------ 2 grekas grekas 4096 out 12 13:17 run_1a130e737e946dbec34f58835e9
drwx------ 2 grekas grekas 4096 out 12 15:25 stress_1a1315d1b774e5959629cf0f13f
drwx------ 2 grekas grekas 4096 out 12 15:38 stress_1a131689d8a531ca62e5bb3a014

[6] Suíte global:

255 passed, 3 skipped, 1 warning in 43.07s

[7] Build frontend:

✓ built in 1.24s

[8] grep shell=True:

(sem saída; exit code 1, nenhuma correspondência)

[9] git log:

cdd7b0e docs: mark sprint 8 verified
9a6e056 feat: end-to-end stress orchestration
86389a8 feat(core): orchestrator and multi-format reports
58dfa0f feat(stress): slowloris adapter
bf205d2 feat(stress): mikumikubeam adapter
dd0d88d feat(stress): ufonet adapter
5adae1a feat(stress): pyddos adapter
5a67b2b feat(stress): overload adapter
1781b65 feat(stress): impulse adapter
02e8c2d feat(stress): mhddos adapter
8036a24 feat(stress): ddoslayer adapter
a911c38 feat(tui): tools panel with descriptions and run screen
dc3d70f feat(stress): slowloris adapter end-to-end
1077184 feat(core): safe subprocess runner with kill-tree
93795df feat(stress): tool registry and declarative catalog
2e7cc50 feat(auth): authorization gate for stress adapters
3e42780 feat: add initial project structure and sprint tracker
96356f0 feat: add integrated evidence dashboard
7755dcc feat: implement local verification core

[10] git status:


[11] SPRINTS.md:

| 0 | Preparar branch, estrutura inicial e tracker sem alterar o catálogo existente | DONE |
| 1 | Definir autorização explícita dos alvos | DONE |
| 2 | Catalogar as ferramentas em `backend/config/tools.yaml` e carregar o registro tipado | DONE |
| 3 | Implementar runner seguro de subprocessos com encerramento em árvore | DONE |
| 4 | Adapter real Slowloris e teste E2E no laboratório local | DONE |
| 5 | TUI Textual: catálogo, descrições e execução no laboratório local | DONE |
| 6 | Adapters restantes (7 ferramentas) | DONE |
| 7 | Orchestrator, persistência SQLite e relatórios JSON/Markdown/HTML | DONE |
| 8 | Integração E2E e documentação | DONE |

