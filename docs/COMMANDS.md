# Jira Skill Commands Reference

## Configuration Commands

### `jira config init`

Initialize master configuration interactively.

```bash
jira config init
```

Creates `~/.claude/jira/config.json` and prompts for:
- Jira Cloud instance ID
- Default assignee username
- Default reporter username

**Output**: Path to created config file

---

### `jira config show [--project-dir PATH]`

Display resolved configuration (master + project overrides).

```bash
jira config show
jira config show --project-dir /path/to/repo
```

**Output**: 
```json
{
  "cloudId": "your-instance",
  "useMcpAuth": true,
  "defaultAssignee": "craig",
  "projects": ["TG", "HCP"],
  "guardrails": { ... }
}
```

Useful for debugging config issues.

---

## Requirement & Epic Commands

### `jira new-epic <requirement> [--project KEY]`

Create an epic from a natural language requirement.

```bash
jira new-epic "Build user authentication with OAuth2 and session management"
jira new-epic "Implement payment processing" --project TG
```

The skill will:
1. Parse the requirement
2. Estimate story points
3. Decompose into tickets/subtasks if needed
4. Show the scope tree
5. Create epic (with confirmation if needed)

**Output**:
```
EPIC: Build user authentication (~15pts)
  TICKET: Implement OAuth2 integration (~5pts)
    SUBTASK: Implementation (~2pts)
    SUBTASK: Testing (~2pts)
  TICKET: Session management (~5pts)
    SUBTASK: Implementation (~2pts)
    SUBTASK: Documentation (~1pt)

✅ TG-555 created: Build user authentication
   ├─ TG-556: Implement OAuth2 integration
   │  ├─ TG-556-1: Implementation
   │  └─ TG-556-2: Testing
   └─ TG-557: Session management
      ├─ TG-557-1: Implementation
      └─ TG-557-2: Documentation
```

**Options**:
- `--project KEY` — Create in specific project (default: infer from current repo)
- `--auto-approve` — Skip confirmation (dangerous!)
- `--dry-run` — Show what would be created without creating

---

### `jira new-ticket <epic-key> <requirement> [--subtasks]`

Add a ticket to an epic from a requirement.

```bash
jira new-ticket TG-555 "Implement OAuth2 provider integration"
jira new-ticket TG-555 "Add integration tests" --subtasks
```

**Output**: Similar to `new-epic`, shows new ticket(s)

**Options**:
- `--subtasks` — Auto-create subtasks if ticket is large
- `--auto-approve` — Skip confirmation

---

## PR & Code Linking Commands

### `jira link-pr <pr-url> [--ticket KEY] [--auto]`

Link a PR to a Jira ticket.

```bash
jira link-pr https://github.com/craighoad/terrorgems/pull/42
jira link-pr https://github.com/craighoad/terrorgems/pull/42 --ticket TG-123
jira link-pr https://github.com/craighoad/terrorgems/pull/42 --auto
```

The skill will:
1. Detect ticket key (branch → title → description)
2. Fetch PR details
3. Link PR in ticket comment
4. Auto-transition ticket to "In Progress" (if configured)

**Output**:
```
🔗 Linked PR #42 to TG-123

Actions planned:
  ├─ Add comment: "🔗 Linked from PR #42"
  └─ Transition TG-123: To Do → In Progress

⚠️  Requires confirmation (reassign enabled)
```

**Options**:
- `--ticket KEY` — Manual ticket key (skips detection)
- `--auto` — Auto-approve transitions (skip confirmation)

---

## Audit & Status Commands

### `jira audit <project-key> [--since DAYS_AGO]`

Compare code changes to Jira tickets.

```bash
jira audit TG
jira audit TG --since 7
```

Finds mismatches:
- Code changed but ticket is "To Do"
- Ticket completed but code not merged
- Code on closed ticket
- Orphaned/stale tickets

**Output**:
```
🔍 Auditing TG project...

ERRORS (3):
  ❌ TG-123: Code changed in src/auth.ts but status is "To Do"
     Suggestion: Transition to "In Progress" or create new ticket
  ❌ TG-456: 5 commits in last 24h but ticket untouched
     Suggestion: Update ticket description

WARNINGS (2):
  ⚠️  TG-789: In Progress for 21 days, no recent activity
     Suggestion: Check if blocked, close if done
  ⚠️  TG-999: Similar to TG-888 (existing ticket)
     Suggestion: Link related ticket or consolidate

SUMMARY: 3 errors, 2 warnings, 42 tickets checked
```

