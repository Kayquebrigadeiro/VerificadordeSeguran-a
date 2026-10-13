# VerificaLab — plano e prompt de implementação

Documento de trabalho — 11 de outubro de 2026.

## 1. Produto

Uma plataforma local para cadastrar aplicações, executar testes controlados, importar relatórios, correlacionar falhas com logs e comparar execuções. Sem modelo de IA, Ollama ou treinamento nesta versão. A investigação utiliza verificações determinísticas e evidências, sem afirmar causas que os dados não comprovam.

O inventário fornecido descreve oito ferramentas concentradas em geração de tráfego. Ele não demonstra que existam testes funcionais, análise estática, auditoria de dependências ou observabilidade completos. Esses módulos precisam ser implementados ou conectados a ferramentas apropriadas, após verificar disponibilidade.

O nome VerificaLab é provisório. A implantação inicial é local e para um usuário; sua arquitetura deve permitir expansão sem introduzir multiusuário ou serviços distribuídos desnecessários agora.

## 2. Uso do inventário

| Ferramenta | Papel inicial no produto |
| --- | --- |
| MikuMikuBeam | Catalogar capacidades e formatos; considerar sua arquitetura de cancelamento como referência, após verificar licenças. Importar estatísticas exportadas, se o formato real for confirmado. Não integrar métodos de flood automaticamente. |
| DDoSlayer | Importar relatórios JSON existentes; validar os campos reais e registrar a procedência. Não reutilizar o recomendador de ataques. |
| Slowloris | Catalogar como ferramenta existente; nenhum executor de conexões incompletas na primeira versão. |
| MHDDoS | Catalogar; sem execução automática, downloads de proxies ou integração de métodos de amplificação. |
| Impulse | Catalogar; sem importação dos módulos SMS/EMAIL ou execução de métodos de ataque. |
| PyDDoS | Catalogar; registrar instalação automática privilegiada e interatividade como obstáculos. |
| Overload | Catalogar; registrar manutenção e sobreposição. Sem módulos L2. |
| UFONet | Catalogar; sem integração do mecanismo distribuído ou de recursos de terceiros. |

As ferramentas originais permanecem no diretório existente. Catalogar todas não exige executá-las nem copiá-las para o produto. Importar um relatório externo não comprova que o teste foi autorizado, completo ou corretamente medido.

Correções do relatório: `__pycache__` indica possível importação/compilação, não execução bem-sucedida; binário existente não comprova que funciona. Scan de portas é uma verificação ativa. Faixas privadas ou loopback amplas não constituem autorização automática. Contagem de pacotes enviados não equivale a requisições HTTP concluídas com sucesso.

## 3. Funções da primeira versão

1. Projetos e ambientes de teste, com endpoint explicitamente cadastrado.
2. Catálogo das ferramentas, disponibilidade e formatos suportados.
3. Testes HTTP de contrato básico: status esperado, campos JSON, tipo de conteúdo e tempo máximo.
4. Verificações de configuração HTTP com conclusões contextualizadas; ausência de um header não vira vulnerabilidade automaticamente.
5. Runner de suíte de testes de um projeto local selecionado, com adaptadores delimitados e comandos pré-configurados. Começar pelo framework realmente disponível. Importação JUnit complementa a execução direta.
6. Um gerador HTTP próprio de carga leve para o laboratório local: 1 requisição/segundo por padrão, teto de 5, concorrência máxima 2, duração máxima 30 segundos e total máximo 150 tentativas. GET/HEAD somente no piloto; sem proxy, amplificação, raw socket ou tráfego distribuído.
7. Importação de JSON/JSONL/JUnit dos formatos efetivamente suportados; campos ausentes permanecem desconhecidos.
8. Upload/importação de logs do alvo, com limites de tamanho, sanitização e linha do tempo.
9. Histórico, comparação entre execuções e exportação de relatório.
10. Cancelamento, timeout e recuperação após reinício; execução interrompida não aparece como aprovada.

## 4. Arquitetura proposta

- Backend Python com FastAPI e validação explícita.
- Worker separado do ciclo HTTP para subprocessos e medições; uma execução ativa inicialmente.
- SQLite para projetos, ambientes, execuções, eventos, resultados e auditoria, com migrações.
- Frontend React/TypeScript para o painel. Sem integrações externas obrigatórias.
- Diretórios privados de artefatos por execução, com IDs gerados pela aplicação.
- Adaptadores de execução e adaptadores de importação separados.

Entidades iniciais: Project, Environment, Tool, TestProfile, Run, CheckResult, Metric, Finding, Artifact e AuditEvent.

