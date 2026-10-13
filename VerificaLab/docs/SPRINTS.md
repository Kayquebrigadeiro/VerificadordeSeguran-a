# Sprints — Orquestração de stress test

| Sprint | Escopo | Status | Evidência |
|---|---|---|---|
| 0 | Preparar branch, estrutura inicial e tracker sem alterar o catálogo existente | DONE | `python -m pytest tests -q -o addopts=''`: `87 passed in 23.79s`; `git diff --exit-code -- backend/verificalab/catalog.py`: sem diferenças |
| 1 | Definir autorização explícita dos alvos | DONE | 19 testes específicos e 106 testes globais passaram; execução manual libera loopback e rejeita alvo externo sem arquivo de autorização (evidências detalhadas abaixo) |
| 2 | Catalogar as ferramentas em `backend/config/tools.yaml` e carregar o registro tipado | DONE | 8 ferramentas carregadas; 25 testes do registry e 131 testes globais passaram |
| 3 | Implementar runner seguro de subprocessos com encerramento em árvore | DONE | 12 testes específicos passaram; timeout manual matou o grupo; grep sem ocorrências; suíte global passou |
| 4 | Adapter real Slowloris e teste E2E no laboratório local | DONE | 9 testes do adapter, execução real em `127.0.0.1:8477` com `returncode=0` e suíte global com 152 testes |
| 5 | TUI Textual: catálogo, descrições e execução no laboratório local | DONE | 9 testes TUI, captura manual com 8 ferramentas e suíte global com 161 testes |
| 6 | Adapters restantes (7 ferramentas) | DONE | 65 testes de adapters passaram; 8 adapters instanciados; suíte global passou (evidências abaixo) |
| 7 | Orchestrator, persistência SQLite e relatórios JSON/Markdown/HTML | DONE | 23 testes focados; execução real Slowloris no lab local; suíte global: 249 passed, 3 skipped (evidências abaixo) |
| 8 | Integração E2E e documentação | DONE | E2E real: `1 passed in 5.37s`; suíte: `255 passed, 3 skipped`; build frontend e Chromium aprovados; processos `0/0/0`; grep sem correspondências; commit de implementação `9a6e056` |

## Evidências do Sprint 1

Implementado `require_authorization(target)` com liberação apenas de `127.0.0.1`,
`::1` e `localhost`; todos os demais alvos exigem `data/secrets/authorization.json`
com `target`, `owner`, `reason` e `expires_at` válidos. A assinatura é opcional.
O alvo registrado deve corresponder literalmente ao pedido; expiração sem fuso
horário, arquivo ausente/inválido e campos obrigatórios ausentes são recusados.

```text
$ cd backend && python -m pytest tests/test_authorization.py -v
collected 19 items
tests/test_authorization.py ...................                          [100%]
============================== 19 passed in 0.06s ==============================
```

```text
$ cd backend && python -m pytest tests -q
........................................................................ [ 67%]
..................................                                       [100%]
```

O comando global acima terminou com código 0. Como `pytest.ini` já define
`addopts = -q`, também foi executado sem essa configuração quiet para registrar
a contagem final:

```text
$ cd backend && python -m pytest tests -q -o addopts=''
........................................................................ [ 67%]
..................................                                       [100%]
106 passed in 24.81s
```

Verificações manuais:

```text
$ cd backend && python -c "from verificalab.core.authorization import require_authorization; print(require_authorization('127.0.0.1:8080'))"
Authorization(target='127.0.0.1:8080', owner='local', reason='alvo loopback', expires_at=None, signature=None)
```

```text
$ cd backend && python -c "from verificalab.core.authorization import require_authorization; require_authorization('example.com')"
verificalab.core.authorization.AuthorizationError: não foi possível ler uma autorização válida: [Errno 2] No such file or directory: '/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/data/secrets/authorization.json'
```

## Evidências do Sprint 2

`backend/config/tools.yaml` declara as oito ferramentas do inventário com
camada, requisito de root, descrição, orientação de uso, exemplo, riscos e
limites curtos. `ToolRegistry.load()` lê o YAML com `safe_load` e produz
dataclasses; `all()` aceita filtro por camada, `get(id)` consulta o registro e
`installed()` limita o resultado a caminhos relativos existentes dentro da raiz.
Caminhos ausentes ou inseguros permanecem no catálogo com `installed=False`.
O catálogo estático existente em `catalog.py` não foi alterado.

