"""Command line interface for the Disco EL assistant."""
from __future__ import annotations

from enum import Enum

import typer

from core.orchestrator import Orchestrator

app = typer.Typer(help="Interact with the Disco EL assistant orchestrator.")


class ProfileOption(str, Enum):
    WORK = "work"
    HOME = "home"


def _build_orchestrator(profile: ProfileOption) -> Orchestrator:
    try:
        return Orchestrator.from_profile(profile.value)
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc


@app.command()
def chat(
    profile: ProfileOption = typer.Option(
        ProfileOption.WORK,
        "--profile",
        "-p",
        case_sensitive=False,
        help="Which profile configuration to use (work or home).",
    ),
) -> None:
    """Start an interactive chat session with the orchestrator."""

    orchestrator = _build_orchestrator(profile)
    typer.secho(f"Loaded '{profile.value}' profile. Type 'exit' to quit.", fg=typer.colors.GREEN)

    integrations = orchestrator.config.get("integrations", {})
    if integrations:
        typer.secho("Active integrations:", fg=typer.colors.BLUE)
        for name, settings in integrations.items():
            enabled = settings.get("enabled", True)
            status_color = typer.colors.GREEN if enabled else typer.colors.YELLOW
            typer.secho(f"  - {name}: {'enabled' if enabled else 'disabled'}", fg=status_color)

    while True:
        try:
            message = typer.prompt("You")
        except typer.Abort:
            typer.echo("\nSession aborted.")
            raise typer.Exit(code=0)
        if message.strip().lower() in {"exit", "quit"}:
            typer.secho("Goodbye!", fg=typer.colors.GREEN)
            break
        responses = orchestrator.handle_message(message)
        for response in responses:
            typer.secho(f"[{response.skill}] {response.content}", fg=typer.colors.CYAN)


if __name__ == "__main__":
    app()
