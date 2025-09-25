"""Command-line interface for interacting with the assistant."""
from __future__ import annotations

import json

import typer

from core import build_assistant, load_profile
from core.orchestrator import DialogueOrchestrator

app = typer.Typer(help="Интерактивный CLI для общения с ассистентом.")


@app.command()
def chat(
    profile: str = typer.Option(..., "--profile", "-p", help="Имя конфигурационного профиля."),
    history_limit: int = typer.Option(
        6, "--history-limit", "-h", help="Количество последних сообщений для контекста."
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Выводить диагностическую информацию после ответа."
    ),
) -> None:
    """Запустить интерактивный чат с ассистентом."""

    try:
        config = load_profile(profile)
    except FileNotFoundError as exc:
        typer.secho(f"Профиль '{profile}' не найден: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as exc:  # pragma: no cover - защитное сообщение для CLI
        typer.secho(f"Не удалось загрузить профиль '{profile}': {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    orchestrator: DialogueOrchestrator = build_assistant(config)
    orchestrator.history_limit = history_limit

    typer.echo("Введите сообщение для ассистента. Пустая строка или команда /exit завершит работу.")

    while True:
        try:
            user_input = input("> ")
        except EOFError:  # pragma: no cover - интерактивный ввод
            typer.echo()
            break
        except KeyboardInterrupt:  # pragma: no cover - интерактивный ввод
            typer.echo("\nВыход по запросу пользователя.")
            break

        trimmed = user_input.strip()
        if not trimmed or trimmed == "/exit":
            typer.echo("Завершение работы CLI.")
            break

        try:
            result = orchestrator.process_user_input(user_input)
        except ValueError as exc:
            typer.secho(f"Ошибка ввода: {exc}", fg=typer.colors.YELLOW)
            continue
        except Exception as exc:  # pragma: no cover - защитное сообщение для CLI
            typer.secho(f"Не удалось обработать запрос: {exc}", fg=typer.colors.RED)
            continue

        skill = result.get("skill", "unknown")
        response = result.get("response", "")
        typer.echo(f"[{skill}] {response}")

        if debug:
            decision = result.get("decision")
            if decision is not None:
                typer.secho(
                    "[DEBUG] Оценки навыков: "
                    + json.dumps(getattr(decision, "scores", {}), ensure_ascii=False, indent=2),
                    fg=typer.colors.BLUE,
                )


if __name__ == "__main__":  # pragma: no cover - точка входа для запуска модуля
    app()