Verificação do total:

```text
$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -c "from verificalab.stress.registry import ToolRegistry; r=ToolRegistry.load(); print(len(r.all()))"
8
```

Verificação manual de `when_to_use` não vazio:

```text
$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -c "from verificalab.stress.registry import ToolRegistry; r=ToolRegistry.load(); [print(t.id, bool(t.when_to_use)) for t in r.all()]"
mikumikubeam True
ddoslayer True
slowloris True
mhddos True
impulse True
pyddos True
overload True
ufonet True
```

Testes específicos:

```text
$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -m pytest tests/test_registry.py -v
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/backend
configfile: pytest.ini
plugins: anyio-4.15.1
collected 25 items

tests/test_registry.py .........................                         [100%]

============================== 25 passed in 0.35s ==============================
```

Suíte global:

```text
$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -m pytest tests -q -o addopts=''
........................................................................ [ 54%]
...........................................................              [100%]
=============================== warnings summary ===============================
tests/test_api_data.py::test_log_upload_parse_and_correlation
  /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
131 passed, 1 warning in 24.32s
```

## Evidências do Sprint 3

`core.runner.run_subprocess()` exige comando em lista, valida diretório contra
raízes permitidas, inicia sessão/grupo próprio, usa ambiente mínimo com `PATH`
explícito, drena stdout/stderr concorrentemente sob limite agregado de 1 MB e
encerra o grupo em timeout ou cancelamento. `RunResult` inclui horários UTC,
código de retorno, saídas capturadas e flags de timeout, cancelamento e
truncamento.

Testes específicos:

```text
$ cd backend && python -m pytest tests/test_runner.py -v
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/backend
configfile: pytest.ini
plugins: anyio-4.12.1, typeguard-4.4.4
collected 12 items

tests/test_runner.py ............                                        [100%]

============================== 12 passed in 2.60s ==============================
```

Verificação manual de timeout e processo filho:

```text
$ cd backend && python -c "from verificalab.core.runner import run_subprocess; r=run_subprocess(['bash','-c','sleep 30 & wait'], cwd='.', timeout_s=2); print(r)"
RunResult(started_at=datetime.datetime(2026, 10, 12, 17, 30, 38, 12375, tzinfo=datetime.timezone.utc), ended_at=datetime.datetime(2026, 10, 12, 17, 30, 40, 18593, tzinfo=datetime.timezone.utc), returncode=-15, stdout='', stderr='', timeout=True, cancelled=False, truncated=False)
$ ps aux | grep 'sleep 30' | grep -v grep
(sem saída; nenhum processo encontrado)
```

Busca por invocação de shell:

```text
$ grep -rn "shell=True" backend/verificalab/
(sem saída; grep retornou 1 por não encontrar correspondências)
```

Suíte global:

```text
$ cd backend && python -m pytest tests -q
........................................................................ [ 50%]
.......................................................................  [100%]
```

O comando global terminou com código 0.

## Evidências do Sprint 4

Implementados `StressRequest`, `StressAdapter` e `StressResult` (alias do
`RunResult` do runner), além do `SlowlorisAdapter`. Os limites máximos são
declarados em `tools.yaml` (30 s e 50 sockets), validados pelo registry e
aplicados sem elevar valores menores. O adapter chama
`require_authorization()` antes da construção/execução do comando, recusa
opções upstream fora da allowlist e só permite o caminho `/`, pois o Slowloris
original não oferece configuração de caminho nem duração. O original permaneceu
inalterado; um supervisor temporizado encerra o processo ao final da duração,
com o timeout do runner como limite de segurança adicional.

O lab registra conexões TCP antes de receber cabeçalhos completos e trata
desconexões do teste como parte normal do ciclo. `backend/tests/fixtures/local_http.py`
reusa o fixture do laboratório da suíte.

Testes específicos:

```text
$ cd backend && python -m pytest tests/test_adapter_slowloris.py -v
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/backend
configfile: pytest.ini
plugins: anyio-4.12.1, typeguard-4.4.4
collected 9 items

tests/test_adapter_slowloris.py .........                                [100%]

============================== 9 passed in 3.68s ==============================
```

