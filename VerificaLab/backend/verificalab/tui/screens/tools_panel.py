"""Painel de catálogo e detalhes das ferramentas disponíveis."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Static

from verificalab.stress.registry import Tool, ToolRegistry
from verificalab.tui.widgets import ToolDetails, installation_status


class ToolDetailsScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Fechar", show=False)]

    DEFAULT_CSS = """
    ToolDetailsScreen {
        align: center middle;
        background: $background 80%;
    }
    #tool-details-dialog {
        width: 80%;
        height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    """

    def __init__(self, tool: Tool) -> None:
        super().__init__()
        self.tool = tool

    def compose(self) -> ComposeResult:
        tool = self.tool
        yield Vertical(
            Static(Text(f"{tool.name} — detalhes completos", style="bold")),
            Static(
                Text(
                    f"ID: {tool.id}  ·  Linguagem: {tool.language}  ·  "
                    f"Camada: {tool.layer}  ·  Root: "
                    f"{'sim' if tool.requires_root else 'não'}\n"
                    f"Caminho: {tool.path}  ·  "
                    f"Instalada: {'sim' if tool.installed else 'não'}"
                )
            ),
            VerticalScroll(ToolDetails(tool)),
            Button("Fechar", id="close-details"),
            id="tool-details-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-details":
            self.dismiss(None)


class ToolsPanel(Vertical):
    """Tabela navegável e painel lateral sincronizado com o cursor."""

    BINDINGS = [
        Binding("q", "quit_app", "Sair"),
        Binding("r", "run_selected", "Executar"),
        Binding("i", "show_details", "Detalhes"),
    ]

    DEFAULT_CSS = """
    ToolsPanel {
        height: 1fr;
        padding: 0 1;
    }
    #tools-layout {
        height: 1fr;
    }
    #catalog-column {
        width: 58%;
        height: 1fr;
        padding-right: 1;
    }
    #details-column {
        width: 42%;
        height: 1fr;
        padding-left: 1;
    }
    #panel-title {
        height: 2;
        text-style: bold;
        padding: 0 1;
    }
    #tools-table {
        height: 1fr;
    }
    #panel-hint {
        height: 2;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__()
        self.registry = registry

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                Static("Ferramentas do catálogo", id="panel-title"),
                DataTable(id="tools-table", cursor_type="row", zebra_stripes=True),
                Static("↑/↓ navegar · r executar · i detalhes · q sair", id="panel-hint"),
                id="catalog-column",
            ),
            VerticalScroll(
                ToolDetails(id="tool-details"),
                id="details-column",
            ),
            id="tools-layout",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tools-table", DataTable)
        table.add_columns("ID", "Nome", "Camada", "Root?", "Status")
        for tool in self.registry:
            table.add_row(
                tool.id,
                tool.name,
                tool.layer,
                "Sim" if tool.requires_root else "Não",
                installation_status(tool),
                key=tool.id,
            )
        if self.registry.tools:
            table.move_cursor(row=0)
            self.query_one("#tool-details", ToolDetails).show_tool(
                self.registry.tools[0]
            )
        table.focus()

    @property
    def selected_tool(self) -> Tool | None:
        table = self.query_one("#tools-table", DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return None
        row = table.get_row_at(table.cursor_row)
        return self.registry.get(str(row[0]))

    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ) -> None:
        tool = self.registry.get(event.row_key.value)
        if tool is not None:
            self.query_one("#tool-details", ToolDetails).show_tool(tool)

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_run_selected(self) -> None:
        tool = self.selected_tool
        if tool is not None:
            from verificalab.tui.screens.run_screen import RunScreen

            self.app.push_screen(RunScreen(tool))

    def action_show_details(self) -> None:
        tool = self.selected_tool
        if tool is not None:
            self.app.push_screen(ToolDetailsScreen(tool))