**Options**:
- `--since DAYS_AGO` — Only check changes in last N days
- `--fix` — Auto-fix simple issues (with confirmation)
- `--format json` — Output as JSON

---

### `jira update-tickets [--project KEY]`

Sync ticket updates based on code changes.

```bash
jira update-tickets
jira update-tickets --project TG
```

Reviews recent commits and:
- Updates ticket descriptions with commit info
- Auto-transitions based on PR status
- Adds comments linking commits
- Suggests status changes

**Output**:
```
📝 Syncing TG project...

UPDATES PLANNED:
  ✏️  TG-123: Update description with latest commits
  ✏️  TG-456: Add comment "Commit abc123: Fix database query"
  ✔️  TG-789: Transition In Progress → In Review (PR merged)

Preview: 3 updates
Auto-approve? [y/n]:
```

---

### `jira status [project-key] [--format FORMAT]`

Show project status summary.

```bash
jira status TG
jira status --format json
```

**Output**:
```
📊 TerrorGems Status

EPICS (6):
  TG-500 [🔴 50%] User Authentication (8/16 pts)
         ├─ TG-501 [✅ Done]
         └─ TG-502 [🟡 In Progress]
  TG-600 [🟢 100%] Phase 1 Gamification (13/13 pts)

UNSTARTED TICKETS (3):
  • TG-123: Implement notification system
  • TG-456: Add analytics
  • TG-789: Performance optimization

IN PROGRESS (5):
  • TG-234: User dashboard
  • TG-345: Admin panel
  ...

BLOCKED TICKETS (1):
  🚫 TG-999: Database migration (blocked by devops)

VELOCITY:
  Last 7 days: 21 points
  Last 30 days: 89 points
  Team capacity: ~20 points/week
```

**Options**:
- `--format json` — JSON output
- `--format csv` — CSV output
- `--include-closed` — Show closed tickets

---

## Workflow Commands

### `jira reassign <ticket-key> <assignee> [--force]`

Reassign a ticket.

```bash
jira reassign TG-123 tory
jira reassign TG-123 tory --force
```

**Output**:
```
🔄 Reassigning TG-123

  From: craig
  To: tory
  
  ⚠️  Ticket is critical (label: critical)
  Requires confirmation for critical tickets
  
Proceed? [y/n]:
```

**Options**:
- `--force` — Skip confirmation (dangerous!)

---

### `jira move-epic <ticket-key> <epic-key>`

Move ticket to a different epic.

```bash
jira move-epic TG-123 TG-600
```

Requires confirmation unless `--force` flag.

---

### `jira list-stale <project-key> [--days N] [--action ACTION]`

Find inactive tickets.

```bash
jira list-stale TG
jira list-stale TG --days 21 --action close
```

**Output**:
```
🧊 Stale tickets in TG (>14 days, In Progress):

  TG-123: User authentication
    Status: In Progress
    Last updated: 25 days ago
    Assignee: craig
    Action: Check in or close

  TG-456: Database migration  
    Status: In Progress
    Last updated: 31 days ago
    Assignee: tory
    Action: Reassign or close
```

**Options**:
- `--days N` — Threshold (default: 14)
- `--action ACTION` — Auto-action: close, reassign, comment
- `--auto-approve` — Skip confirmation

---

## Advanced Commands

### `jira find-duplicates <project-key>`

Find potential duplicate tickets.

```bash
jira find-duplicates TG
```

Uses text similarity to detect likely duplicates.

---

### `jira velocity <project-key> [--interval PERIOD]`

Show team velocity over time.

```bash
jira velocity TG
jira velocity TG --interval monthly
```

**Output**:
```
📈 TerrorGems Velocity

Week 1 (Apr 14-20): 13 pts
Week 2 (Apr 21-27): 21 pts
Week 3 (Apr 28-May 4): 18 pts

Average: 17.3 points/week
Trend: ↗ Improving
```

---

## Global Options

All commands support:

```bash
--help              Show command help
--verbose           Verbose output
--no-color          Disable colored output
--config PATH       Use custom config file
--dry-run           Show what would happen, don't execute
```

## Examples

See [EXAMPLES.md](EXAMPLES.md) for complete workflow examples.
