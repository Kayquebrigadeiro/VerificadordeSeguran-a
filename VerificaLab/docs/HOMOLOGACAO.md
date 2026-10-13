# Homologação local

Data da rodada: 11 de outubro de 2026.

## Resultado atual

| Área | Evidência | Estado |
| --- | --- | --- |
| Backend | 87 testes pytest concluídos | aprovado |
| Frontend | TypeScript e bundle Vite de produção | aprovado |
| Contratos HTTP | laboratório real, incluindo falha intencional e redirect externo bloqueado | aprovado |
| Carga leve | reserva global, limites, concorrência e cancelamento cobertos | aprovado |
| Runner pytest | processo real, JUnit, timeout e encerramento de filho | aprovado |
| Importadores | JUnit XML, JSON, JSONL e DDoSlayer JSON; entradas malformadas e XXE cobertas | aprovado |
| Segurança local | Host, Origin, CSRF, path traversal, XSS/sanitização e redação | aprovado por testes automatizados |
| Browser real | Chromium headless, viewports 1440×1000 e 390×844, API e assets reais | aprovado |

## Rodada Sprint 8 — 12 de outubro de 2026

| Área | Evidência | Estado |
| --- | --- | --- |
| Fluxo E2E de stress | `tests/test_e2e_stress.py`: servidor HTTP real em loopback/porta efêmera, autorização local, Slowloris por 3 s/10 threads, artefato e três formatos de relatório | aprovado |
| Autorização | `127.0.0.1:<porta>` liberado; `example.com` recusado com `AuthorizationError` | aprovado |
| Tráfego local | O contador de conexões do laboratório aumentou durante a execução real do adapter | aprovado |
| Relatórios | JSON válido, Markdown com “Slowloris” e HTML parseado com nome da ferramenta, alvo e duração | aprovado |
| Browser | Chromium headless abriu o HTML gerado e exibiu ferramenta, alvo e duração (exit code 0) | aprovado |
| Processos | zero antes, zero imediatamente após e zero após espera de 2 s | aprovado |
| Orchestrator | 19 testes E2E/orchestrator passaram, incluindo sobrescritas dentro e fora dos limites | aprovado |
| Suíte backend | 255 passed, 3 skipped | aprovado |
| Frontend | `npm run build`, TypeScript e Vite de produção | aprovado |
| Busca de shell | `grep -rn "shell=True" backend/verificalab/` sem correspondências | aprovado |

O teste usa o diretório temporário isolado definido por `backend/tests/conftest.py`
para banco, artefatos e exports, sem alterar os dados preexistentes do usuário.
Além do teste isolado, uma execução real persistiu no diretório local
`data/`: `stress_1a131689d8a531ca62e5bb3a014`, alvo loopback em porta efêmera,
11 conexões vistas pelo laboratório, log `slowloris.log` e exports JSON,
Markdown e HTML. A suíte global terminou em `255 passed, 3 skipped, 1 warning
in 43.07s`; a advertência existente é a depreciação do `httpx` no
`starlette.testclient`.

## Critérios observados

- Execução que contém falha intencional termina como `failed`.
- Perda de conexão é registrada como observação de contrato não atendido, sem derrubar o worker.
- Redirect para destino não cadastrado é interrompido antes da chamada seguinte.
- Valores acima dos limites de carga recebem resposta 422 em vez de serem ajustados silenciosamente.
- Cancelamento interrompe novos envios e encerra o grupo do subprocesso; o filho real não permanece órfão.
- Uma execução deixada ativa antes de reinício é recuperada como `interrupted`, nunca `passed`.
- Artefatos utilizam caminho gerado pelo backend; tentativas de escapar da raiz são recusadas.
- Dados sensíveis conhecidos são redigidos em evidências e relatórios.
- Correlações temporais declaram fuso, incerteza e natureza hipotética.
- A demonstração real do contrato persistiu 11 checks e 1 conjunto de
  métricas, exibiu as 2 falhas intencionais, terminou como `failed` e exportou
  um relatório HTML de 6.475 bytes.

## Inventário e remoção anterior

As oito ferramentas foram catalogadas por inspeção estática, sem executar mecanismos ofensivos. Na busca exata sob `/home/grekas/Projetos`, não foram localizados `planejador-local`, `Planejador_Local_v0.1.0.zip` ou `Planejamento_IA_Arquiteta_v0.1.md`; nada foi removido e nenhum processo atribuível ao planejador foi encerrado. Outros projetos permaneceram intocados.

## Repetição

Use um diretório descartável para a rodada:

```bash
tmpdir="$(mktemp -d)"
VERIFICALAB_DATA="$tmpdir" verificalab migrate
VERIFICALAB_DATA="$tmpdir" verificalab demo
VERIFICALAB_DATA="$tmpdir" python -m pytest -q backend/tests
```

O diretório temporário pode ser descartado depois da inspeção manual. A aplicação não o remove automaticamente.
