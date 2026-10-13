# PyDDoS v3.0

## Como funciona

PyDDoS é um script simples com 3 tipos de ataque:

| Método | Tipo | Descrição |
|--------|------|-----------|
| `SYNFLOOD` | L4 | Flood de pacotes SYN via raw sockets (requer root) |
| `REQUEST` | L7 | HTTP flood — requisições GET em massa |
| `PYSLOW` | L7 | Slowloris — conexões lentas que esgotam threads do servidor |

O script tem interface colorida no terminal e pede os parâmetros de forma interativa.

## Dependências

```bash
pip install requests colorama termcolor
```

## Como instalar

```bash
cd pyddos/
pip install -r requirements.txt
```

## Como usar

```bash
# Rodar (menu interativo)
python3 pyddos.py

# O script vai pedir:
# 1. Tipo de ataque (SYNFLOOD / REQUEST / PYSLOW)
# 2. IP/URL do alvo
# 3. Porta
# 4. Número de threads
```

### Exemplo de sessão

```
 PyDDoS v3.0

 Select attack type:
  [1] SYNFLOOD
  [2] REQUEST
  [3] PYSLOW

> 2

 Target IP/URL: 192.168.1.100
 Port: 80
 Threads: 100

 [+] Starting REQUEST flood...
 [+] Sending requests to 192.168.1.100:80
```

## Notas

- `SYNFLOOD` requer `sudo` — usa raw sockets
- `REQUEST` e `PYSLOW` funcionam sem root
- O arquivo `ua.txt` contém user-agents aleatórios usados nas requisições HTTP

## Estrutura do projeto

```
pyddos/
├── pyddos.py       # Script principal
├── requirements.txt
└── ua.txt          # Lista de User-Agents
```

## ⚠️ Aviso Legal

Script criado para fins educacionais. Use **somente em ambientes que você tem autorização**.
