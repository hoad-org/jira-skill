# Jira Skill Architecture

## Design Principles

1. **Safety first** — Guardrails prevent mistakes, confirmations for critical actions
2. **Intelligent defaults** — Auto-sizing, scope detection, duplicate prevention
3. **Multi-project support** — Master config + per-project overrides
4. **Stateless operations** — Each command reads fresh state from Jira
5. **Composable modules** — Core logic separated from CLI/API

## Module Structure

```
src/
├── models.py              # Data models (Epic, Ticket, Config, etc.)
├── config_loader.py       # Master + project config loading/merging
├── jira_api.py            # Jira Cloud API client
├── requirement_parser.py  # Parse requirements → epic/ticket/subtask scope
├── auto_sizer.py          # Story point estimation
├── pr_linker.py           # Detect PRs and link to tickets
├── code_auditor.py        # Compare code changes to tickets [TODO]
├── workflow_engine.py     # Status transitions, reassignments [TODO]
├── intelligence.py        # Scope creep, stale detection, velocity [TODO]
├── guardrails.py          # Confirmation logic, validation
└── main.py                # CLI dispatcher [TODO]
```

## Data Models

### Core Domain Models

**Epic** — represents a Jira epic
- Owns multiple Tickets
- Has points, status, assignee
- Properties: `total_points`, `completed_points`, `progress_percent()`

**Ticket** — represents a Jira story/task
- Has Status, Points, Assignee, Labels
- Owns multiple Subtasks
- Can be linked to an Epic
- Method: `is_critical(labels)` for guardrail checks

**Subtask** — represents a Jira subtask
- Child of a Ticket
- Cannot own other subtasks

**RequirementScope** — structured requirement breakdown
- Type: epic, ticket, or subtask
- Has estimated_points
- Has sub_items (recursive tree structure)

### Configuration Models

**JiraConfig** — resolved master config
- Jira connection details
- Guardrail rules
- Keyword complexity mappings
- Project definitions

**ProjectConfig** — per-project configuration
- Key, name, custom field IDs
- Project-specific guardrails

### Action Models

**TransitionAction** — ticket status transition
- ticket_key, from_status, to_status
- requires_confirmation flag

**ReassignmentAction** — ticket reassignment
- ticket_key, from_assignee, to_assignee
- requires_confirmation flag

**ExecutionPlan** — batch of planned actions
- transitions, reassignments, creations, updates
- Validates against limits before execution

## Core Workflows

### 1. Create Epic from Requirement

```
User requirement text
    ↓
RequirementParser.parse()
    ├─ Estimate total points
    ├─ Check if complex (>40pts or multiple domains)
    └─ If complex: decompose into tickets
        └─ Each ticket checks if needs subtasks
    ↓
RequirementScope tree
    ↓
User reviews & approves
    ↓
JiraAPI.create_epic()
    ├─ Create epic
    └─ For each ticket: JiraAPI.create_ticket()
        └─ For each subtask: JiraAPI.create_subtask()
    ↓
Summary with links
```

### 2. Link PR to Ticket

```
PR metadata (branch, title, description)
    ↓
PRLinker.detect_ticket()
    ├─ Try branch name (highest priority)
    ├─ Try PR title
    └─ Try PR description
    ↓
Ticket key → JiraAPI.get_ticket()
    ↓
ExecutionPlan
    ├─ Link PR in comment
    └─ Auto-transition to "In Progress" [if configured]
    ↓
Guardrails.validate_execution_plan()
    └─ Check limits, confirmation needs
    ↓
User approval [if needed]
    ↓
Execute actions
```

### 3. Audit Code vs Tickets

```
Get code changes (git diff)
    ↓
Get project tickets (JiraAPI.get_tickets())
    ↓
For each code file changed:
    ├─ Find related tickets by filename/component
    └─ Check if ticket status matches code status
        ├─ Code changed but ticket is "To Do" → ERROR
        ├─ Code completed but ticket not "Done" → WARNING
        └─ Code reverted but ticket "In Progress" → WARNING
    ↓
AuditFinding[] with severity and suggestions
    ↓
Present findings to user
    ↓
User approves fixes
    ↓
Execute updates
```

## Key Design Decisions

### Why Requirement Parser Decomposes Requirements

Complex requirements need to be broken into manageable work units:
- Large epics (>40pts) split into multiple smaller epics or sub-epics
- Large tickets (>13pts) suggest subtasks
- Detects complexity patterns (multiple domains, dependencies)

Algorithm: regex-based pattern detection + keyword analysis.

### Why Auto-Sizer Uses Keyword Mapping

Story points are subjective, but can be systematized:
- Base: 2 points
- Keywords add points (configurable per team)
- Length adjustment (longer descriptions = more complex)
- Capped at 1-21 points

This gives consistent estimates, can be refined with historical data.

### Why PR Linking Uses Priority Order

Multiple detection methods with fallback:
1. **Branch name** — most reliable, follows convention
2. **PR title** — readable, visible in logs
3. **PR description** — fallback for edge cases

This allows flexible usage without requiring strict conventions.

### Why Guardrails Are Separate Module

Decoupling guardrails from business logic:
- Easy to add new confirmation requirements
- Can preview actions before executing
- Testable independently
- Different projects can have different guardrail levels

## Testing Strategy

### Unit Tests

Each module has unit tests:
- `test_auto_sizer.py` — keyword analysis, point clamping
- `test_pr_linker.py` — branch/title/description detection
- `test_config_loader.py` — config merging, validation
- `test_guardrails.py` — confirmation logic, validation

Run: `pytest tests/`

### Integration Tests [TODO]

Full workflows:
- Create epic → ticket → subtask → link PR → audit → update
- Cross-project ticket linking
- Reassignment with guardrails

### Mocking Strategy

Mock Jira API responses for fast, reliable testing:
- `tests/fixtures/mock_jira_api.py` — mock responses
- No external network calls during tests
- Can simulate various Jira states

## Extension Points

### Adding New Auto-Sizing Rules

1. Update `complexityKeywords` in config schema
2. Modify `AutoSizer.estimate()` algorithm
3. Add unit tests

### Adding New Guardrail

1. Add rule to config schema
2. Implement check in `Guardrails` class
3. Update `ExecutionPlan` marking
4. Add test

### Adding New Workflow

1. Create new module (e.g., `workflow_x.py`)
2. Implement using existing models + Jira API
3. Create `ExecutionPlan` with planned actions
4. Pass through guardrails validation
5. Execute after approval

## Performance Considerations

- **Stateless**: Each command re-fetches state (could optimize with caching)
- **Batch operations**: Single run can process multiple actions
- **Limits**: Configured limits prevent runaway actions
- **Jira API rate limits**: No aggressive retries, fail fast if throttled

## Future Enhancements

- [ ] Velocity tracking per project/team
- [ ] Automatic ticket state machine (PR → status transition chain)
- [ ] Slack/email notifications on action
- [ ] Bulk operations (migrate epics, archive old tickets)
- [ ] Time tracking integration
- [ ] Dependency graph visualization
- [ ] Sprint planning automation
- [ ] Risk assessment (critical path analysis)
- [ ] Cost estimation from historical velocity
