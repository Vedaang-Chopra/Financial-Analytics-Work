# Mutual Fund Project Memory Pack

This zip contains markdown files that capture the current project context from the first major planning conversation.

## Recommended Placement

Unzip into your repository root.

Expected structure:

```text
CHATGPT_PROJECT_MEMORY.md
docs/project_memory/
  00_project_summary.md
  01_conversation_decisions.md
  02_system_architecture_memory.md
  03_phase_plan_memory.md
  04_current_status_and_next_steps.md
  05_codex_working_instructions.md
  06_data_sources_and_provider_strategy.md
  07_notebook_and_testing_policy.md
  08_phase_1_5_strategy_resolution_memory.md
```

## How to Use With ChatGPT Project Memory

For ChatGPT project instructions/memory, paste the contents of:

```text
CHATGPT_PROJECT_MEMORY.md
```

If there is space, also paste summaries from:

```text
docs/project_memory/03_phase_plan_memory.md
docs/project_memory/04_current_status_and_next_steps.md
docs/project_memory/05_codex_working_instructions.md
```

## How to Use With Codex

Ask Codex:

```text
Read CHATGPT_PROJECT_MEMORY.md and all files under docs/project_memory/.
Also read AGENTS.md and docs/design/mutual_fund_ingestion/ if present.
Then inspect the existing codebase and implement only the requested phase.
```

## Relationship to Design Specs

These files are memory/context files.

They do not replace detailed phase design specs under:

```text
docs/design/mutual_fund_ingestion/
```

Use memory files for continuity and design specs for implementation details.