Execução real contra o laboratório local:

```text
LAB: {'running': True, 'pid': 217263, 'endpoint': 'http://127.0.0.1:8477', 'managed_by': 'verificalab', 'message': 'lab iniciado'}
RunResult: RunResult(started_at=datetime.datetime(2026, 10, 12, 17, 38, 20, 392820, tzinfo=datetime.timezone.utc), ended_at=datetime.datetime(2026, 10, 12, 17, 38, 23, 450108, tzinfo=datetime.timezone.utc), returncode=0, stdout='', stderr='[12-10-2026 14:38:20] Attacking 127.0.0.1 with 10 sockets.\n[12-10-2026 14:38:20] Creating sockets...\n[12-10-2026 14:38:21] Sending keep-alive headers...\n[12-10-2026 14:38:21] Socket count: 10\n', timeout=False, cancelled=False, truncated=False)
LAB_STOP: {'running': False, 'pid': None, 'endpoint': 'http://127.0.0.1:8477', 'managed_by': None, 'message': 'lab encerrado'}
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
```

Suíte global, comando solicitado:

```text
$ cd backend && python -m pytest tests -q
........................................................................ [ 47%]
........................................................................ [ 94%]
........                                                                 [100%]
```

O comando terminou com código 0. Para obter a contagem final sem o `addopts`
quiet do projeto:

```text
$ cd backend && python -m pytest tests -q -o addopts=''
........................................................................ [ 47%]
........................................................................ [ 94%]
........                                                                 [100%]
152 passed in 31.21s
```

## Evidências do Sprint 5

Implementado o painel Textual com tabela navegável (ID, nome, camada, root e
status), descrição lateral atualizada pelo cursor, tela de detalhes (`i`) e
formulário de execução (`r`). Ferramentas ausentes são marcadas em vermelho.
A execução na TUI fica restrita ao adapter Slowloris revisado, a loopback e à
porta configurada para o laboratório local; não há invocação direta dos outros
executáveis do catálogo. A tela solicita duração e threads e exibe resultado,
saída e erros.

Testes com `textual.pilot`, sem executar ferramentas reais:

```text
$ cd backend && python -m pytest tests/test_tui_smoke.py -v
collected 9 items
tests/test_tui_smoke.py .........                                        [100%]
============================== 9 passed in 3.83s ===============================
```

Execução manual de `python -m verificalab tui` em terminal real: o painel abriu,
a seta ↓ moveu a seleção para DDoSlayer, o conteúdo lateral mudou e `q` encerrou
com código 0. Dump do quadro capturado:

```text
Ferramentas do catálogo
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
           de camada de rede que usam pacotes raw. Exige revisão do método
           escolhido antes de qualquer teste.
Quando usar: Apenas para testes autorizados e isolados no laboratório local,
             escolhendo HTTP e mantendo duração e threads nos limites abaixo.
Exemplo: python3 ddoslayer/DDoSlayer.py
Riscos: Métodos SYN e UDP podem exigir privilégios elevados e afetar redes.
        A interface interativa não aplica os limites do VerificaLab.
Limites padrão: 5s · 1 thread(s) · rate limit low
```

Suíte global solicitada:

```text
$ cd backend && python -m pytest tests -q
........................................................................ [ 44%]
........................................................................ [ 89%]
.................                                                        [100%]
```

O comando terminou com código 0. Para registrar a contagem final, executado
também sem os `addopts` quiet do projeto:

```text
$ cd backend && python -m pytest tests -q -o addopts=''
........................................................................ [ 44%]
........................................................................ [ 89%]
.................                                                        [100%]
161 passed, 1 warning in 33.36s
```

## Evidências do Sprint 6

Implementados os sete adapters solicitados e `ToolRegistry.adapter_for(id)`;
os testes de `test_adapters_all.py` também incluem Slowloris. Todos os novos
adapters aplicam autorização antes de validar/executar, restringem alvos a
loopback e limitam duração e threads conforme `tools.yaml`. Os testes root
mockam somente a checagem para confirmar a recusa e garantem que nenhum
subprocesso é iniciado.

