---
name: jira
version: 2.0.0
description: Production-grade Jira Cloud management with 28 commands — requirement decomposition, epic/ticket creation/management, PR linking, code auditing, blockers, scope creep detection, risk assessment, and comprehensive guardrails.
author: Claude Code
---

# Jira Skill

A comprehensive Jira Cloud management skill that keeps your tickets synchronized with your code, automatically sizes and scopes requirements, links PRs, and detects mismatches.

## Quick Start

```bash
# Initialize master config (interactive)
jira config init

# Create epic from requirement
jira new-epic "Build user authentication system with OAuth2 and session management"

# Link a PR to a ticket
jira link-pr https://github.com/org/repo/pull/42

# Audit tickets vs current code changes
jira audit TG

# Update tickets based on code changes
jira update-tickets

# Show status summary
jira status TG
```

## Core Commands (28 total)

**Configuration**: `config init`, `config show`

**Create & Manage**: `new-epic`, `quick-create`, `create-subtask`, `link-pr`

**View & Explore**: `show`, `list-epics`, `epic-info`, `status`, `list-stale`

**Update & Transition**: `reassign`, `move-to-epic`, `transition`, `add-comment`

**Analyze & Detect**: `find-blockers`, `detect-scope-creep`, `estimate-epic`, `risk-assessment`, `suggest-consolidation`, `audit`, `decompose-preview`

**Advanced**: `search`, `update-ticket`, `create-epic`, `create-ticket-in-epic`, `handle-pr-merge`

## Features

✅ **Intelligent requirement parsing** — Decompose requirements into epic/ticket/subtask hierarchy  
✅ **Auto-sizing** — Estimate story points from complexity keywords and historical velocity  
✅ **PR linking** — Detect PR intent via branch name, title, or commit message  
✅ **Code audit** — Find tickets not updated when code changes  
✅ **Auto-transitions** — Move tickets to "In Progress" when PR opens (with guards)  
✅ **Auto-reassignment** — Suggest reassignment when assignee overloaded or unavailable  
✅ **Scope creep detection** — Flag when ticket scope grows >50%  
✅ **Stale detection** — Find inactive tickets after N days  
✅ **Velocity tracking** — Learn team velocity per epic type  
✅ **Guardrails** — Require confirmation on critical/destructive actions  
✅ **Multi-project** — Support cross-project work with per-project config overrides  
✅ **Config validation** — Verify Jira access, field IDs, project keys before executing  

## Configuration

Master config: `~/.claude/jira/config.json`  
Per-project override: `.claude/jira.json` in your repo (overrides master)  

See [CONFIG.md](docs/CONFIG.md) for schema and examples.

## Examples

See [EXAMPLES.md](docs/EXAMPLES.md) for detailed workflows.

## Development

Tests: `make test`  
Linting: `make lint`  
Coverage: `make coverage`  

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical design.
