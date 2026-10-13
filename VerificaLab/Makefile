.PHONY: help bootstrap test serve tui migrate demo clean

PYTHON := .venv/bin/python
VERIFICALAB := .venv/bin/verificalab

help: ## Lista os targets disponíveis
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "%-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Cria o ambiente, instala dependências e valida o projeto
	@./bootstrap.sh

test: ## Executa a suíte de testes
	@$(PYTHON) -m pytest backend/tests -o addopts='' -ra

serve: ## Inicia API e laboratório em loopback
	@$(VERIFICALAB) serve

tui: ## Abre o painel interativo
	@$(VERIFICALAB) tui

migrate: ## Aplica migrações e semeia o catálogo
	@$(VERIFICALAB) migrate

demo: ## Cria projeto e perfis de demonstração
	@$(VERIFICALAB) demo

clean: ## Remove .venv, caches Python e frontend/node_modules (confirmação para .venv)
	@if [ -d .venv ]; then \
		printf 'Remover .venv/? [y/N] '; \
		read answer; \
		case "$$answer" in \
			y|Y|yes|YES) rm -rf -- .venv ;; \
			*) echo 'Cancelado; nenhum arquivo removido.'; exit 1 ;; \
		esac; \
	fi
	@find . -type d -name __pycache__ -prune -exec rm -rf -- {} +
	@if [ -d frontend/node_modules ]; then rm -rf -- frontend/node_modules; fi
	@echo 'Caches e dependências locais removidos.'