Quatro upstreams falham fechados, sem alterar os originais: DDoSlayer e
Overload só oferecem interface interativa; PyDDoS não respeita a porta
solicitada pelo adapter; UFONet permanece somente para análise estática,
conforme o catálogo. MHDDoS usa GET direto com arquivo local de proxies vazio,
verificado antes da execução. MikuMikuBeam usa HTTP direto sem proxy, uma
thread, intervalo de 1 segundo e dependências Go apenas do cache local.

Verificação individual na ordem da sprint:

```text
$ python -m pytest tests/test_adapters_all.py -k ddoslayer -v
8 passed
$ python -m pytest tests/test_adapters_all.py -k mhddos -v
8 passed
$ python -m pytest tests/test_adapters_all.py -k impulse -v
8 passed
$ python -m pytest tests/test_adapters_all.py -k overload -v
8 passed
$ python -m pytest tests/test_adapters_all.py -k pyddos -v
8 passed
$ python -m pytest tests/test_adapters_all.py -k ufonet -v
7 passed, 1 skipped
$ python -m pytest tests/test_adapters_all.py -k mikumikubeam -v
8 passed, 1 skipped
$ python -m pytest tests/test_adapters_all.py -k slowloris -v
8 passed, 1 skipped
```

O teste MikuMikuBeam executa o comando Go real contra o fixture HTTP local
(loopback), sem mock do executor e sem buscar dependências ou proxies externos:

```text
$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -m pytest tests/test_adapters_all.py -k mikumikubeam -v
collected 68 items / 59 deselected / 9 selected
tests/test_adapters_all.py .......s.                                     [100%]
8 passed, 1 skipped
```

Saída exigida da suíte de adapters:

```text
$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -m pytest tests/test_adapters_all.py -v
collected 68 items
tests/test_adapters_all.py ............................................. [ 66%]
................sss....                                                  [100%]
65 passed, 3 skipped
```

Instanciação de todas as ferramentas:

```text
$ python -c "from verificalab.stress.registry import ToolRegistry; r=ToolRegistry.load(); [print(t.id, r.adapter_for(t.id)) for t in r.all()]"
mikumikubeam <verificalab.stress.adapters.mikumikubeam.MikuMikuBeamAdapter object at 0x7fc16c966ba0>
ddoslayer <verificalab.stress.adapters.ddoslayer.DDoSlayerAdapter object at 0x7fc16c966ba0>
slowloris <verificalab.stress.adapters.slowloris.SlowlorisAdapter object at 0x7fc16c966ba0>
mhddos <verificalab.stress.adapters.mhddos.MHDDOSAdapter object at 0x7fc16c966ba0>
impulse <verificalab.stress.adapters.impulse.ImpulseAdapter object at 0x7fc16c966ba0>
pyddos <verificalab.stress.adapters.pyddos.PyDDoSAdapter object at 0x7fc16c966ba0>
overload <verificalab.stress.adapters.overload.OverloadAdapter object at 0x7fc16c966ba0>
ufonet <verificalab.stress.adapters.ufonet.UFONetAdapter object at 0x7fc16c966ba0>
```

Suíte global; o Python do sistema não tinha `textual`, então foi usado o
interpretador já configurado no `.venv`:

```text
$ cd backend && /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin/python -m pytest tests -q
......................................................................ss [ 31%]
s....................................................................... [ 62%]
........................................................................ [ 94%]
.............                                                            [100%]
=============================== warnings summary ===============================
tests/test_api_data.py::test_log_upload_parse_and_correlation
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
226 passed, 3 skipped, 1 warning
```

## Evidências do Sprint 7 — Orchestrator + relatórios

Implementados `core/orchestrator.py` e `core/report.py`. O orchestrator
recusa ferramentas fora do `ToolRegistry`, valida autorização antes de
executar adapters, aplica os limites declarados no catálogo e continua após
falha individual. Cada ferramenta gera registro `runs`, `check_results`,
`artifacts` e log privado em `data/artifacts/<orchestrator_run_id>/<tool>.log`.
Os relatórios JSON, Markdown e HTML são gerados em `data/exports/` ao final da
execução, com redação de segredos e seção de limitações. O esquema SQLite
existente não contém `stress_runs` nem `storage/models.py`: os campos
`tool_id`, `target`, `ended_at`, `returncode`, `ok` e `orchestrator_id` foram
adicionados por migração compatível à tabela `runs` existente.

