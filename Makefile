.PHONY: help bootstrap test serve tui migrate demo clean

PYTHON := .venv/bin/python
VERIFICALAB := .venv/bin/verificalab

help: ## Lista os targets disponíveis
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "%-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Cria o ambiente, instala dependências e valida o projeto
	@./bootstrap.sh

test: ## Executa a suíte de testes
	@cd VerificaLab && ../$(PYTHON) -m pytest backend/tests -o addopts='' -ra

serve: ## Inicia API e laboratório em loopback
	@cd VerificaLab && ../$(VERIFICALAB) serve

tui: ## Abre o painel interativo
	@cd VerificaLab && ../$(VERIFICALAB) tui

migrate: ## Aplica migrações e semeia o catálogo
	@cd VerificaLab && ../$(VERIFICALAB) migrate

demo: ## Cria projeto e perfis de demonstração
	@cd VerificaLab && ../$(VERIFICALAB) demo

clean: ## Remove .venv, caches Python e frontend/node_modules
	@if [ -d .venv ]; then \
		printf 'Remover .venv/? [y/N] '; \
		read answer; \
		case "$$answer" in \
			y|Y|yes|YES) rm -rf -- .venv ;; \
			*) echo 'Cancelado.'; exit 0 ;; \
		esac; \
	fi
	@find . -type d -name __pycache__ -prune -exec rm -rf -- {} +
	@if [ -d VerificaLab/frontend/node_modules ]; then rm -rf -- VerificaLab/frontend/node_modules; fi
	@echo 'Limpeza concluída.'
