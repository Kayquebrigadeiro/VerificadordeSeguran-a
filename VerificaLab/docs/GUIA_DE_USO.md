# Guia de Uso — VerificaLab

## Pré-requisitos

- Python 3.11 ou superior.
- Ambiente virtual do projeto em `.venv/`.
- Comando padrão: `.venv/bin/python -m verificalab ...`.
- Para executar a aplicação localmente, use o diretório raiz do repositório.

## 1. Subir o laboratório (alvo de teste)

O laboratório é um servidor HTTP em loopback que serve rotas conhecidas:
`/ok`, `/error`, `/slow`, `/json`, `/headers`, `/drop`,
`/redirect-local` e `/redirect-external`.

```python
from verificalab import labctl

labctl.start()
# {'running': True, 'endpoint': 'http://127.0.0.1:8477', ...}

# ... execute verificações autorizadas ...

labctl.stop()
```

O serviço escuta apenas em loopback e destina-se a testes locais descartáveis.
Também é possível subir a aplicação web com `.venv/bin/python -m verificalab
serve`; abra `http://127.0.0.1:8400`. Use `serve --no-lab` para não iniciar o
laboratório junto com a aplicação.

## 2. Verificações passivas (contrato HTTP)

Não usam ferramentas de stress. Comparam as respostas HTTP recebidas com os
valores esperados na configuração.

```python
import threading
from verificalab.executors.httpchecks import run_http_checks


class Ctx:
    def __init__(self, cfg, env):
        self.cfg = cfg
        self.env = env
        self.cancel_event = threading.Event()
        self.secret_header = None

    def log(self, level, msg):
        print(f"[{level}] {msg}")

    def set_progress(self, value):
        pass

    def deadline_reached(self):
        return False


ctx = Ctx(
    cfg={
        "checks": [
            {
                "name": "ok200",
                "type": "status",
                "path": "/ok",
                "expected_status": 200,
            },
            {
                "name": "json",
                "type": "json_fields",
                "path": "/json",
                "expected_status": 200,
                "fields": [{"path": "service", "equals": "verificalab-lab"}],
            },
        ],
        "include_config_checks": True,
        "timeout_s": 5,
    },
    env={
        "scheme": "http",
        "host": "127.0.0.1",
        "port": 8477,
        "secret_header_name": None,
    },
)
result = run_http_checks(ctx)
```

O resultado registra os checks e as observações obtidas nessa execução. Um
check `fail` indica que a resposta observada não correspondeu ao contrato
configurado; achados contextuais não são, por si só, prova de vulnerabilidade.

## 3. Stress test autorizado

O `Orchestrator` valida a autorização antes de executar adapters. Use somente
alvos próprios ou explicitamente autorizados. Para o laboratório local:

```python
from verificalab import labctl
from verificalab.core.orchestrator import Orchestrator

labctl.start()
try:
    orchestrator = Orchestrator()
    plan = orchestrator.plan("127.0.0.1:8477", ["slowloris"])
    summary = orchestrator.run(plan)
    print(summary.run_id, summary.ok)
finally:
    labctl.stop()
```

Ferramentas com execução real confirmada em loopback:

- `slowloris` — conexões HTTP lentas/incompletas; limitada pelo adapter.
- `mikumikubeam` — teste HTTP/TCP; usar somente no laboratório local e sem
  proxies.

Ferramentas que recusam execução (fail-closed): `ddoslayer`, `overload`,
`ufonet` e `pyddos`. `mhddos` e `impulse` declaram `requires_root: true` e não
foram homologadas E2E. Consulte `backend/config/tools.yaml` e
`docs/PENDENCIAS.md` antes de qualquer uso.

## 4. Alvo externo

Um alvo fora de loopback exige autorização válida. Crie
`data/secrets/authorization.json` com os dados do alvo e a validade:

```json
{
  "target": "https://meu-servidor-de-teste.com",
  "owner": "seu nome",
  "reason": "teste autorizado em ambiente de staging",
  "expires_at": "2026-12-31T23:59:59Z"
}
```

O alvo deve corresponder literalmente ao pedido e a autorização precisa estar
válida e completa. Por exemplo, use o mesmo valor em `plan()`:

```python
plan = orchestrator.plan(
    "https://meu-servidor-de-teste.com",
    ["slowloris"],
)
```

Sem autorização válida, o gate recusa a execução antes de iniciar qualquer
subprocesso. Não use o mecanismo para contornar falta de permissão do
proprietário do sistema; autorização técnica não substitui autorização legal.

## 5. Cancelar uma execução

O cancelamento disponível é feito pela API:

```bash
curl -X POST http://127.0.0.1:8400/api/runs/<run_id>/cancel
```

O worker solicita a interrupção da execução ativa ou cancela uma execução
enfileirada. A execução ativa pode responder primeiro com `cancelling`; ao
terminar, o estado final é `cancelled`.

Via Python: `o.cancel(run_id)` delega a chamada a `Worker.request_cancel()`.
Instancie o Orchestrator com a mesma instância de `Worker` que gerencia as
execuções, por exemplo `o = Orchestrator(worker=worker)`.
Esse método cancela runs administradas por esse worker; `Orchestrator.run()`
continua sendo uma execução síncrona separada e não é enfileirada no Worker.

## 6. Relatórios e artefatos

Após `orchestrator.run(plan)`, os relatórios são gravados em:

- `data/exports/<orchestrator_run_id>.json`
- `data/exports/<orchestrator_run_id>.md`
- `data/exports/<orchestrator_run_id>.html`

Logs (`stdout`/`stderr`) de cada ferramenta ficam em:

- `data/artifacts/<orchestrator_run_id>/<tool_id>.log`

Os dados permanecem localmente até remoção manual. Os relatórios descrevem
somente o comportamento observado na execução correspondente.

## 7. TUI

Na raiz do repositório:

```bash
.venv/bin/python -m verificalab tui
```

Teclas: `↑`/`↓` navegam, `i` abre detalhes, `r` inicia uma execução permitida
e `q` sai. A execução pela TUI é restrita ao adapter Slowloris revisado e ao
laboratório local.

## 8. Suíte de testes

Na raiz do repositório:

```bash
.venv/bin/python -m pytest backend/tests -o addopts='' -ra
```

Resultado da homologação: `255 passed, 3 skipped`, com um warning
preexistente de compatibilidade Starlette/httpx. Os testes skipados relacionados
a root não significam que essas ferramentas foram homologadas para execução.

## 9. Ver pendências conhecidas

Leia [`docs/PENDENCIAS.md`](PENDENCIAS.md) antes de reportar um comportamento
como bug. O histórico e as evidências dos sprints estão em
[`docs/SPRINTS.md`](SPRINTS.md); o resultado detalhado da homologação está em
[`docs/HOMOLOGACAO_FINAL.md`](HOMOLOGACAO_FINAL.md).
