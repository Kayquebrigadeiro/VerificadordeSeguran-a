# Impulse — Modern Denial-of-Service Toolkit

## Como funciona

Impulse é um toolkit de stress test com múltiplos métodos de ataque organizados por camada de rede:

| Método | Camada | Descrição |
|--------|--------|-----------|
| `UDP` | L4 | Flood de pacotes UDP |
| `SYN` | L4 | SYN flood — esgota tabela de conexões TCP |
| `ICMP` | L4 | Ping flood (Ping of Death) |
| `NTP` | L4 | Amplificação via servidores NTP públicos |
| `MEMCACHED` | L4 | Amplificação via servidores Memcached expostos |
| `POD` | L4 | Ping of Death com pacotes oversized |
| `HTTP` | L7 | HTTP flood — requisições GET/POST em massa |
| `SLOWLORIS` | L7 | Conexões lentas que esgotam threads do servidor |
| `EMAIL` | App | Flood de e-mails para um endereço |
| `SMS` | App | Flood de SMS para um número |

Os métodos L4 (SYN, ICMP, NTP, MEMCACHED) requerem **root/sudo** pois usam raw sockets via Scapy.

## Dependências

```bash
pip install requests scapy colorama humanfriendly
# Para métodos L4 (raw sockets):
sudo apt install python3-scapy  # ou via pip com sudo
```

## Como instalar

```bash
cd impulse/
pip install -r requirements.txt
```

## Como usar

```bash
# Sintaxe geral
python3 impulse.py --target <alvo> --method <MÉTODO> --time <segundos> --threads <N>

# HTTP flood por 60 segundos com 50 threads
python3 impulse.py --target http://192.168.1.100 --method HTTP --time 60 --threads 50

# UDP flood em IP:porta
python3 impulse.py --target 192.168.1.100:80 --method UDP --time 30 --threads 10

# SYN flood (requer sudo)
sudo python3 impulse.py --target 192.168.1.100:80 --method SYN --time 30 --threads 5

# Slowloris via Impulse
python3 impulse.py --target http://192.168.1.100 --method SLOWLORIS --time 120 --threads 20

# NTP amplification (requer sudo)
sudo python3 impulse.py --target 192.168.1.100:123 --method NTP --time 30 --threads 5
```

## Parâmetros

| Parâmetro | Descrição |
|-----------|-----------|
| `--target` | IP:porta, URL ou telefone (depende do método) |
| `--method` | Método de ataque (ver tabela acima) |
| `--time` | Duração em segundos (padrão: 10) |
| `--threads` | Número de threads (1–200, padrão: 3) |

## Estrutura do projeto

```
impulse/
├── impulse.py          # Ponto de entrada
├── requirements.txt
└── tools/
    ├── L4/             # Ataques de camada 4 (UDP, SYN, ICMP, NTP...)
    ├── L7/             # Ataques de camada 7 (HTTP, Slowloris)
    ├── EMAIL/          # Flood de e-mail
    └── SMS/            # Flood de SMS
```

## ⚠️ Aviso Legal

Use **somente em ambientes que você tem autorização**. Métodos L4 requerem root e enviam pacotes raw — use apenas em lab isolado.
