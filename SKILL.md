---
name: jira
version: 3.0.0
description: DevArmor-compliant Jira Cloud management skill with full governance, event publishing, and cross-skill communication. Creates/manages tickets and epics, links PRs, detects blockers, and estimates work. Features lifecycle management, audit trails, and policy enforcement. Use this skill whenever you need to: create or view Jira tickets and epics, check project status, link pull requests to tickets, find blocking issues, estimate completion, audit code against tickets, detect scope creep, or perform any Jira Cloud operation.
author: Claude Code
---

# Jira Skill (DevArmor v3.0.0)

A comprehensive, enterprise-grade Jira Cloud management skill with full DevArmor governance. Keeps your tickets synchronized with your code, automatically sizes and scopes requirements, links PRs, detects mismatches, and enforces policies at every operation.

## DevArmor Compliance

This skill is fully DevArmor-compliant with v0.1.0 core:

✅ **Lifecycle Management**
- `on_install` hook: Register event subscriptions
- `on_upgrade` hook: Handle migration logic
- `on_remove` hook: Cleanup and unsubscribe

✅ **Event Publishing**
- `ticket_created` — When new tickets are created
- `ticket_updated` — When tickets are modified (status, assignee, etc.)
- `ticket_deleted` — When tickets are deleted (blocked operation with confirmation)
- Custom events via `publish_event()`

✅ **Cross-Skill Communication**
- Subscribes to GitHub events for PR integration
- Publishes events for other skills to consume
- Handles event subscriptions/unsubscriptions

✅ **Policy Enforcement**
- Pre-action checks for all mutations via `pre_action_check()`
- Respects DevArmor policy evaluation
- Audit trail via `DevArmorAPI.audit_logger`

✅ **Configuration Hierarchy** (4-level)
1. Code defaults (in config/jira.default.json)
2. Master config (~/.claude/jira/config.json)
3. Repo config (.claude/jira.json)
4. Environment variables (JIRA_*)

Also integrates with DevArmor policy configuration for governance.

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

## Architecture

**3-Pillar Structure**:
- **Config Layer** (`src/config.py`) — 4-level hierarchy with validation
- **Skill Layer** (`src/skill.py`) — Lifecycle hooks, event subscriptions, DevArmor integration
- **API Layer** (`src/api.py`) — Jira API with event publishing and pre-action checks

**Key Classes**:
- `JiraSkill` — Base skill with lifecycle hooks and event handling
- `JiraSkillWithEvents` — Extended skill with cross-skill communication demo
- `JiraConfigLoader` — 4-level config hierarchy (code → master → repo → env)
- `JiraAPIWithEvents` — Wraps Jira API and publishes events

## Configuration

Master config: `~/.claude/jira/config.json`  
Per-project override: `.claude/jira.json` in your repo (overrides master)  
DevArmor policy config: `~/.devarmor/config.yaml` or `.devarmor/config.yaml`

### Loading Priority (highest to lowest)
1. Environment variables (`JIRA_CLOUD_ID`, etc.)
2. Repo config (`.claude/jira.json`)
3. Master config (`~/.claude/jira/config.json`)
4. Code defaults (`src/config/jira.default.json`)

See [CONFIG.md](docs/CONFIG.md) for schema and examples.

## Event System

### Publishing Events

The skill publishes events for all mutations:

```python
# Automatic via JiraAPIWithEvents
api = JiraAPIWithEvents(config, skill)
await api.create_ticket(...)  # Publishes ticket_created
await api.update_ticket(...)  # Publishes ticket_updated
await api.delete_ticket(...)  # Publishes ticket_deleted
```

### Subscribing to Events

Other skills can subscribe:

```python
skill = JiraSkillWithEvents()
await skill.initialize()

async def handle_github_pr(event):
    print(f"PR event: {event.action}")

skill.subscribe_to_event(
    event_types=[EventType.CUSTOM],
    callback=handle_github_pr,
    subscriber_id="my-github-handler"
)
```

### Event Types

Custom events follow pattern:
```python
{
    "event_type": "ticket_created|ticket_updated|ticket_deleted",
    "skill_name": "jira-skill",
    "action": "create_ticket|update_ticket|delete_ticket",
    "resource": "PROJ-123",
    "actor": "claude",
    "details": {...}
}
```

## Examples

See [EXAMPLES.md](docs/EXAMPLES.md) for detailed workflows.

## Development

Tests: `make test`  
Linting: `make lint`  
Coverage: `make coverage` (must be >85%)

Integration tests demonstrate:
- Config loading from 4 levels
- Event publishing on ticket operations
- Cross-skill communication
- Lifecycle hooks (install/upgrade/remove)

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical design.

## Migration from v2.x

This version (v3.0.0) maintains full backward compatibility with v2.x CLI while adding DevArmor compliance:

```python
# Old way (still works)
config = config_loader.load_and_merge()
api = JiraAPI(config)
api.create_ticket(...)

# New way (with DevArmor)
skill = JiraSkillWithEvents()
await skill.initialize()
api = JiraAPIWithEvents(config, skill)
await api.create_ticket(...)  # Events published automatically
```
