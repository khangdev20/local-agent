"""
CLI interface: Rich terminal UI with real-time streaming.
Usage:
  python -m interfaces.cli                    # interactive chat
  python -m interfaces.cli "fix this bug"    # one-shot mode
  python -m interfaces.cli --model qwen3:8b
"""
from __future__ import annotations

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from agent.core import Agent, Step
from agent.default_task import get_default_task

app = typer.Typer(help="Local AI Coding Agent — powered by Ollama")
console = Console()


# ── CLI Commands ──────────────────────────────────────────────────────────────

@app.command()
def chat(
    task: Optional[str] = typer.Argument(None, help="One-shot task (skip interactive mode)"),
    model: str = typer.Option("qwen3:8b", "--model", "-m", help="Ollama model name"),
    ollama_url: str = typer.Option("http://localhost:11434", "--url", help="Ollama API URL"),
    auto_confirm: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm all actions"),
    max_steps: int = typer.Option(15, "--max-steps", help="Max agent steps per task"),
    run_default: bool = typer.Option(False, "--default-task", help="Run the default idle engineering learning task once"),
):
    """Start the AI coding agent."""
    asyncio.run(_main(task, model, ollama_url, auto_confirm, max_steps, run_default))


@app.command()
def models(
    ollama_url: str = typer.Option("http://localhost:11434", "--url"),
):
    """List available Ollama models."""
    asyncio.run(_list_models(ollama_url))


@app.command()
def history(n: int = typer.Option(10, "--n", help="Number of recent turns to show")):
    """Show recent conversation history."""
    from agent.memory import Memory
    mem = Memory()
    turns = mem.get_recent(n)
    if not turns:
        console.print("[dim]No history yet.[/dim]")
        return
    for i, t in enumerate(turns, 1):
        console.print(Panel(t["user"], title=f"[bold cyan]You #{i}[/]", border_style="cyan"))
        console.print(Panel(Markdown(t["assistant"]), title=f"[bold green]Agent #{i}[/]", border_style="green"))


# ── Main async logic ──────────────────────────────────────────────────────────

async def _main(task, model, ollama_url, auto_confirm, max_steps, run_default):
    _print_banner(model)

    # Check Ollama is running
    if not await _check_ollama(ollama_url):
        return

    agent = Agent(
        model=model,
        ollama_url=ollama_url,
        max_steps=max_steps,
        temperature=0.2,
    )
    agent.safety.auto_confirm = auto_confirm

    if run_default and not task:
        await _run_task(agent, get_default_task(), display_task="Default idle task")
    elif task:
        # One-shot mode
        await _run_task(agent, task)
    else:
        # Interactive chat loop
        console.print("[dim]Type your task. Press Enter on an empty prompt to run the default idle task. Commands: /exit /history /clear /models /default[/dim]\n")
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]You[/]")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input.strip():
                await _run_task(agent, get_default_task(), display_task="Default idle task")
                continue

            cmd = user_input.strip().lower()
            if cmd in ("/exit", "/quit", "/q"):
                console.print("[dim]Goodbye![/dim]")
                break
            elif cmd == "/history":
                turns = agent.memory.get_recent(5)
                for t in turns:
                    console.print(f"[cyan]You:[/] {t['user'][:80]}...")
                continue
            elif cmd == "/clear":
                agent.memory.clear_short()
                console.print("[dim]Memory cleared.[/dim]")
                continue
            elif cmd == "/models":
                await _list_models(ollama_url)
                continue
            elif cmd == "/default":
                await _run_task(agent, get_default_task(), display_task="Default idle task")
                continue

            await _run_task(agent, user_input)

    await agent.close()


async def _run_task(agent: Agent, task: str, display_task: str | None = None):
    console.print()
    console.print(Rule(f"[bold]{display_task or 'Task'}[/]"))

    step_count = 0
    final_answer = ""

    async def confirm_fn(tool_name: str, args: dict) -> bool:
        prompt_text = agent.safety.format_confirmation_prompt(tool_name, args)
        console.print(Panel(prompt_text, border_style="yellow", title="[yellow]Confirm Action[/]"))
        return Confirm.ask("Proceed?", default=False)

    with console.status("[bold green]Agent thinking...[/]", spinner="dots") as status:
        try:
            async for event in agent.stream(task, confirm_fn=confirm_fn):
                if event["type"] == "step":
                    step = event["data"]
                    step_count += 1
                    status.stop()
                    _print_step(step, step_count)
                    status.start()

                elif event["type"] == "final":
                    status.stop()
                    final_answer = event["data"]["answer"]
                    elapsed = event["data"]["elapsed"]
                    _print_final(final_answer, elapsed, step_count)

                elif event["type"] == "error":
                    status.stop()
                    console.print(Panel(
                        f"[red]{event['data']['message']}[/]",
                        title="[red]Error[/]",
                        border_style="red"
                    ))
        except Exception as e:
            status.stop()
            console.print(f"[red]Error: {e}[/]")


def _print_step(step: dict, num: int):
    tool_name = step.get("tool_name")
    thought = step.get("thought", "")
    result = step.get("tool_result", "")

    if tool_name:
        args_preview = str(step.get("tool_args", {}))[:100]
        header = Text()
        header.append(f"Step {num} ", style="bold dim")
        header.append(f"→ {tool_name}", style="bold yellow")
        header.append(f"  {args_preview}", style="dim")
        console.print(header)

        if result:
            preview = result[:300] + ("..." if len(result) > 300 else "")
            console.print(Panel(preview, border_style="dim", padding=(0, 1)))
    elif thought:
        console.print(Text(f"[Thinking] {thought[:200]}", style="dim italic"))


def _print_final(answer: str, elapsed: float, steps: int):
    console.print()
    console.print(Rule("[bold green]Answer[/]"))
    console.print(Markdown(answer))
    console.print(Rule(f"[dim]Done in {elapsed}s · {steps} steps[/dim]", style="dim"))
    console.print()


def _print_banner(model: str):
    console.print(Panel(
        f"[bold cyan]Local AI Coding Agent[/]\n"
        f"[dim]Model: [white]{model}[/white] · Powered by Ollama[/]",
        border_style="cyan",
        padding=(0, 2),
    ))


async def _check_ollama(url: str) -> bool:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{url}/api/tags")
            if r.status_code == 200:
                return True
    except Exception:
        pass
    console.print(Panel(
        f"[red]Cannot connect to Ollama at {url}[/]\n\n"
        "[yellow]Start Ollama:[/]\n"
        "  ollama serve\n\n"
        "[yellow]Install a model:[/]\n"
        "  ollama pull qwen3:8b",
        title="[red]Ollama Not Found[/]",
        border_style="red",
    ))
    return False


async def _list_models(url: str):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{url}/api/tags")
            models = r.json().get("models", [])
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        return

    table = Table(title="Available Ollama Models")
    table.add_column("Name", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Modified", style="dim")

    for m in models:
        size_gb = m.get("size", 0) / 1e9
        table.add_row(m["name"], f"{size_gb:.1f} GB", m.get("modified_at", "")[:10])

    console.print(table)


if __name__ == "__main__":
    app()