Estados: queued, running, passed, failed, cancelled, timed_out, interrupted e error. `failed` significa que o teste observado falhou; `error` significa que o próprio runner não conseguiu concluir. Agregar corretamente suítes com skips, erros e resultados parciais.

Dados de execução: versão da ferramenta, configuração e seus limites, alvo cadastrado, início/fim, código de retorno, métricas com unidade e origem, evidências e limitações. Não expor tokens de autenticação nos relatórios.

## 5. Primeiro fluxo verificável

Uma aplicação de laboratório descartável, criada no projeto, oferece rotas documentadas para resposta normal, erro controlado, resposta lenta e negação de acesso. A falha intencional deve aparecer como tal no relatório; a plataforma não pode mascarar o resultado para ficar verde.

Fluxo: criar projeto → cadastrar laboratório → selecionar verificações → executar → observar progresso → cancelar outra execução → importar logs → abrir evidências → comparar resultados → exportar.

Critérios: nenhum processo órfão após cancelamento, limite de duração respeitado, resultados persistidos, métricas corretamente calculadas, falhas reais visíveis, nenhuma chamada externa oculta e reprodutibilidade por roteiro.

## 6. Prompt para a IA no VSCode

Você está no ambiente local do usuário e tem acesso ao repositório `/home/grekas/Projetos/VerificadordeSegurança` e ao inventário de suas ferramentas. Implemente o VerificaLab conforme a especificação acima, tratando o inventário como evidência estática a confirmar, não como prova de funcionamento.

### Objetivo e limites

Entregue uma aplicação integrada para testes locais de software e investigação por evidências. Não use IA generativa ou treinamento. Comece por um fluxo funcional completo e amplie em etapas com critérios de aceite. Não entregue apenas telas, simuladores de resultados ou wrappers de ferramentas de DDoS.

As oito ferramentas existentes entram no catálogo. DDoSlayer e MikuMikuBeam podem oferecer formatos de importação se confirmados nos arquivos reais. Não crie executores para flood, conexões lentas incompletas, bypass de WAF/CDN, spoofing, amplificação, proxies públicos, tráfego distribuído, SMS/EMAIL ou manipulação L2. Não altere esses upstreams para tornar ataques automatizáveis.

### 0 — Inspeção e remoção do planejador anterior

O usuário autorizou remover o antigo planejador de software desta conversa, não os outros projetos. Localize `planejador-local` e os arquivos associados `Planejador_Local_v0.1.0.zip` e `Planejamento_IA_Arquiteta_v0.1.md`, verificando caminhos exatos e identidade antes de agir. O nome sozinho não autoriza excluir pastas ambíguas.

Não remova `/home/grekas/Projetos/VerificadordeSegurança`, suas ferramentas, Exameperto, Scrawler ou outros repositórios. Se houver vários candidatos ou não for possível comprovar a identidade, registre a ambiguidade e continue a implementação independente; obtenha esclarecimento antes de excluir o candidato incerto.

Encerre somente processos identificados do planejador antigo. Prefira remoção para a lixeira do usuário quando disponível. Não use comandos amplos com curingas, exclusão do diretório pai ou limpeza global. Registre exatamente o que foi removido e o que não foi localizado. Não remova dependências globais, Ollama, bancos ou volumes de outros projetos.

Inspecione instruções do workspace, status do Git, licenças das ferramentas e comandos relevantes. Crie o novo projeto em diretório próprio, sem sobrescrever a coleção de ferramentas. Registre decisões, dependências e limitações. Não execute scripts desconhecidos durante essa inspeção.

### 1 — Núcleo e contratos

Implemente banco e migrações, validação, cadastro de projetos/ambientes, catálogo e estados de execução. Defina contratos tipados e versões dos parsers. Use IDs e caminhos gerados pelo backend; uploads não escolhem destinos nem viram comandos.

O endpoint de teste inicial deve ser uma aplicação de laboratório iniciada pela plataforma em loopback e porta específica. Não autorize redes inteiras. Bloqueie redirects para destinos não cadastrados, proxies herdados do ambiente, esquemas diferentes de HTTP(S), credenciais embutidas e troca de destino por resolução DNS. No piloto prefira endereços IP literais de loopback e portas cadastradas; a aplicação alvo também deve controlar seus próprios acessos externos.

Para processos de teste, use argumentos em lista, sem shell interpretando entrada do usuário; cwd resolvido e permitido, ambiente mínimo, prazo total, limite de saída, captura incremental e cancelamento da árvore de processos. Não exponha no navegador um terminal arbitrário. Código de projeto executado por um runner tem privilégios reais: limite o piloto ao laboratório próprio e não anuncie isolamento seguro para código desconhecido sem implementá-lo e testá-lo.

