# VerificaLab

> Versão atual: **0.2.0** — ver [CHANGELOG](CHANGELOG.md).

Plataforma local para executar testes controlados, preservar evidências e comparar resultados. A versão piloto opera somente contra IPs literais de loopback e não implementa mecanismos de flood, proxy, amplificação, spoofing, conexões incompletas ou tráfego distribuído.

## Início rápido

Requisitos: Python 3.11 ou superior, Node.js 18 ou superior e `npm`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
npm --prefix frontend ci
npm --prefix frontend run build
verificalab migrate
verificalab demo
verificalab serve
```

Abra `http://127.0.0.1:8400`. O servidor e o laboratório descartável escutam apenas em loopback. Para manter o laboratório desligado, use `verificalab serve --no-lab`.

Durante desenvolvimento, execute o backend e o Vite em terminais separados:

```bash
verificalab serve
npm --prefix frontend run dev
```

O frontend de desenvolvimento fica em `http://127.0.0.1:5173` e encaminha `/api` ao backend local.

## Roteiro verificável

1. Execute `verificalab demo` e inicie o servidor.
2. Em **Projetos**, abra *Laboratório VerificaLab*.
3. Execute *Contrato do laboratório*. As duas falhas intencionais devem deixar a execução vermelha; elas não são mascaradas.
4. Execute *Carga leve (2 rps, 6 s)* e confira amostras, população e unidade em **Métricas**.
5. Execute *Suíte longa*, abra a execução e cancele. O grupo de processos, incluindo o filho real, deve terminar.
6. Anexe um `.log` ao ambiente, abra uma execução e use **Correlacionar logs**. O resultado é identificado como hipótese, nunca como causa comprovada.
7. Em **Importações**, envie JUnit XML, JSON, JSONL ou DDoSlayer JSON e, se desejado, vincule-o a uma execução.
8. Em **Execuções**, selecione duas linhas para comparar; abra uma delas e exporte o relatório HTML.

## Arquitetura e contratos

- FastAPI expõe contratos Pydantic, aplica Host/Origin/CSRF e serve o frontend compilado na mesma origem.
- SQLite registra projetos, ambientes, perfis, execuções, resultados, métricas, achados, artefatos e auditoria por migrações incrementais.
- Um worker dedicado executa uma tarefa por vez e recupera execuções deixadas em `running` como `interrupted` após reinício.
- Executores HTTP validam o destino em cada salto. Redirect para outra origem é recusado antes da chamada e proxies do ambiente não são herdados.
- O gerador de carga reserva o orçamento global antes de cada envio: padrão de 1 req/s, teto de 5 req/s, concorrência 2, duração 30 s e 150 tentativas; somente GET/HEAD.
- O runner de suíte recebe argumentos em lista, sem shell, aceita apenas prefixos pytest pré-configurados, restringe o diretório e encerra o grupo de processos no cancelamento.
- Uploads têm 2 MiB no máximo. Nomes não escolhem destinos no filesystem. XML rejeita DTD/ENTITY e todos os parsers limitam profundidade ou quantidade.

Estados terminais: `passed`, `failed`, `cancelled`, `timed_out`, `interrupted` e `error`. `failed` significa que a observação não atendeu ao teste; `error` significa que o executor não conseguiu concluir.

## Stress test autorizado

O catálogo de ferramentas de stress é declarativo (`backend/config/tools.yaml`) e passa por validação antes de ser disponibilizado. A execução controlada pelo VerificaLab aceita somente loopback explícito e respeita os limites de duração e threads do catálogo. O orchestrator exige autorização antes de iniciar adapters, executa subprocessos sem shell e salva logs e relatórios JSON/Markdown/HTML em `data/`.

A TUI permite execução real somente do adapter Slowloris revisado, contra a porta loopback do laboratório descartável; as demais ferramentas permanecem indisponíveis para execução pela interface. O E2E do backend exercita o caminho integrado do orchestrator, autorização, Slowloris real, laboratório HTTP, artefato, relatórios e encerramento de processos.

**Aviso legal:** execute testes de stress somente em sistemas próprios ou com autorização expressa e dentro do escopo aprovado. O modo do VerificaLab descrito aqui destina-se ao laboratório local em loopback; não use as ferramentas contra terceiros, redes públicas ou serviços sem autorização. A autorização técnica não substitui obrigações legais nem autorização do proprietário.

## Dados, segredos e retenção

Por padrão, o banco, artefatos e segredos ficam em `data/`, com diretórios privados. Valores secretos de ambientes são cifrados e redigidos de logs, API e exportações. Os dados permanecem até remoção manual; nada é enviado para fora da máquina pela plataforma.

Para um diretório alternativo:

```bash
VERIFICALAB_DATA=/caminho/privado verificalab serve
```

## Testes

```bash
python -m pytest -q backend/tests
npm --prefix frontend run build
```

Os testes cobrem limites da API, CSRF/Host/Origin, política de destino, redirects, orçamento concorrente, timeout/cancelamento com filho real, recuperação, parsers malformados, path traversal, redação, sanitização e o fluxo real contra o laboratório.

## Limitações conhecidas

- Piloto local e de usuário único; não é sandbox para executar código desconhecido.
- O runner direto inicial é pytest. JUnit complementa outros frameworks por importação.
- MikuMikuBeam expõe estatísticas por stream, mas não foi encontrado arquivo exportável homologável; portanto não há parser inventado.
- DDoSlayer é somente importado a partir da estrutura JSON confirmada no fonte; suas contagens não são reinterpretadas como requisições HTTP.
- Cabeçalhos ausentes são observações contextuais, não vulnerabilidades automáticas.
- Métricas coletadas no cliente não representam recursos internos do servidor.

Detalhes da homologação estão em [docs/HOMOLOGACAO.md](docs/HOMOLOGACAO.md).
O fluxo e as restrições dos adapters estão descritos em [docs/STRESS_ORCHESTRATION.md](docs/STRESS_ORCHESTRATION.md).

## Documentação

- [docs/PENDENCIAS.md](docs/PENDENCIAS.md) — o que não funciona e por quê.
- [docs/GUIA_DE_USO.md](docs/GUIA_DE_USO.md) — como usar na prática.
- [docs/HOMOLOGACAO_FINAL.md](docs/HOMOLOGACAO_FINAL.md) — resultado da homologação.
- [docs/SPRINTS.md](docs/SPRINTS.md) — histórico de desenvolvimento.
