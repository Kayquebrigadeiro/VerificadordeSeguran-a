# Orquestração de stress test

O fluxo de execução controlada possui cinco camadas. A configuração e a
interface não substituem a autorização do proprietário do alvo; a execução
real suportada permanece limitada a loopback.

## 1. Autorização

`core.authorization.require_authorization()` libera `127.0.0.1`, `::1` e
`localhost` explicitamente. Um alvo que não seja loopback exige
`data/secrets/authorization.json`, com alvo correspondente, responsável,
motivo e expiração ISO 8601 com fuso horário. A autorização não amplia as
restrições dos adapters: eles ainda recusam qualquer destino não loopback.
O orchestrator valida a autorização antes de persistir uma execução ou iniciar
um processo.

## 2. Registro de ferramentas

`backend/config/tools.yaml` é a fonte declarativa do catálogo. O
`ToolRegistry` valida os campos, identificadores, caminhos e limites e faz a
associação entre ID e classe de adapter. Os limites máximos são tetos: os
valores pedidos no plano devem ser positivos e não exceder o teto definido.
Uma ferramenta sem adapter seguro não ganha permissão de execução apenas por
estar listada no catálogo.

## 3. Adapters

`StressRequest` transporta alvo, duração, número de threads, caminho e
argumentos. A classe base aplica limites e valida loopback; cada adapter
aplica ainda as restrições específicas da ferramenta. Slowloris é o único
adapter executável pela TUI atualmente. Os outros adapters recusam execução
quando seu upstream não oferece uma invocação suficientemente restrita.

O adapter Slowloris é real, não simulado: inicia o script instalado com
argumentos em lista, sem shell, e supervisiona seu tempo de vida. O laboratório
de integração é um servidor HTTP real vinculado a uma porta livre em
`127.0.0.1`.

## 4. Orchestrator, runner e evidências

`Orchestrator.plan()` resolve cada ID no registro e aceita sobrescritas
opcionais de duração/threads somente dentro dos limites declarados.
`Orchestrator.run(plan, auth)` revalida autorização e entradas do plano antes
da execução. O adapter usa `core.runner.run_subprocess()`, que cria um grupo
de processos, captura saída com limite e encerra a árvore ao atingir timeout
ou cancelamento.

Cada execução persiste seus metadados no SQLite e grava
`data/artifacts/<run_id>/<tool_id>.log`. O orchestrator gera
`data/exports/<run_id>.json`, `.md` e `.html`; os relatórios redigem valores
sensíveis e incluem limitações e resultado observado. O E2E troca o diretório
de dados pela área temporária isolada configurada pela suíte, e valida os
mesmos caminhos exportados pela aplicação sem poluir os dados locais do
usuário.

## 5. TUI

O painel Textual mostra ferramentas do registro, detalhes e status de
instalação. A tela de execução só habilita Slowloris instalado, valida a porta
do laboratório local, duração e threads e apresenta o resultado do runner.
A TUI chama diretamente o adapter seguro; o E2E do Sprint 8 exercita o caminho
do orchestrator em vez de automatizar interação de terminal. Assim, são dois
entry points com autorização e validação de loopback, e a suíte mantém testes
de smoke separados para a interface.

## Teste E2E

Execute a partir de `backend/`:

```bash
python -m pytest tests/test_e2e_stress.py -v
```

O teste sobe o laboratório HTTP real em porta efêmera, confirma `/ok`, testa
autorização local e rejeição de `example.com`, executa Slowloris por 3 segundos
com 10 threads contra loopback, confirma tráfego e artefato, valida os três
relatórios e conta processos antes/depois (incluindo uma espera de 2 segundos).
Ele não faz requisições a alvos externos nem substitui o executor por mock.
