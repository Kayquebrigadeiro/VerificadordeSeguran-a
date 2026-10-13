"""Aplicação Textual do painel de ferramentas VerificaLab."""

from __future__ import annotations

from textual.app import App, ComposeResult

from verificalab.core.authorization import AuthorizationError
from verificalab.core.runner import RunResult
from verificalab.stress.adapters.slowloris import SlowlorisAdapter
from verificalab.stress.base import StressAdapter, StressRequest
from verificalab.stress.registry import Tool, ToolRegistry
from verificalab.tui.screens.tools_panel import ToolsPanel


class VerificaLabApp(App[None]):
    TITLE = "VerificaLab — Ferramentas"
    SUB_TITLE = "Catálogo e execução em laboratório local"
    CSS = """
    Screen {
        background: $background;
    }
    """

    def __init__(
        self,
        *,
        registry: ToolRegistry | None = None,
        adapter: StressAdapter | None = None,
    ) -> None:
        super().__init__()
        self.registry = registry if registry is not None else ToolRegistry.load()
        self.adapter = adapter if adapter is not None else SlowlorisAdapter()

    def compose(self) -> ComposeResult:
        yield ToolsPanel(self.registry)

    def run_tool(self, tool: Tool, request: StressRequest) -> RunResult:
        """Executa somente o adapter revisado, contra o laboratório loopback."""
        if tool.id != "slowloris" or self.adapter.tool_id != tool.id:
            raise ValueError(
                f"não há adapter de execução revisado para {tool.name}"
            )
        if not tool.installed:
            raise ValueError(f"ferramenta não instalada: {tool.name}")

        from verificalab.tui.screens.run_screen import _is_lab_target

        if not _is_lab_target(request.target):
            raise AuthorizationError(
                "a TUI só permite o alvo loopback na porta do laboratório local"
            )
        return self.adapter.run(request)
