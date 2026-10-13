"""Widgets reutilizados pelo painel TUI."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from verificalab.stress.registry import Tool


def installation_status(tool: Tool) -> Text:
    """Retorna o status colorido usado pela tabela de ferramentas."""
    if tool.installed:
        return Text("✓ instalado", style="bold green")
    return Text("✗ faltando", style="bold red")


class ToolDetails(Vertical):
    """Painel lateral com instruções e limites do item selecionado."""

    DEFAULT_CSS = """
    ToolDetails {
        height: auto;
        padding: 1 2;
        border: round $primary;
    }
    ToolDetails .detail-label {
        margin-top: 1;
        text-style: bold;
        color: $accent;
    }
    ToolDetails .detail-value {
        height: auto;
        padding-left: 1;
    }
    """

    def __init__(self, tool: Tool | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tool = tool

    def compose(self) -> ComposeResult:
        yield Static("Selecione uma ferramenta", id="tool-detail-title")
        yield Static("Descrição", classes="detail-label")
        yield Static("—", id="tool-description", classes="detail-value")
        yield Static("Quando usar", classes="detail-label")
        yield Static("—", id="tool-when-to-use", classes="detail-value")
        yield Static("Exemplo", classes="detail-label")
        yield Static("—", id="tool-example", classes="detail-value")
        yield Static("Riscos", classes="detail-label")
        yield Static("—", id="tool-risks", classes="detail-value")
        yield Static("Limites padrão", classes="detail-label")
        yield Static("—", id="tool-default-limits", classes="detail-value")

    def on_mount(self) -> None:
        if self._tool is not None:
            self.show_tool(self._tool)

    def show_tool(self, tool: Tool) -> None:
        self.query_one("#tool-detail-title", Static).update(
            Text(f"{tool.name} ({tool.id})", style="bold")
        )
        self.query_one("#tool-description", Static).update(Text(tool.description))
        self.query_one("#tool-when-to-use", Static).update(Text(tool.when_to_use))
        self.query_one("#tool-example", Static).update(Text(tool.example))
        self.query_one("#tool-risks", Static).update(
            Text("\n".join(f"• {risk}" for risk in tool.risks))
        )
        limits = tool.default_limits
        self.query_one("#tool-default-limits", Static).update(
            Text(
                f"{limits.duration_s}s · {limits.threads} thread(s) · "
                f"rate limit {limits.rate_limit}"
            )
        )
