# Tribultz DevOps Crew

This crew automates DevOps tasks for the Tribultz platform using CrewAI.

## Setup

This crew requires `crewai` and `crewai-tools` to be installed. These are **development dependencies** and are NOT included in the production `backend/requirements.txt`.

### Integration Tests (Recommended)
Run in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install crewai crewai-tools
```

## Running

### Dry Run (Default)
By default, the crew runs in **DRY RUN** mode. It will print the actions it *would* take but will NOT execute any destructive commands (like shell commands or docker operations that modify state).

```bash
# Run in dry-run mode (default)
python main.py
```

### Execution Mode
To actually execute the commands, set `DRY_RUN=0` (or `false`):

```bash
# Run with execution enabled
DRY_RUN=0 python main.py
```
