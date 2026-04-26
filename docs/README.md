# Jira Skill Documentation

Complete documentation for the production-grade Jira Cloud management skill.

## Documentation Index

**User-Facing**:
1. **[Quick Start](#quick-start-commands)** — Essential commands to get started
2. **[Configuration Guide](CONFIG.md)** — Set up master config and per-project overrides
3. **[Command Reference](COMMANDS.md)** — Complete list of all 28 commands
4. **[Examples](EXAMPLES.md)** — Real-world workflows and use cases

**Developer & Architecture**:
5. **[Architecture](ARCHITECTURE.md)** — System design and how components interact
6. **[Skill Development Model](SKILL_ARCHITECTURE.md)** — How this skill should be used as a reference for building other skills

## What This Skill Does

The Jira skill automates keeping your Jira tickets in sync with your code:

✅ **Parse requirements** → automatically decompose into epics, tickets, subtasks  
✅ **Link PRs** → detect which ticket a PR is for, auto-transition status  
✅ **Audit tickets** → find mismatches between code and Jira  
✅ **Auto-size** → estimate story points from complexity  
✅ **Guardrails** → require confirmation for critical actions  
✅ **Multi-project** → manage multiple projects with unified config  

## Key Concepts

### Requirement Scoping

When you ask the skill to create an epic from a requirement like:

```
"Implement user authentication with OAuth2 and session management"
```

It automatically:
1. Estimates total story points (~15pts)
2. Detects it's complex (involves multiple domains)
3. Decomposes into tickets:
   - OAuth2 integration (~5pts)
   - Session management (~5pts)
   - ...
4. Suggests subtasks for each ticket

### PR Linking

The skill detects which ticket a PR is for using priority order:

1. **Branch name**: `feat/TG-123-auth` → TG-123 ✅ Most reliable
2. **PR title**: `[TG-123] Implement auth` → TG-123 ✅ Good
3. **PR description**: `Closes TG-123` → TG-123 ✅ Fallback

### Guardrails

Safety first. Critical actions require confirmation:
- Reassigning critical tickets
- Moving tickets between epics
- Closing tickets with open subtasks
- Status transitions to "Done"

### Config Hierarchy

```
Defaults
    ↓
Master config (~/.claude/jira/config.json)
    ↓
Project config (.claude/jira.json) [overrides master]
```

Each layer can override the previous one. Project config takes precedence.

## Common Workflows

### Create Epic from Requirement
```bash
jira new-epic "Build payment processing with Stripe integration"
```

### Link PR and Auto-Transition
```bash
jira link-pr https://github.com/org/repo/pull/42
```
(Automatically detects TG-123 from branch name and transitions to "In Progress")

### Audit Code vs Tickets
```bash
jira audit TG --since 7
```

### Update Tickets from Code
```bash
jira update-tickets
```

### Find Stale Tickets
```bash
jira list-stale TG --days 14
```

## Configuration

### Master Config
**Path**: `~/.claude/jira/config.json`

Controls:
- Jira Cloud instance
- Default values (assignee, reporter, labels)
- Guardrail rules (what requires confirmation)
- Auto-sizing keywords
- All projects in your Jira

**First time**: `jira config init` (interactive setup)

### Per-Project Config
**Path**: `.claude/jira.json` in your project repo

Overrides master config for:
- Project-specific guardrails
- Custom keyword weights
- Project-specific defaults

**Example**:
```json
{
  "jira": {
    "projectKey": "TG"
  },
  "guardrails": {
    "criticalLabels": ["critical", "revenue"]
  }
}
```

See [CONFIG.md](CONFIG.md) for full reference.

## Commands

### Core Commands

| Command | Purpose |
|---------|---------|
| `jira new-epic <requirement>` | Create epic from requirement description |
| `jira new-ticket <epic> <requirement>` | Add ticket to epic |
| `jira link-pr <url>` | Link PR to ticket (auto-detect) |
| `jira audit <project>` | Compare code vs Jira, find mismatches |
| `jira update-tickets` | Sync ticket updates from code |
| `jira status [project]` | Show project status summary |
| `jira list-stale <project>` | Find inactive tickets |
| `jira reassign <ticket> <user>` | Reassign ticket |

### Config Commands

| Command | Purpose |
|---------|---------|
| `jira config init` | Initialize master config |
| `jira config show` | Display resolved config |

See [COMMANDS.md](COMMANDS.md) for complete reference.

## Testing

Run tests:
```bash
make test
```

Run with coverage:
```bash
make coverage
```

Run specific test:
```bash
pytest tests/test_auto_sizer.py -v
```

## Development

### Setup
```bash
make install
```

### Code Quality
```bash
make lint          # Check with ruff
make format        # Auto-format with black
make type-check    # Type check with mypy
make check         # Run all checks
```

### Project Structure
```
src/
├── models.py              # Data models
├── config_loader.py       # Config loading/merging
├── jira_api.py            # Jira Cloud API client
├── requirement_parser.py  # Requirement decomposition
├── auto_sizer.py          # Story point estimation
├── pr_linker.py           # PR detection
├── guardrails.py          # Safety checks
└── [TODO modules]         # Code auditor, workflow engine, etc.

tests/
├── test_*.py              # Unit tests
└── fixtures/              # Test data/mocks

docs/
├── README.md              # This file
├── CONFIG.md              # Configuration guide
├── COMMANDS.md            # Command reference
├── EXAMPLES.md            # Usage examples
└── ARCHITECTURE.md        # Technical design
```

## TODO / Future Work

The skill is built in phases:

### Phase 1 (Complete) ✅
- ✅ Config system (master + project overrides)
- ✅ Models & data structures
- ✅ Jira API client
- ✅ Requirement parser & auto-sizer
- ✅ PR linker
- ✅ Guardrails & validation
- ✅ Unit tests
- ✅ Documentation

### Phase 2 (In Progress)
- [ ] CLI dispatcher (main.py)
- [ ] Code auditor module
- [ ] Workflow engine (transitions, reassignments)
- [ ] Intelligence module (scope creep, stale detection, velocity)
- [ ] Integration tests
- [ ] Error handling improvements

### Phase 3 (Future)
- [ ] Slack notifications
- [ ] Email notifications
- [ ] Historical velocity tracking
- [ ] Dependency graph visualization
- [ ] Sprint planning automation
- [ ] Risk assessment
- [ ] Cost estimation
- [ ] Bulk operations

## Common Issues

### Config Validation Error

**Problem**: "Config validation failed"

**Solution**: Check the config file matches schema
```bash
jira config show
```
Look for which field is invalid. Check [CONFIG.md](CONFIG.md) for correct format.

### Can't Connect to Jira

**Problem**: "Cannot connect to Jira"

**Solution**: 
1. Verify `cloudId` is correct (from instance URL)
2. Check API token is valid (if not using MCP auth)
3. Ensure user has API access enabled

### PR Not Detected

**Problem**: `link-pr` can't find the ticket

**Solution**:
1. Check branch name format: `feat/TG-123-description`
2. Or manually specify: `jira link-pr <url> --ticket TG-123`

## Architecture Highlights

The skill is built with:

- **Clean separation**: Core logic isolated from CLI/API
- **Testable modules**: Each module has independent unit tests
- **Configuration as code**: All behavior can be customized
- **Safety first**: Guardrails prevent mistakes
- **Intelligent defaults**: Auto-sizing, scope detection, duplicate prevention

See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details.

## Contributing

To add a new feature:

1. Create module in `src/`
2. Add unit tests in `tests/`
3. Update docs
4. Run `make check` to pass all checks

## License

[Add your license here]

## Support

For issues, questions, or ideas:
- Check [EXAMPLES.md](EXAMPLES.md) for common workflows
- Review [CONFIG.md](CONFIG.md) for configuration
- See [ARCHITECTURE.md](ARCHITECTURE.md) for how it works
- Run `jira <command> --help` for command help
