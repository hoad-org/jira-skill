# Jira Skill Configuration Guide

## Overview

The Jira skill uses a two-tier configuration system:

1. **Master config** (`~/.claude/jira/config.json`) — global defaults
2. **Per-project config** (`.claude/jira.json`) — project-specific overrides

The per-project config completely overrides relevant sections of the master config, allowing you to have different settings per project.

## Master Config Initialization

First time setup:

```bash
jira config init
```

This creates `~/.claude/jira/config.json` and walks you through the setup.

Or manually create the file with your settings (see schema below).

## Configuration Schema

All configs must match the schema at `config/schema.json`. Here's the full structure:

### Jira Connection (`jira`)

```json
{
  "cloudId": "your-instance",
  "useMcpAuth": true,
  "apiToken": "optional-token-if-not-using-mcp",
  "maxAutoTransitionsPerRun": 10,
  "maxAutoReassignmentsPerRun": 5
}
```

**cloudId** (required): Your Jira Cloud instance ID.  
→ Found at: `https://YOUR_ID.atlassian.net`

**useMcpAuth** (default: true): Use Jira MCP connector for authentication.  
→ If false, requires `apiToken`

**apiToken** (optional): Jira API token.  
→ Create at: https://id.atlassian.com/manage-profile/security/api-tokens

**maxAutoTransitionsPerRun**: Maximum ticket status transitions per run.  
→ Prevents too many changes at once

**maxAutoReassignmentsPerRun**: Maximum reassignments per run.

### Requirements (`requirements`)

```json
{
  "defaultEpicPointsMax": 40,
  "defaultTicketPointsMax": 13,
  "complexityKeywords": {
    "integrate": 3,
    "refactor": 2,
    "testing": 1,
    ...
  }
}
```

**defaultEpicPointsMax**: If a requirement exceeds this, split into multiple epics.

**defaultTicketPointsMax**: If a ticket exceeds this, suggest subtasks.

**complexityKeywords**: Keywords that add points to estimate. Customize for your team.

### Guardrails (`guardrails`)

```json
{
  "requireConfirmationFor": ["reassign", "move_epic"],
  "neverAutoTransition": ["Done", "Closed"],
  "neverAutoReassignCritical": true,
  "criticalLabels": ["critical", "security", "compliance", "blocker"],
  "maxAutoCreateSubtasks": 3,
  "staleDaysThreshold": 14
}
```

**requireConfirmationFor**: Actions that require explicit user confirmation.  
→ Options: `reassign`, `move_epic`, `auto_close`, `delete`, `transition_to_done`, `create_epic`

**neverAutoTransition**: Statuses that should never auto-transition.  
→ Default: `["Done", "Closed"]`

**neverAutoReassignCritical**: Never auto-reassign tickets with critical labels.

**criticalLabels**: Labels that mark a ticket as critical.

**maxAutoCreateSubtasks**: Maximum subtasks to auto-create from one requirement.

**staleDaysThreshold**: Days a ticket can be "In Progress" before flagged as stale.

### Defaults (`defaults`)

```json
{
  "assignee": "craig",
  "reporter": "craig",
  "labels": []
}
```

**assignee**: Default assignee for new tickets.

**reporter**: Default reporter for new tickets.

**labels**: Default labels for new tickets.

### PR Linking (`prLinking`)

```json
{
  "branchPattern": "^(feat|fix|refactor|docs|test|chore)/([A-Z]+-[0-9]+)",
  "titlePattern": "^\\[?([A-Z]+-[0-9]+)\\]?",
  "autoTransitionOnOpen": true,
  "autoTransitionOnMerge": true
}
```

**branchPattern**: Regex to detect ticket from branch name.  
→ Example: `feat/TG-123-user-auth` → `TG-123`

**titlePattern**: Regex to detect ticket from PR title.  
→ Example: `[TG-123] Implement auth` → `TG-123`

**autoTransitionOnOpen**: Auto-transition ticket to "In Progress" when PR opens.

**autoTransitionOnMerge**: Auto-transition when PR merges.

### Projects (`projects`)

```json
{
  "projects": {
    "TG": {
      "name": "TerrorGems",
      "key": "TG",
      "epicLinkField": "customfield_10001",
      "storyPointField": "customfield_10000"
    }
  }
}
```

**key**: Jira project key (required).

**name**: Full project name.

**epicLinkField**: Custom field ID for epic link.  
→ Find in Jira: Project Settings → Fields → Epic Link

**storyPointField**: Custom field ID for story points.  
→ Default: `customfield_10000`

## Per-Project Config

Create `.claude/jira.json` in your project root to override specific settings:

```json
{
  "jira": {
    "projectKey": "TG"
  },
  "guardrails": {
    "requireConfirmationFor": ["reassign"]
  },
  "requirements": {
    "complexityKeywords": {
      "integrate": 5
    }
  }
}
```

Any settings here override the master config for this project.

## Finding Custom Field IDs

Jira uses custom field IDs like `customfield_10001`. To find yours:

1. Go to your Jira instance
2. Settings → Issues → Custom Fields
3. Hover over the field name
4. The ID appears in the URL: `customfield_XXXXX`

Or use the Jira API:

```bash
curl -u email@example.com:token \
  https://your-instance.atlassian.net/rest/api/3/fields | jq '.[] | select(.name=="Story Points")'
```

## Validation

Check your config for errors:

```bash
jira config show
```

This displays the resolved config (master + project overrides) and validates it.

## Examples

### Example Master Config (TerrorGems + HCP)

```json
{
  "jira": {
    "cloudId": "craighoad",
    "useMcpAuth": true,
    "maxAutoTransitionsPerRun": 10,
    "maxAutoReassignmentsPerRun": 5
  },
  "defaults": {
    "assignee": "craig",
    "reporter": "craig"
  },
  "guardrails": {
    "requireConfirmationFor": ["reassign", "move_epic"],
    "criticalLabels": ["critical", "security", "revenue", "compliance"],
    "staleDaysThreshold": 14
  },
  "projects": {
    "TG": {
      "name": "TerrorGems",
      "key": "TG",
      "epicLinkField": "customfield_10001"
    },
    "HCP": {
      "name": "HCP Platform",
      "key": "HCP",
      "epicLinkField": "customfield_10002"
    }
  }
}
```

### Example Per-Project Override (TerrorGems)

In your TerrorGems repo, `.claude/jira.json`:

```json
{
  "jira": {
    "projectKey": "TG"
  },
  "guardrails": {
    "criticalLabels": ["critical", "revenue", "compliance"]
  }
}
```

## Troubleshooting

### "Config validation failed"

Your config doesn't match the schema. Run:
```bash
jira config show
```

Check the error message for which field is invalid.

### "Cannot connect to Jira"

- Check `cloudId` is correct
- Verify API token is valid (if using `useMcpAuth: false`)
- Ensure Jira user has API access enabled

### "Custom field not found"

Check the field ID in Jira Settings → Custom Fields. IDs change per instance.

### "Project key not found"

Verify the project key exists and you have access. Check Jira project settings.
