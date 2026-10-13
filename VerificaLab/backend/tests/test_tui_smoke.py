from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from functools import wraps

from rich.text import Text
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Static

from verificalab.core.runner import RunResult
from verificalab.stress.base import StressRequest
from verificalab.stress.registry import ToolRegistry
from verificalab.tui.app import VerificaLabApp
from verificalab.tui.screens.run_screen import RunScreen
from verificalab.tui.screens.tools_panel import ToolDetailsScreen


def textual_test(test_function):
    @wraps(test_function)
    def run_with_textual_pilot():
        asyncio.run(test_function())

    return run_with_textual_pilot


class FakeAdapter:
    tool_id = "slowloris"

    def __init__(self) -> None:
        self.requests: list[StressRequest] = []

    def run(self, request: StressRequest) -> RunResult:
        self.requests.append(request)
        now = datetime.now(timezone.utc)
        return RunResult(now, now, 0, "ok", "")


@textual_test
async def test_app_mounts_without_error():
    app = VerificaLabApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#tools-table", DataTable)


@textual_test
async def test_catalog_table_has_three_tools_and_expected_columns():
    app = VerificaLabApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#tools-table", DataTable)
        assert table.row_count == 3
        assert len(table.ordered_columns) == 5


@textual_test
async def test_arrow_navigation_updates_description_panel():
    app = VerificaLabApp()
    registry = ToolRegistry.load()
    descriptions = [tool.description for tool in registry]

    async with app.run_test() as pilot:
        detail = app.query_one("#tool-description", Static)
        assert detail.renderable.plain == descriptions[0]

        await pilot.press("down")
        await pilot.pause()

        assert detail.renderable.plain == descriptions[1]


@textual_test
async def test_uninstalled_tool_status_is_red():
    tools = tuple(
        replace(tool, installed=False) if tool.id == "slowloris" else tool
        for tool in ToolRegistry.load()
    )
    app = VerificaLabApp(registry=ToolRegistry(tools))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#tools-table", DataTable)
        row = next(index for index, tool in enumerate(tools) if tool.id == "slowloris")
        status = table.get_cell_at(Coordinate(row, 4))

        assert isinstance(status, Text)
        assert status.plain == "✗ faltando"
        assert status.style == "bold red"


@textual_test
async def test_r_opens_run_screen_without_starting_a_tool():
    adapter = FakeAdapter()
    app = VerificaLabApp(adapter=adapter)

    async with app.run_test() as pilot:
        await pilot.press("r")
        await pilot.pause()

        assert isinstance(app.screen, RunScreen)
        assert app.query_one("#run-target", Input).value.startswith("http://127.0.0.1:")
        assert adapter.requests == []


@textual_test
async def test_q_exits_the_application():
    app = VerificaLabApp()

    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()

        assert not app.is_running


@textual_test
async def test_i_opens_complete_details():
    app = VerificaLabApp()

    async with app.run_test() as pilot:
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(app.screen, ToolDetailsScreen)
        assert app.query_one("#tool-example", Static).renderable.plain
        assert app.query_one("#tool-risks", Static).renderable.plain
        assert app.query_one("#tool-default-limits", Static).renderable.plain


@textual_test
async def test_run_screen_uses_injected_adapter_only_for_local_lab():
    adapter = FakeAdapter()
    app = VerificaLabApp(adapter=adapter)
    tools = ToolRegistry.load().tools
    slowloris_row = next(i for i, tool in enumerate(tools) if tool.id == "slowloris")

    async with app.run_test() as pilot:
        table = app.query_one("#tools-table", DataTable)
        table.move_cursor(row=slowloris_row)
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.click("#run")
        await pilot.pause(0.1)

        assert len(adapter.requests) == 1
        assert adapter.requests[0].target.startswith("http://127.0.0.1:")
        assert adapter.requests[0].threads == 1


@textual_test
async def test_run_screen_rejects_external_targets_without_calling_adapter():
    adapter = FakeAdapter()
    app = VerificaLabApp(adapter=adapter)
    tools = ToolRegistry.load().tools
    slowloris_row = next(i for i, tool in enumerate(tools) if tool.id == "slowloris")

    async with app.run_test() as pilot:
        app.query_one("#tools-table", DataTable).move_cursor(row=slowloris_row)
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        app.query_one("#run-target", Input).value = "http://example.com:8479"
        await pilot.click("#run")
        await pilot.pause()

        assert adapter.requests == []
        assert "somente loopback" in app.query_one("#run-status", Static).renderable.plain
