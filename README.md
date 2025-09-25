# Disco EL Assistant

Disco EL Assistant is a lightweight playground for experimenting with a local
orchestrator and multiple user interfaces. The project ships with:

- a rule-based demo orchestrator that loads profile-specific configurations and
  knowledge bases,
- an advanced `DialogueOrchestrator` with memory management and pluggable skill
  routing,
- Typer-based CLI and FastAPI web UI for chatting with the assistant, and
- configuration scaffolding for work and home profiles, including local
  knowledge base examples.

## Project structure

```
core/          # Orchestrators, memory management and shared helpers
skills/        # Example skill implementations used by the advanced orchestrator
config/        # Profile configuration files (base/work/home, skill matrix, etc.)
interfaces/    # User interfaces (CLI and web)
services/      # Integrations such as the OpenAI client wrapper
scripts/       # Utility scripts like environment bootstrapping
```

## Quick start

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-org/disco_el_assistant.git
   cd disco_el_assistant
   ```

2. **Prepare a virtual environment and install dependencies**

   You can run the helper script:

   ```bash
   ./scripts/setup_env.sh
   ```

   or perform the steps manually:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   ```

   Update the copied file with your secrets. Core variables include:

   | Variable | Description |
   | --- | --- |
   | `OPENAI_API_KEY` | OpenAI API key used by the advanced orchestrator. |
   | `ASSISTANT_PROFILE` | Default profile (`base`, `work`, `home`, etc.). |
   | `VECTOR_DB_URL` | Optional connection string to a vector database. |
   | `ENVIRONMENT` | Runtime environment name (`development`, `production`). |
   | `LOG_LEVEL` | Log verbosity for services. |
   | `CONFIG_PATH` | Default path to the profile configuration file. |
   | `WORKSPACE_DIR` | Directory for temporary files and exports. |

   Additional variables enable integrations for the CLI/web demo (Slack and
   Telegram tokens for both work and home profiles).

4. **Review profile configuration**

   Profiles live in `config/work.yaml` and `config/home.yaml` and inherit from
   `config/base.yaml`. The files describe integrations (Slack, Telegram,
   knowledge bases), vector-store collections, and profile-specific fallbacks.
   Edit them to match your environment or add new profiles by creating additional
   YAML files that inherit from `base`.

## Command-line interface

Launch an interactive chat session with the demo orchestrator:

```bash
python -m interfaces.cli chat --profile work
```

Use `--profile home` for the personal configuration. Type `exit` or `quit` to
end the session. The CLI prints which integrations are enabled for the selected
profile and streams skill responses as they are produced.

## Web interface

Run the FastAPI server with Uvicorn to access the lightweight SPA:

```bash
uvicorn interfaces.web.app:app --reload --port 8000
```

Then open <http://localhost:8000>. Choose a profile from the drop-down, send a
message, and inspect the live conversation history.

## Working with the advanced orchestrator

Developers can interact with the more sophisticated `DialogueOrchestrator` from
`core.orchestrator`. It coordinates OpenAI-backed skills, keeps both short-term
and optional long-term memory, and uses a skill matrix to resolve conflicts.
Skill configuration files live under `skills/config/`, and the skill registry is
exposed via `skills/__init__.py`.

Key helpers:

- `core.load_profile_config` – loads and merges profile YAML files with
  inheritance support.
- `core.DialogueOrchestrator` – stateful orchestrator using the OpenAI client
  and memory abstractions.
- `core.Orchestrator` – rule-based orchestrator used by the sample CLI and web
  UI, featuring a simple knowledge base loader.

## Security guidance

- **Secret management:** keep API keys and tokens in the local `.env` file or a
  dedicated secret manager. Never commit them to version control.
- **Profile isolation:** work and home profiles read from different environment
  variable names to avoid mixing credentials.
- **Logging:** redact tokens and sensitive data if you extend logging or add
  persistence. Avoid writing secrets to stdout or shared log files.
- **Knowledge bases:** limit file permissions for YAML knowledge bases so only
  trusted users can edit them.

## Extending the assistant

- **Add a new CLI/Web demo skill:** create a class in `core/skills.py` that
  implements `respond`, then register it inside `Orchestrator._build_skills`.
- **Add a new advanced skill:** implement a subclass of `skills.base.BaseSkill`
  and register it in `skills/__init__.py`. Provide configuration under
  `skills/config/` to control prompts, weights, and behaviour.
- **Persist conversations:** extend `core.orchestrator.DialogueOrchestrator` to
  plug in a long-term memory backend (e.g., `SQLiteLongTermMemory` in
  `core/memory.py`) or integrate a vector store referenced from the profile
  configuration.

## Быстрый старт (кратко на русском)

1. Скопируйте окружение: `cp .env.example .env`.
2. Запустите установку зависимостей: `./scripts/setup_env.sh` либо активируйте
   виртуальное окружение и выполните `pip install -r requirements.txt`.
3. Обновите переменные окружения (`OPENAI_API_KEY`, `ASSISTANT_PROFILE`,
   `VECTOR_DB_URL` и др.) и настройте профили в `config/base.yaml`,
   `config/work.yaml`, `config/home.yaml`.

Скрипт `scripts/setup_env.sh` создаст виртуальное окружение, установит
зависимости и подготовит `.env` при первом запуске.

Happy experimenting!
