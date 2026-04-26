# Jira Skill Examples & Workflows

## Setup

### Initialize Configuration

```bash
jira config init
```

Follow prompts:
```
Enter your Jira Cloud ID (from https://your-instance.atlassian.net): craighoad
Enter default assignee username [craig]: craig
✅ Config saved to ~/.claude/jira/config.json
```

### Create Per-Project Override

In your TerrorGems repo:

```bash
mkdir -p .claude
cat > .claude/jira.json << 'EOF'
{
  "jira": {
    "projectKey": "TG"
  },
  "guardrails": {
    "requireConfirmationFor": ["reassign"],
    "criticalLabels": ["critical", "revenue", "compliance"]
  }
}
EOF
```

---

## Workflow 1: Create Epic from Requirements

### Scenario
You have a complex feature requirement and need to break it into manageable work.

### Command

```bash
jira new-epic "Implement user dashboard with real-time notifications, profile management, and activity history. This involves frontend React components, backend APIs, database schema changes, and integration with our notification service."
```

### Output

```
📋 Parsing requirement...

SCOPE TREE:
EPIC: Implement user dashboard (~18pts)
  TICKET: Frontend dashboard components (~6pts)
    SUBTASK: Implement React components (~3pts)
    SUBTASK: Add styling and responsive layout (~2pts)
    SUBTASK: Integration testing (~1pt)
  TICKET: Backend APIs (~6pts)
    SUBTASK: Design and implement endpoints (~3pts)
    SUBTASK: Add authentication checks (~2pts)
    SUBTASK: Testing (~1pt)
  TICKET: Database and notification integration (~6pts)
    SUBTASK: Schema design (~2pts)
    SUBTASK: Notification service integration (~2pts)
    SUBTASK: Testing (~1pt)

⚠️  Requires confirmation (create_epic enabled in guardrails)

Create epic? [y/n]: y

✅ Epic created successfully!

TG-500 [To Do] Implement user dashboard (~18pts)
├─ TG-501 [To Do] Frontend dashboard components (~6pts)
│  ├─ TG-501-1 [To Do] Implement React components
│  ├─ TG-501-2 [To Do] Add styling and responsive layout
│  └─ TG-501-3 [To Do] Integration testing
├─ TG-502 [To Do] Backend APIs (~6pts)
│  ├─ TG-502-1 [To Do] Design and implement endpoints
│  ├─ TG-502-2 [To Do] Add authentication checks
│  └─ TG-502-3 [To Do] Testing
└─ TG-503 [To Do] Database and notification integration (~6pts)
   ├─ TG-503-1 [To Do] Schema design
   ├─ TG-503-2 [To Do] Notification service integration
   └─ TG-503-3 [To Do] Testing

🔗 View epic: https://craighoad.atlassian.net/browse/TG-500
```

---

## Workflow 2: Link PR and Auto-Transition

### Scenario
You've opened a PR for TG-123 and want to link it and move the ticket to "In Progress".

### Command

```bash
jira link-pr https://github.com/craighoad/terrorgems/pull/47
```

(Your branch is `feat/TG-123-user-auth`, so it auto-detects the ticket)

### Output

```
🔍 Detecting ticket from PR...

Detected: TG-123 (from branch: feat/TG-123-user-auth)

🔗 Linking PR #47 to TG-123

ACTIONS PLANNED:
  ✏️  Add comment: "🔗 Linked from PR #47: Implement user authentication"
  ✔️  Transition TG-123: To Do → In Progress
  👤 Assignee: craig (already assigned)

Proceed? [y/n]: y

✅ Successfully linked!
   TG-123 now In Progress
   Comment added with PR link
   
🔗 PR: https://github.com/craighoad/terrorgems/pull/47
🔗 Ticket: https://craighoad.atlassian.net/browse/TG-123
```

---

## Workflow 3: Audit Code vs Tickets

### Scenario
It's Friday afternoon and you want to make sure all code changes have corresponding tickets.

### Command

```bash
jira audit TG --since 7
```

### Output

```
🔍 Auditing TG project (changes in last 7 days)...

Checked 4 files, 12 commits, 45 open tickets

ERRORS (2):
  ❌ src/auth.ts modified (3 commits) but no ticket
     Files: src/auth.ts, src/components/LoginForm.tsx
     Commits: abc123, def456, ghi789
     Suggestion: Create ticket TG-??? or link to existing
     
  ❌ Code on closed ticket
     Ticket: TG-100 (Closed on Apr 15)
     Recent commits: jkl012 (Apr 18), mno345 (Apr 19)
     Suggestion: Create new ticket or reopen TG-100

WARNINGS (1):
  ⚠️  TG-123 in progress 14 days, no recent updates
     Last activity: Apr 12
     Suggestion: Update ticket or mark as blocked

SUMMARY: 2 errors, 1 warning
```

### Fix Errors

```bash
jira audit TG --since 7 --fix
```

The skill proposes automatic fixes with confirmation.

---

## Workflow 4: Update Tickets from Code

### Scenario
You've merged 3 PRs and want to automatically update their tickets.

### Command

```bash
jira update-tickets --project TG
```

### Output

```
📝 Syncing TG project...

Checking last 24 hours of activity...

UPDATES FOUND (3):
  ✏️  TG-123: Update description with latest commits
     Commits: [abc123] Implement OAuth2, [def456] Add session management
     
  ✏️  TG-456: Add PR merge comment
     PR #47 merged into main 2 hours ago
     
  ✔️  TG-789: Transition In Progress → In Review
     PR #48 opened, waiting for review

Preview these updates? [y/n]: y

Processing...
  TG-123: ✅ Description updated
  TG-456: ✅ Comment added
  TG-789: ✅ Transitioned to In Review

✅ All updates complete!
```

