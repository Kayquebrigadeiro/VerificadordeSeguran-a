# Overload — Network Stress Testing Tool

## Como funciona

Overload é um toolkit de stress test com suporte a múltiplas camadas de rede, com interface interativa no terminal:

| Método | Camada | Descrição |
|--------|--------|-----------|
| `http` | L7 | HTTP flood direto |
| `http-proxy` | L7 | HTTP flood via proxies |
| `slowloris` | L7 | Slowloris direto |
| `slowloris-proxy` | L7 | Slowloris via proxies |
| `syn-flood` | L4 | SYN flood via Scapy (requer root) |
| `arp-spoof` | L2 | ARP spoofing na rede local |
| `disconnect` | L2 | Desconectar dispositivos da rede local |

> **Nota:** O projeto está arquivado (sem manutenção ativa), mas o código funciona.

## Dependências

```bash
pip install requests colorama humanfriendly PySocks scapy get_mac
```

## Como instalar

```bash
cd overload/
pip install -r requirements.txt
```

## Como usar

```bash
# Rodar (menu interativo)
python3 overload.py

# O script vai perguntar:
# 1. Método de ataque
# 2. URL/IP do alvo
# 3. Número de threads
# 4. Duração
```

### Exemplo de sessão

```
 [?] Method: http
 [?] Target URL: http://192.168.1.100
 [?] Threads: 100
 [?] Duration (seconds): 60

 [+] Starting HTTP flood...
 [+] Requests sent: 1523 | Threads: 100
```

### Métodos L2 (rede local)

```bash
# Para arp-spoof e disconnect, o script lista os IPs da rede local
# e pede para escolher o alvo

sudo python3 overload.py
# [?] Method: arp-spoof
# [?] Target IP (local): 192.168.1.50
```

## Estrutura do projeto

```
overload/
├── overload.py         # Ponto de entrada
├── requirements.txt
├── pyproject.toml
└── tools/
    ├── L2/
    │   ├── arp-spoof.py
    │   └── disconnect.py
    ├── L4/
    │   └── syn-flood.py
    └── L7/
        ├── http.py
        ├── http-proxy.py
        └── (slowloris)
```

## Notas

- `syn-flood` e métodos L2 requerem `sudo`
- Proxies são buscados automaticamente de fontes públicas quando necessário
- Compatível com Linux, Windows e Termux

## ⚠️ Aviso Legal

Use **somente em ambientes que você tem autorização**. Métodos L2 afetam toda a rede local — use apenas em lab isolado.
