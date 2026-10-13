"""Formulário de execução controlada de ferramenta."""

from __future__ import annotations

import asyncio
from ipaddress import ip_address
from urllib.parse import urlsplit

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from verificalab import config
from verificalab.core.authorization import AuthorizationError
from verificalab.stress.base import StressRequest
from verificalab.stress.registry import Tool


def _is_lab_target(value: str) -> bool:
    """Aceita apenas loopback explícito na porta do laboratório descartável."""
    target = value.strip()
    try:
        parsed = urlsplit(target if "://" in target else f"http://{target}")
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme.lower() != "http"
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or port != config.LAB_PORT
    ):
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return str(ip_address(hostname)) in {"127.0.0.1", "::1"}
    except ValueError:
        return False


class RunScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Voltar", show=False)]

    DEFAULT_CSS = """
    RunScreen {
        align: center middle;
        background: $background 80%;
    }
    #run-dialog {
        width: 72;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    #run-dialog .run-field {
        height: 3;
        align-vertical: middle;
    }
    #run-dialog .run-label {
        width: 22;
        content-align: left middle;
    }
    #run-dialog Input {
        height: 1;
        width: 1fr;
    }
    #run-buttons {
        height: 3;
        align-horizontal: right;
    }
    #run-buttons Button {
        width: 16;
    }
    #run-status {
        height: auto;
        min-height: 2;
        margin-top: 1;
    }
    """

    def __init__(self, tool: Tool) -> None:
        super().__init__()
        self.tool = tool
        self._supported = tool.id == "slowloris" and tool.installed

    def compose(self) -> ComposeResult:
        limits = self.tool.default_limits
        hint = (
            "Execução real restrita ao adapter Slowloris, loopback e porta "
            f"{config.LAB_PORT} do laboratório."
            if self._supported
            else "Sem adapter de execução revisado para esta ferramenta; nenhuma "
            "execução será iniciada."
        )
        yield Vertical(
            Static(Text(f"Executar {self.tool.name}", style="bold")),
            Static(hint, id="run-safety-hint"),
            Horizontal(
                Static("Alvo HTTP local", classes="run-label"),
                Input(
                    value=f"http://127.0.0.1:{config.LAB_PORT}",
                    placeholder="URL do laboratório local",
                    id="run-target",
                ),
                classes="run-field",
            ),
            Horizontal(
                Static("Duração (segundos)", classes="run-label"),
                Input(value=str(limits.duration_s), id="run-duration"),
                classes="run-field",
            ),
            Horizontal(
                Static("Threads", classes="run-label"),
                Input(value=str(limits.threads), id="run-threads"),
                classes="run-field",
            ),
            Static("", id="run-status"),
            Horizontal(
                Button(
                    "Executar",
                    id="run",
                    variant="primary",
                    disabled=not self._supported,
                ),
                Button("Voltar", id="run-back"),
                id="run-buttons",
            ),
            id="run-dialog",
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-back":
            self.dismiss(None)
        elif event.button.id == "run":
            await self._execute()

    async def _execute(self) -> None:
        if not self._supported:
            self._show_status("Execução indisponível para esta ferramenta.", error=True)
            return

        target = self.query_one("#run-target", Input).value.strip()
        if not _is_lab_target(target):
            self._show_status(
                f"Use somente loopback na porta {config.LAB_PORT} do laboratório.",
                error=True,
            )
            return

        try:
            duration = int(self.query_one("#run-duration", Input).value)
            threads = int(self.query_one("#run-threads", Input).value)
        except ValueError:
            self._show_status("Duração e threads devem ser números inteiros.", error=True)
            return

        limits = self.tool.max_limits
        max_duration = limits.duration_s if limits else self.tool.default_limits.duration_s
        max_threads = limits.threads if limits else self.tool.default_limits.threads
        if not 1 <= duration <= max_duration:
            self._show_status(
                f"Duração deve estar entre 1 e {max_duration} segundos.", error=True
            )
            return
        if not 1 <= threads <= max_threads:
            self._show_status(
                f"Threads devem estar entre 1 e {max_threads}.", error=True
            )
            return

        button = self.query_one("#run", Button)
        button.disabled = True
        self._show_status("Executando no laboratório local…")
        try:
            result = await asyncio.to_thread(
                self.app.run_tool,
                self.tool,
                StressRequest(target, duration_s=duration, threads=threads),
            )
        except (AuthorizationError, OSError, RuntimeError, ValueError) as exc:
            self._show_status(f"Falha na execução: {exc}", error=True)
        else:
            state = "timeout" if result.timeout else f"código {result.returncode}"
            details = (
                f"Resultado: {state}\n"
                f"Início: {result.started_at.isoformat()}\n"
                f"Fim: {result.ended_at.isoformat()}"
            )
            if result.stdout:
                details += f"\nstdout:\n{result.stdout[-2000:]}"
            if result.stderr:
                details += f"\nstderr:\n{result.stderr[-2000:]}"
            self._show_status(details, error=result.returncode != 0 or result.timeout)
        finally:
            button.disabled = not self._supported

    def _show_status(self, message: str, *, error: bool = False) -> None:
        style = "bold red" if error else "green"
        self.query_one("#run-status", Static).update(Text(message, style=style))