Testes focados:

```text
$ cd backend && ../.venv/bin/python -m pytest tests/test_orchestrator.py tests/test_report.py -v
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/backend
configfile: pytest.ini
plugins: anyio-4.15.1, platformdirs-4.13.0
collected 23 items

tests/test_orchestrator.py .............                                 [ 56%]
tests/test_report.py ..........                                          [100%]

============================== 23 passed in 0.44s ==============================
```

Execução ponta a ponta real contra o laboratório local (não usa mock do
executor):

```text
$ cd backend && python -c "from verificalab.core.orchestrator import Orchestrator; o=Orchestrator(); s=o.run(o.plan('127.0.0.1:8477', ['slowloris'])); print(s)"
RunSummary(run_id='stress_1a1315d1b774e5959629cf0f13f', target='127.0.0.1:8477', started_at=datetime.datetime(2026, 10, 12, 18, 25, 47, 895660, tzinfo=datetime.timezone.utc), ended_at=datetime.datetime(2026, 10, 12, 18, 25, 53, 340946, tzinfo=datetime.timezone.utc), executions=(ToolRunSummary(run_id='run_1a1315d1b778063131774e0af60', tool_id='slowloris', tool_name='Slowloris', target='127.0.0.1:8477', started_at=datetime.datetime(2026, 10, 12, 18, 25, 48, 62380, tzinfo=datetime.timezone.utc), ended_at=datetime.datetime(2026, 10, 12, 18, 25, 53, 179018, tzinfo=datetime.timezone.utc), returncode=0, ok=True, artifact_path='/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/data/artifacts/stress_1a1315d1b774e5959629cf0f13f/slowloris.log', error=None),), report_paths=(('json', '/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/data/exports/stress_1a1315d1b774e5959629cf0f13f.json'), ('markdown', '/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/data/exports/stress_1a1315d1b774e5959629cf0f13f.md'), ('html', '/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/data/exports/stress_1a1315d1b774e5959629cf0f13f.html')))
```

Verificação dos caminhos e relatórios gerados:

```text
$ ls -la data/artifacts/stress_1a1315d1b774e5959629cf0f13f/
total 12
drwx------ 2 grekas grekas 4096 out 12 15:25 .
drwx------ 4 grekas grekas 4096 out 12 15:25 ..
-rw------- 1 grekas grekas  208 out 12 15:25 slowloris.log

$ ls -la data/exports/
total 20
drwx------ 2 grekas grekas 4096 out 12 15:25 .
drwx------ 7 grekas grekas 4096 out 12 15:25 ..
-rw------- 1 grekas grekas 1473 out 12 15:25 stress_1a1315d1b774e5959629cf0f13f.html
-rw------- 1 grekas grekas 1110 out 12 15:25 stress_1a1315d1b774e5959629cf0f13f.json
-rw------- 1 grekas grekas  686 out 12 15:25 stress_1a1315d1b774e5959629cf0f13f.md
```

Primeiras 30 linhas do HTML produzido:

```html
<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>VerificaLab — relatório stress_1a1315d1b774e5959629cf0f13f</title>
<style>
body{font-family:system-ui,sans-serif;max-width:70rem;margin:2rem auto;padding:0 1rem;color:#172033}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd;padding:.5rem;text-align:left}
th{background:#eef1f7}.status{font-weight:600}.limitations{background:#f5f7fa;padding:1rem}
</style></head>
<body><h1>Relatório VerificaLab</h1>
<p class="status">Resultado: OK</p>
<dl><dt>Execução</dt><dd>stress_1a1315d1b774e5959629cf0f13f</dd>
<dt>Alvo</dt><dd>127.0.0.1:8477</dd>
<dt>Início</dt><dd>2026-10-12T18:25:47.895660+00:00</dd>
<dt>Fim</dt><dd>2026-10-12T18:25:53.340946+00:00</dd>
<dt>Duração total</dt><dd>5.445286 s</dd></dl>
<h2>Ferramentas executadas</h2>
<table><thead><tr><th>Ferramenta</th><th>Resultado</th><th>Código</th><th>Duração (s)</th>
</tr></thead><tbody><tr><td>Slowloris</td><td>OK</td><td>0</td><td>5.116638</td></tr></tbody></table>
<section class="limitations"><h2>Limitações</h2><ul><li>Somente alvos loopback explícitos são suportados pelos adapters.</li><li>Não há amplificação de tráfego nem uso de proxies externos.</li><li>Cada ferramenta respeita os limites de duração e threads do catálogo.</li><li>Resultados descrevem somente o comportamento observado nesta execução.</li></ul></section>
</body></html>
```

