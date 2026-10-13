# DDoSlayer v3.0 — Advanced DDoS Testing Framework

## Como funciona

DDoSlayer é um framework de teste de stress com interface rica no terminal (usa a biblioteca `rich`). Suporta múltiplos métodos de ataque:

| Método | Tipo | Descrição |
|--------|------|-----------|
| HTTP Flood | L7 | Requisições HTTP GET em massa com threads |
| Slowloris | L7 | Conexões lentas que esgotam o pool de threads do servidor |
| SYN Flood | L4 | Flood de pacotes SYN via Scapy (requer root) |
| UDP Flood | L4 | Flood de pacotes UDP via Scapy (requer root) |

A interface exibe estatísticas em tempo real: pacotes enviados, threads ativas, tempo decorrido.

**Dependências opcionais:**
- `rich` — interface visual avançada no terminal (recomendado)
- `scapy` — necessário para métodos L4 (SYN, UDP)

## Dependências

```bash
pip install termcolor rich scapy requests
```

## Como instalar

```bash
cd ddoslayer/
pip install termcolor rich scapy requests
```

## Como usar

```bash
# Rodar o script (menu interativo)
python3 DDoSlayer.py

# O script vai pedir:
# 1. Método de ataque
# 2. Alvo (IP ou URL)
# 3. Porta
# 4. Número de threads
# 5. Duração
```

### Exemplo de sessão interativa

```
[*] Select attack method:
  [1] HTTP Flood
  [2] Slowloris
  [3] SYN Flood (requires root)
  [4] UDP Flood (requires root)

> 1

[*] Target URL/IP: 192.168.1.100
[*] Port [80]: 80
[*] Threads [100]: 200
[*] Duration (seconds) [60]: 60

[+] Starting HTTP Flood against 192.168.1.100:80
[+] Threads: 200 | Duration: 60s
```

## Estrutura do projeto

```
ddoslayer/
└── DDoSlayer.py    # Script único, tudo em um arquivo
```

## Notas importantes

- Métodos SYN e UDP requerem `sudo` (raw sockets via Scapy)
- Se `rich` não estiver instalado, a UI cai para modo texto simples
- Se `scapy` não estiver instalado, apenas métodos HTTP/Slowloris ficam disponíveis

## ⚠️ Aviso Legal

Use **somente em ambientes que você tem autorização**. Projeto criado para fins educacionais e testes autorizados de segurança.
