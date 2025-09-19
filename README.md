# Disco EL Assistant

Disco EL Assistant is a lightweight environment for experimenting with a local
skill orchestrator. Two profiles are provided: a "work" profile that mimics an
enterprise environment and a "home" profile for personal automations. The
project ships with both a Typer based CLI and an optional FastAPI + SPA web UI
so you can test skills in whichever environment fits best.

## Requirements

- Python 3.10+
- A virtual environment manager such as `venv`, `conda` or `pipenv`
- (Optional) Node-free environment for the SPA – all assets are served as plain HTML/CSS/JS

## Quick start

Follow the same steps on both your work and home machines. Use different
profiles to switch behaviours and integrations.

### 1. Clone the repository

```bash
git clone https://github.com/your-org/disco_el_assistant.git
cd disco_el_assistant
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the template file and fill in the tokens relevant to your setup.

```bash
cp .env.example .env
```

- On the **work** machine, add corporate Slack and Telegram secrets.
- On the **home** machine, add tokens for personal bots or leave values blank if
  the integration is disabled in the profile.

Environment variables are loaded automatically by both the CLI and the web app.

### 4. Review profile configuration

Profile-specific settings live in `config/work.yaml` and `config/home.yaml`. The
files describe which integrations are active (Slack, Telegram, and the local
knowledge base) and how often the knowledge base is refreshed.

Adjust the YAML files if you want to enable or disable integrations or point the
knowledge base at different files.

### 5. Launch the CLI

Interactive chat session using the orchestrator:

```bash
python -m interfaces.cli chat --profile work
```

Use `--profile home` on your personal machine. Type `exit` or `quit` to stop the session.

### 6. Launch the web interface (optional)

Run the FastAPI server with Uvicorn:

```bash
uvicorn interfaces.web.app:app --reload --port 8000
```

Open <http://localhost:8000> in your browser. Select the desired profile from
the drop-down and start chatting. The web UI keeps the full skill conversation
history visible at all times.

## Security policy

- **Secret management:** store API keys and tokens in the `.env` file locally and
  never commit them to version control. In production environments prefer a
  dedicated secret manager (Vault, AWS Secrets Manager, etc.) and inject them as
  environment variables.
- **Profile isolation:** each profile uses its own set of environment variable
  names to avoid leaking work credentials into the home setup and vice versa.
- **Logging:** the sample orchestrator logs only high-level events. If you add
  logging or persistence, redact tokens and personal data. Avoid writing secrets
  to stdout or shared log files.
- **Configuration files:** YAML configurations may contain paths to local
  knowledge bases. Restrict file permissions so that only trusted users can
  modify them.

## FAQ: extending the skill set

**How do I add a new skill?**

Create a new class in `core/skills.py` that implements the `respond` method and
register it inside `Orchestrator._build_skills`. Use the profile configuration
file to toggle the skill on and off if it depends on external services.

**Can the assistant call external APIs?**

Yes. Add the integration settings to the relevant profile YAML and inject the
required clients inside your skill implementation. Respect the security policy
when handling tokens and user data.

**How do I extend the knowledge base?**

Edit the YAML files in `data/` or point the configuration to your own dataset.
Every entry supports `keywords`, a `title`, and a `response`. Re-run the CLI or
refresh the web UI to load the new content.

**How do I persist conversations?**

The current orchestrator keeps history in memory. To make it persistent, extend
`Orchestrator.handle_message` to write to a database or file system, ensuring
that personally identifiable information is encrypted at rest.

---

Have fun experimenting with profiles and skills! Contributions are welcome.
