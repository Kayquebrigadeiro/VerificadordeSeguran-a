.PHONY: help bootstrap test serve tui migrate demo clean

VENV    := VerificaLab/.venv
PYTHON  := $(VENV)/bin/python
VLAB    := $(VENV)/bin/verificalab

help: ## Lista os targets disponíveis
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "%-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Cria o ambiente, instala dependências e valida o projeto
	@./bootstrap.sh

test: ## Executa a suíte de testes
	@$(PYTHON) -m pytest VerificaLab/backend/tests -o addopts='' -ra

serve: ## Inicia API e laboratório em loopback
	@$(VLAB) serve

tui: ## Abre o painel interativo
	@$(VLAB) tui

migrate: ## Aplica migrações e semeia o catálogo
	@$(VLAB) migrate

demo: ## Cria projeto e perfis de demonstração
	@$(VLAB) demo

clean: ## Remove .venv, caches Python e frontend/node_modules
	@if [ -d $(VENV) ]; then \
		printf 'Remover %s/? [y/N] ' '$(VENV)'; \
		read answer; \
		case "$$answer" in \
			y|Y|yes|YES) rm -rf -- $(VENV) ;; \
			*) echo 'Cancelado.'; exit 0 ;; \
		esac; \
	fi
	@find . -type d -name __pycache__ -prune -exec rm -rf -- {} +
	@if [ -d VerificaLab/frontend/node_modules ]; then rm -rf -- VerificaLab/frontend/node_modules; fi
	@echo 'Limpeza concluída.'