O HTML também foi aberto com Chromium headless e inspecionado visualmente:
resultado `OK`, alvo loopback, linha Slowloris e limitações aparecem na página.
A captura foi temporária e não integra o repositório.

Suíte completa (`pytest.ini` já define `addopts = -q`; sem a opção extra,
pytest fica em modo quieto duplo e omite a contagem final):

```text
$ cd backend && PATH=/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin:$PATH python -m pytest tests -q
......................................................................ss [ 28%]
s....................................................................... [ 57%]
........................................................................ [ 85%]
....................................                                     [100%]

$ cd backend && PATH=/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin:$PATH python -m pytest tests -q -o addopts=''
......................................................................ss [ 28%]
s....................................................................... [ 57%]
........................................................................ [ 85%]
....................................                                     [100%]
=============================== warnings summary ===============================
tests/test_api_data.py::test_log_upload_parse_and_correlation
  /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
249 passed, 3 skipped, 1 warning in 36.52s
```

## Evidências do Sprint 8 — Integração E2E + documentação

O teste único `test_e2e_full_flow()` inicia um servidor HTTP real em loopback e
porta efêmera, confirma `/ok`, autoriza o alvo local e rejeita `example.com`.
Executa o Slowloris real por 3 segundos/10 threads, verifica no SQLite a
configuração enviada, confirma as 10 sockets no artefato, valida os três
relatórios e checa encerramento de processos. O teste usa o diretório isolado
da suíte. Também foi feita uma rodada real independente com o diretório de
dados normal da aplicação:

```text
run_id=stress_1a131689d8a531ca62e5bb3a014
target=127.0.0.1:46461
connections=11
artifact=data/artifacts/stress_1a131689d8a531ca62e5bb3a014/slowloris.log
json=data/exports/stress_1a131689d8a531ca62e5bb3a014.json
markdown=data/exports/stress_1a131689d8a531ca62e5bb3a014.md
html=data/exports/stress_1a131689d8a531ca62e5bb3a014.html
```

Teste E2E dedicado:

```text
$ cd backend && python -m pytest tests/test_e2e_stress.py -v
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/backend
configfile: pytest.ini
plugins: anyio-4.12.1, typeguard-4.4.4
collected 1 item

tests/test_e2e_stress.py .                                               [100%]

============================== 1 passed in 5.37s ===============================
```

Contagem de processos antes da execução: `0`. Verificação imediatamente
depois: `0`; nova contagem após 2 segundos: `0`. O teste também exige zero
antes/depois internamente em caso de falha no fluxo.

Suíte global executada com o Python do ambiente virtual do projeto:

```text
$ cd backend && PATH=/home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/bin:$PATH python -m pytest tests -q -o addopts=''
......................................................................ss [ 27%]
s....................................................................... [ 55%]
........................................................................ [ 83%]
..........................................                               [100%]
=============================== warnings summary ===============================
tests/test_api_data.py::test_log_upload_parse_and_correlation
  /home/grekas/Projetos/VerificadordeSegurança/VerificaLab/.venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
255 passed, 3 skipped, 1 warning in 43.07s
```

Build frontend: `✓ built in 1.24s`. Busca
`grep -rn "shell=True" backend/verificalab/`: nenhuma correspondência
(grep retornou 1, como esperado). O histórico contém commits dos Sprints 1–7;
Chromium headless abriu o relatório exportado e confirmou ferramenta, alvo e
duração com exit code 0. Commit de implementação: `9a6e056`
(`feat: end-to-end stress orchestration`).