---

## Workflow 5: Manage Stale Tickets

### Scenario
You want to clean up tickets that have been in progress for too long.

### Command

```bash
jira list-stale TG --days 14
```

### Output

```
🧊 Stale tickets in TG (>14 days In Progress):

TG-234: User dashboard  
  Status: In Progress
  Days: 18
  Assignee: craig
  Last update: Apr 7
  Subtasks: 2 open, 1 done
  
TG-345: Admin panel
  Status: In Progress
  Days: 21
  Assignee: tory
  Last update: Apr 4
  
TG-456: Email notifications
  Status: In Progress
  Days: 25
  Assignee: craig
  Last update: Mar 31
  Subtasks: All done, but parent not closed

Actions:
  1. Check in on TG-234 and TG-345 (might be blocked)
  2. Close TG-456 (subtasks done, just needs closing)

Apply auto-close to completed tickets? [y/n]: y

Closing TG-456: Email notifications
✅ Closed

Still active:
  ⚠️  TG-234: Added comment "Checking in - status update needed"
  ⚠️  TG-345: Added comment "Still active? Reassign or close if done?"
```

---

## Workflow 6: Cross-Project Work

### Scenario
You're building an integration between TerrorGems (TG) and HCP Platform (HCP).

### Command

Create epic in TG:
```bash
jira new-epic "Build HCP platform integration for content delivery system"
```

Then link HCP ticket:
```bash
jira move-epic TG-600 TG-500  # Move to integration epic
jira link-related TG-500 HCP-200  # Link to HCP epic
```

### Output

The ticket TG-500 now has a relationship to HCP-200, visible in both projects.

---

## Workflow 7: Team Collaboration

### Scenario
You're onboarding Tory to TerrorGems and want to balance the workload.

### Command

```bash
jira status TG --format json | jq '.inProgress'
```

See that Craig has 4 tickets, Tory has 1.

### Reassign work

```bash
jira reassign TG-234 tory
jira reassign TG-345 tory
```

### Output

```
🔄 Reassigning TG-234

  Current: craig
  New: tory
  Points: 5
  
⚠️  Ticket is critical (label: critical)
   Requires confirmation

Proceed? [y/n]: y

✅ TG-234 now assigned to tory
   ✏️  Added comment: "Reassigned from craig to tory on Apr 26"
```

---

## Workflow 8: Pre-Deployment Checklist

### Scenario
You're deploying Phase 2 and want to verify all work is tracked.

### Commands

```bash
# 1. Audit everything
jira audit TG

# 2. Check for stale tickets
jira list-stale TG --days 7

# 3. Verify all epics are complete
jira status TG

# 4. Check velocity
jira velocity TG --interval weekly
```

### Combined Output

```
✅ All tickets have commits (audit: 0 errors)
✅ No stale tickets (all updated in last 7 days)
✅ Phase 2 epic: 100% complete (45/45 pts)
📈 Velocity: 23 pts/week (on track)

🚀 Safe to deploy!
```

---

## Tips & Best Practices

### Branch Naming

Use format: `feat/TG-123-short-description`

The skill will automatically detect `TG-123` when you open the PR.

### PR Title Options

All of these work:
- `[TG-123] Implement authentication`
- `TG-123: Implement authentication`
- `Implement authentication (TG-123)`
- `Closes TG-123`

### Requirement Structure

Good requirements for `new-epic`:
```
Implement user authentication with OAuth2 integration. 
The system should support multiple providers (Google, GitHub, email).
Includes session management, session timeout, and remember-me functionality.
Requires database schema changes for storing sessions and provider configs.
```

The skill will decompose this into:
- Epic: Implement user authentication
- Ticket: OAuth2 integration
  - Subtask: Provider implementation
  - Subtask: Testing
- Ticket: Session management
  - Subtask: Implementation
  - Subtask: Documentation

### Config Customization

Adjust complexity keywords for your team:

```json
{
  "requirements": {
    "complexityKeywords": {
      "integrate": 5,
      "refactor": 3,
      "frontend": 2,
      "database": 3
    }
  }
}
```

### Working with Two-Person Team

With Craig and Tory:

```bash
# Check who's overloaded
jira status TG | grep -A 3 "IN PROGRESS"

# Rebalance
jira reassign TG-100 tory  # Move from craig to tory
jira reassign TG-200 craig  # Move from tory to craig
```

---

## Troubleshooting Examples

### PR Not Detected?

If `link-pr` can't find the ticket:

```bash
# Manually specify
jira link-pr https://github.com/... --ticket TG-123

# Or check branch name
git branch  # Should be feat/TG-123-description
```

### Config Validation Error?

```bash
jira config show
# Check output for missing/invalid fields
# Fix in ~/.claude/jira/config.json
```

### Ticket Not Transitioning?

Check guardrails:
```bash
jira config show | grep -A 10 guardrails
```

If `transition_to_done` requires confirmation, you'll see a prompt.

---

For more details, see:
- [CONFIG.md](CONFIG.md) — configuration reference
- [COMMANDS.md](COMMANDS.md) — all commands
- [ARCHITECTURE.md](ARCHITECTURE.md) — how it works