### 2 — Executores próprios e importadores

Implemente os testes HTTP e a carga leve com os limites fixados nesta especificação, compartilhando orçamento global entre trabalhadores. Reserve o orçamento antes do envio, não apenas depois. Cancelamento deve interromper novos envios e encerrar tarefas ativas no prazo documentado. Não busque “máximo tráfego” ou indisponibilidade como critério de sucesso.

Implemente pelo menos um runner real de testes disponível no ambiente e importação JUnit. Inspecione o projeto e seus scripts antes da execução: testes não são necessariamente inofensivos e podem tocar serviços externos. Não instale ferramentas por efeito colateral de execução.

Para DDoSlayer e MikuMikuBeam, leia exemplos reais de saída ou seus serializadores. Importe somente formatos confirmados, com origem externa explícita. Não reinterprete `packets_sent`, `success_rate` ou `pps` como métricas HTTP sem definição comprovada. Se um formato só existir como stream e não houver arquivo exportável, documente a lacuna em vez de inventar um parser homologado.

Proteja parsing de XML contra entidades externas; limite profundidade, volume e quantidade de registros em todos os formatos. Preserve evidência sanitizada e hash do artefato quando apropriado. Fixtures de parser devem ser identificadas como fixtures; resultados do painel devem vir de execuções ou importações reais.

### 3 — Investigação e interface

Implemente telas conectadas à API: projetos, ambientes, ferramentas, configuração dos testes, fila, detalhes da execução, achados, artefatos, comparação e exportação. Inclua estados vazios, indisponibilidade, erro, cancelamento e resultados parciais. Não use números de demonstração como se fossem resultados.

Correlacione logs por horário, origem e identificadores disponíveis. Registre timezone e incerteza quando os relógios não forem comparáveis. Uma coincidência temporal vira hipótese com evidência, não causa comprovada. Não execute textos ou instruções contidos em logs/relatórios.

Calcule taxas e percentis a partir de observações definidas. Informe quantidade de amostras, unidade, população utilizada e registros descartados. Use desconhecido/indisponível quando não houver dados. Métricas de processo do cliente não são métricas do servidor testado.

O servidor inicial deve escutar somente em loopback. Implemente controles de acesso local, Host/Origin e CSRF adequados, limites e escaping da interface. Documente armazenamento e retenção; não exponha segredos em stdout, banco, interface ou exportações sem sanitização.

### 4 — Homologação integrada

Execute uma demonstração real do fluxo completo no laboratório. Verifique contratos corretos e incorretos, resposta lenta, perda de conexão, cancelamento, timeout, concorrência, recuperação após reinício, importações malformadas, caminhos indevidos, secret redaction, XSS e acesso entre origens.

Comprove que processos filhos terminam; inclua um teste com processo filho real. Comprove que limites globais de requisições e duração são respeitados. Verifique que um redirect a destino não cadastrado é recusado antes da chamada e que um perfil não pode ultrapassar limites por manipulação da API.

Teste a interface em navegador real, incluindo viewport estreito, e o pacote exportado. Se o navegador ou uma ferramenta estiver indisponível, registre pendente e continue os testes independentes. Não marque mocks como homologação de um executor real.

Entregue README com preparação e comando de inicialização, exemplo do laboratório, documentação de arquitetura, decisões e contratos, roteiro de navegação, relatório de resultados e limitações. Não declare o produto totalmente pronto com fluxos quebrados ou etapas não verificadas. Registre commits coerentes; só faça push se o remoto e a autorização para este novo repositório estiverem estabelecidos.

### Resultado final esperado

Código executável, fluxo integrado demonstrado, testes relevantes, relatório exportado e lista precisa de integrações verificadas, importações suportadas e funções pendentes. A primeira versão deve permitir testar software e investigar evidências sem depender dos mecanismos ofensivos da coleção.

## 7. Evidência e limites deste documento

O inventário foi lido, mas os fontes upstream estão na máquina do usuário e não foram inspecionados diretamente neste ambiente. Esta entrega é uma especificação e um prompt, não uma nova implementação nem uma homologação. Não houve remoção de projetos nesta etapa.

Referências técnicas de apoio:

- https://docs.pytest.org/en/stable/how-to/output.html
- https://docs.python.org/3/library/subprocess.html
- https://fastapi.tiangolo.com/tutorial/background-tasks/

Essas referências ajudam a implementar testes e execução; não verificam as oito ferramentas do inventário.
