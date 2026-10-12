# Como reproduzir do zero

Este guia descreve a instalação do VerificaLab em um checkout limpo. O
bootstrap instala dependências no `.venv/` do repositório e, se Node.js/npm
estiverem disponíveis, em `frontend/node_modules/`.

## Requisitos

- Python 3.11 ou superior.
- Git.
- Node.js 18 ou superior e npm, opcionais; necessários para instalar e compilar
  o frontend.
- Linux ou macOS recomendado. O script avisa e tenta continuar em outros
  sistemas.

## Instalação em 3 passos

```bash
git clone https://github.com/Kayquebrigadeiro/VerificaLab.git
cd VerificaLab
./bootstrap.sh
```

O script:

- Cria `.venv/` se ainda não existir.
- Instala o backend em modo editable com as dependências de teste.
- Instala as dependências frontend com `npm ci` e compila a aplicação se
  Node.js 18+ e npm estiverem disponíveis.
- Aplica migrações e semeia o catálogo.
- Cria os dados de demonstração.
- Executa a suíte de testes; resultado homologado: `258 passed, 3 skipped`.

O bootstrap é idempotente: pode ser executado novamente para atualizar as
dependências, reaplicar migrações e validar a instalação. Não usa `sudo` nem
instala dependências fora de `.venv/` e `frontend/node_modules/`.

## Uso após instalação

Na raiz do repositório:

```bash
source .venv/bin/activate
verificalab serve        # API + laboratório em loopback
verificalab tui          # painel de ferramentas
verificalab migrate      # aplica migrações e semeia o catálogo
verificalab demo         # cria projeto/perfis de exemplo
```

`serve` permanece em execução no terminal. Inicie `tui`, `migrate` ou `demo`
em outro terminal quando necessário. Consulte também
[`docs/GUIA_DE_USO.md`](GUIA_DE_USO.md).

## Verificação

Se algo der errado, execute:

```bash
make test
```

Resultado esperado: `258 passed, 3 skipped`. Um warning de depreciação de
Starlette/httpx pode aparecer, conforme a versão das dependências instaladas.

## Trocar de máquina

O repositório contém o código; `.venv/` e `frontend/node_modules/` são
específicos da máquina e não devem ser copiados como ambientes portáveis.
Clone o repositório e rode `./bootstrap.sh` novamente. Se a versão do Python
mudar, recrie o ambiente virtual antes do bootstrap:

```bash
rm -rf .venv
./bootstrap.sh
```

## Desinstalar dependências locais

```bash
make clean
```

O target pede confirmação antes de remover `.venv/`; também remove caches
`__pycache__/` do checkout e `frontend/node_modules/`.
