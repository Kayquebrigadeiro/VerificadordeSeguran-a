# ddos_tools — Ferramentas de Stress Test / DDoS (Uso Educacional)

> ⚠️ **AVISO LEGAL:** Todas as ferramentas aqui são para **uso educacional e testes autorizados** em ambientes controlados (sua própria VM, lab local, servidor de teste com permissão). Usar contra sistemas de terceiros sem autorização é **crime** (Lei 12.737/2012 no Brasil, Computer Fraud and Abuse Act nos EUA, etc.).

---

## Ferramentas disponíveis

| Pasta | Ferramenta | Linguagem | Métodos | Root? | Dificuldade |
|-------|-----------|-----------|---------|-------|-------------|
| `slowloris/` | Slowloris | Python 3 | Slowloris (L7) | Não | ⭐ Fácil |
| `pyddos/` | PyDDoS | Python 3 | SYN, HTTP, Slowloris | SYN sim | ⭐ Fácil |
| `ddoslayer/` | DDoSlayer v3 | Python 3 | HTTP, Slowloris, SYN, UDP | SYN/UDP sim | ⭐⭐ Médio |
| `impulse/` | Impulse | Python 3 | UDP, SYN, ICMP, NTP, HTTP, Slowloris... | L4 sim | ⭐⭐ Médio |
| `overload/` | Overload | Python 3 | HTTP, Slowloris, SYN, ARP, Disconnect | L4/L2 sim | ⭐⭐ Médio |
| `mhddos/` | MHDDoS | Python 3 | 57 métodos L4+L7 | SYN sim | ⭐⭐⭐ Avançado |
| `ufonet/` | UFONet | Python 3 | Open Redirect, Amplificação L3, DarkNET | Não | ⭐⭐⭐ Avançado |
| `mikumikubeam/` | MikuMikuBeam | Go | HTTP, TCP, Slowloris, Minecraft | Não | ⭐⭐ Médio |

---

## Qual ferramenta usar?

### Quero algo simples, sem instalar nada
→ **Slowloris** — só precisa de Python 3 padrão, zero dependências externas

### Quero testar um servidor web (HTTP/HTTPS)
→ **MHDDoS** (mais métodos) ou **DDoSlayer** (interface mais amigável)

### Quero testar camada 4 (TCP/UDP/SYN)
→ **Impulse** ou **Overload** — ambos usam Scapy para raw sockets

### Quero uma interface visual no browser
→ **MikuMikuBeam** — servidor web embutido com UI

### Quero a ferramenta mais completa
→ **MHDDoS** — 57 métodos, suporte a proxies, Docker

### Quero entender Open Redirects e amplificação
→ **UFONet** — mais complexo, mas o mais educativo sobre técnicas avançadas

---

## Instalação rápida por ferramenta

```bash
# Slowloris (sem dependências)
cd slowloris/
python3 slowloris.py 192.168.1.100

# PyDDoS
cd pyddos/
pip install -r requirements.txt
python3 pyddos.py

# DDoSlayer
cd ddoslayer/
pip install termcolor rich scapy requests
python3 DDoSlayer.py

# Impulse
cd impulse/
pip install -r requirements.txt
python3 impulse.py --target http://192.168.1.100 --method HTTP --time 30 --threads 50

# Overload
cd overload/
pip install -r requirements.txt
python3 overload.py

# MHDDoS
cd mhddos/
pip install -r requirements.txt
python3 start.py GET http://192.168.1.100 100 0 0 1000 60

# UFONet
cd ufonet/
pip install requests
python3 ufonet --help

# MikuMikuBeam (precisa de Go 1.24+)
cd mikumikubeam/
make build
./mmb-server
```

---

## Comparativo de métodos por camada

### Layer 7 (Aplicação / HTTP)
| Ferramenta | HTTP Flood | Slowloris | Bypass WAF | Via Proxy |
|-----------|-----------|-----------|-----------|-----------|
| Slowloris | ❌ | ✅ | ❌ | ❌ |
| PyDDoS | ✅ | ✅ | ❌ | ❌ |
| DDoSlayer | ✅ | ✅ | ❌ | ❌ |
| Impulse | ✅ | ✅ | ❌ | ❌ |
| Overload | ✅ | ✅ | ❌ | ✅ |
| MHDDoS | ✅ | ✅ | ✅ | ✅ |
| UFONet | ✅ | ❌ | ✅ | ✅ |
| MikuMikuBeam | ✅ | ✅ | ✅ | ✅ |

### Layer 4 (Transporte / TCP/UDP)
| Ferramenta | SYN | UDP | ICMP | NTP Amp | Memcached Amp |
|-----------|-----|-----|------|---------|---------------|
| Impulse | ✅ | ✅ | ✅ | ✅ | ✅ |
| Overload | ✅ | ❌ | ❌ | ❌ | ❌ |
| DDoSlayer | ✅ | ✅ | ❌ | ❌ | ❌ |
| MHDDoS | ✅ | ✅ | ✅ | ❌ | ❌ |
| UFONet | ❌ | ❌ | ❌ | ✅ | ✅ |
| MikuMikuBeam | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## Estrutura de pastas

```
ddos_tools/
├── README.md               ← este arquivo
├── slowloris/
│   ├── README_USO.md       ← como usar
│   └── slowloris.py        ← código
├── impulse/
│   ├── README_USO.md
│   ├── impulse.py
│   └── tools/
├── mhddos/
│   ├── README_USO.md
│   ├── start.py
│   └── files/
├── ddoslayer/
│   ├── README_USO.md
│   └── DDoSlayer.py
├── pyddos/
│   ├── README_USO.md
│   ├── pyddos.py
│   └── ua.txt
├── overload/
│   ├── README_USO.md
│   ├── overload.py
│   └── tools/
├── ufonet/
│   ├── README_USO.md
│   ├── ufonet
│   └── botnet/
└── mikumikubeam/
    ├── README_USO.md
    ├── cmd/
    └── internal/
```

---

## Ambiente de teste recomendado

Para testar com segurança, use uma VM isolada:

```bash
# Instalar VirtualBox + criar VM Ubuntu
# Ou usar Docker para isolar o alvo:

docker run -d -p 8888:80 --name alvo nginx
# Agora teste contra http://127.0.0.1:8888
# Quando terminar:
docker stop alvo && docker rm alvo
```

Nunca teste em redes de produção ou contra serviços que você não possui.
