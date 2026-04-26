# Jira Skill Integration Guide

## For Claude Sessions (Code & Desktop)

This repository contains the **Jira Skill v2.0.0** — a production-grade Jira Cloud management tool with 28 commands.

### How Claude Should Use This Skill

1. **Direct CLI Access**: The `jira` command is available system-wide
2. **Project Binding**: Each repo has `.claude/claude.json` specifying which Jira project to bind to
3. **Master Config**: `~/.claude/jira/config.json` provides instance details, guardrails, and defaults

### When to Use the Jira Skill

Use the jira skill when:
- Creating epics from requirements: `jira new-epic "Build auth system"`
- Managing tickets: `jira show TG-123`, `jira move-to-epic TG-123 TG-500`
- Linking PRs: `jira link-pr https://github.com/...pull/42`
- Detecting issues: `jira find-blockers TG`, `jira detect-scope-creep TG`
- Checking status: `jira status TG`

### Available Commands

**Full list**: `jira --help`

**Quick access**:
```
jira config init           # Initialize config
jira new-epic "req"        # Create epic
jira show TG-123           # View ticket
jira status TG             # Project status
jira audit TG              # Code vs Jira audit
jira estimate-epic TG-500  # Forecast completion
```

### Configuration

**Master config**: `~/.claude/jira/config.json`
- Cloud instance: darkmothcreative.atlassian.net
- Projects: TG (TerrorGems), HCP (Hoad Cloud Platform), TPC (Content)
- Guardrails: confirmation required for reassign/closeTicket/moveToEpic

**Repo config**: `.claude/claude.json`
- Specifies which project this repo binds to
- Example: `{"jira": {"projectKey": "TG", "cloudId": "darkmothcreative"}}`

### Guardrails & Safety

These actions require explicit user confirmation:
- `reassign` — changing ticket assignee
- `closeTicket` — moving ticket to Done
- `moveToEpic` — moving between epics

Never skip confirmation prompts. The skill will explicitly ask before executing.

### Integration for Claude Desktop

The jira skill is registered as a system command and accessible in:
- Claude Code (browser)
- Claude Desktop (native app)

Claude Desktop will automatically discover the `jira` command when:
1. The jira-skill package is installed (`pip install -e /path/to/jira-skill`)
2. The entry point is registered (automatic on install)
3. The command is in PATH (verified with `which jira`)

### Testing the Skill

```bash
# Verify installation
jira --version

# Show help
jira --help

# Test config
jira config show

# Try a safe command
jira status TG
```

### Troubleshooting

**"jira: command not found"**
- Reinstall: `pip install -e .`
- Verify PATH: `which jira`
- Check JIRA_API_TOKEN environment variable is set

**Authentication errors**
- Set token: `export JIRA_API_TOKEN=<your-token>`
- Validate config: `jira config show`

**Missing repo binding**
- Ensure `.claude/claude.json` exists in your repo
- Should contain: `{"jira": {"projectKey": "TG|HCP|TPC", "cloudId": "darkmothcreative"}}`

## For Developers

The skill source code is in `src/` with:
- `main.py` — CLI implementation (28 commands)
- `jira_api.py` — Jira Cloud REST API wrapper
- `intelligence.py` — AI-powered analysis (decomposition, sizing, scope creep detection)
- `models.py` — Data models for tickets, epics, audits
- `guardrails.py` — Safety enforcement
- `workflow_engine.py` — Automation workflows

Tests: `pytest tests/` (64 tests, 100% passing)
