# Jira Skill Architecture & Design Model

This document serves as a reference model for how Claude skills should be architected, documented, and deployed.

## Overview

The Jira Skill is a production-grade Claude skill that demonstrates:
- **Complete feature coverage** with 28 commands exposing 100% of internal APIs
- **Layered architecture** separating concerns: CLI, API, Intelligence, Workflow, Guardrails
- **Comprehensive documentation** at every level (user, developer, architect)
- **Enterprise-grade guardrails** with confirmation-required actions and safety limits
- **Configuration hierarchy** supporting master + per-repo overrides with validation
- **Full test coverage** with unit, integration, and edge case testing

## Directory Structure (Model)

```
jira-skill/
├── .claude/                          # Claude integration
│   ├── CLAUDE.md                     # Development workflow instructions
│   └── SKILL.md                      # Skill integration guide (for Claude Code/Desktop)
├── docs/                             # User & developer documentation
│   ├── ARCHITECTURE.md               # Technical design & patterns
│   ├── COMMANDS.md                   # Complete command reference
│   ├── CONFIG.md                     # Configuration guide
│   ├── EXAMPLES.md                   # Workflow examples
│   ├── README.md                     # Getting started
│   └── SKILL_ARCHITECTURE.md         # This file (design model)
├── config/                           # Configuration schemas & defaults
│   ├── jira.default.json             # Default configuration template
│   └── schema.json                   # Config validation schema (JSON Schema)
├── src/                              # Core implementation
│   ├── __init__.py                   # Package exports & version
│   ├── main.py                       # CLI: 28 commands, argument parsing, error handling
│   ├── jira_api.py                   # Jira Cloud REST API wrapper (authentication, requests)
│   ├── models.py                     # Data models: Epic, Ticket, Subtask, etc.
│   ├── config_loader.py              # Config resolution: master + repo overrides
│   ├── requirement_parser.py          # NLP: requirement decomposition
│   ├── auto_sizer.py                 # Estimation: story point sizing
│   ├── workflow_engine.py            # Automation: transitions, reassignments
│   ├── intelligence.py               # ML/AI: scope creep, blockers, velocity
│   ├── code_auditor.py               # Code-vs-Jira audit logic
│   ├── pr_linker.py                  # PR-to-ticket linking
│   └── guardrails.py                 # Safety: confirmation gates, limits
├── tests/                            # Test suite (64 tests, 100% passing)
│   ├── unit/                         # Unit tests per module
│   ├── integration/                  # Integration tests (API mocks)
│   ├── fixtures/                     # Test data
│   └── conftest.py                   # pytest configuration
├── SKILL.md                          # Skill definition (metadata + overview)
├── v2_RELEASE_NOTES.md               # Version 2.0.0 release notes
├── pyproject.toml                    # Package config: dependencies, entry point, metadata
├── Makefile                          # Common tasks: test, lint, coverage
└── .gitignore                        # Standard Python ignore rules
```

## Architectural Layers (Model)

### 1. CLI Layer (`main.py`)
**Purpose**: User-facing command interface with argument parsing and error handling

**Responsibilities**:
- 28 commands across 6 categories (config, create, link, view, manage, analyze)
- Argument parsing with sensible defaults
- Error handling and user-friendly messages
- Version display (`--version`)
- Help documentation (`--help`, `<command> --help`)

**Example Pattern**:
```python
def cmd_new_epic(args):
    """Create epic from requirement"""
    config = load_config()
    parser = RequirementParser()
    epics = parser.decompose(args.requirement)
    # ... create tickets in Jira
```

### 2. API Layer (`jira_api.py`)
**Purpose**: Thin wrapper around Jira Cloud REST API

**Responsibilities**:
- Authentication (Bearer token from environment variable)
- HTTP request handling (requests library)
- Error handling with retries for transient failures
- Request/response logging for debugging
- No business logic — just API calls

**Example Pattern**:
```python
class JiraAPI:
    def __init__(self, cloud_id: str, api_token: str):
        self.cloud_url = f"https://{cloud_id}.atlassian.net"
        self.headers = {"Authorization": f"Bearer {api_token}"}
    
    def get_ticket(self, ticket_key: str) -> dict:
        """Fetch ticket details from Jira"""
        return self._request("GET", f"/rest/api/3/issues/{ticket_key}")
```

### 3. Models Layer (`models.py`)
**Purpose**: Data structures representing Jira entities

**Responsibilities**:
- Type-safe dataclasses for Epic, Ticket, Subtask, etc.
- Validation on construction
- Serialization/deserialization
- No API calls — just data

**Example Pattern**:
```python
@dataclass
class Ticket:
    key: str
    summary: str
    status: str
    assignee: Optional[str] = None
    
    def is_blocked(self) -> bool:
        return self.status == "Blocked"
```

### 4. Intelligence Layer (`intelligence.py`, `auto_sizer.py`, etc.)
**Purpose**: AI-powered analysis and decision-making

**Responsibilities**:
- Requirement parsing and decomposition (NLP)
- Story point estimation (heuristics + learning)
- Scope creep detection (historical analysis)
- Blocker identification (dependency analysis)
- No external dependencies — just analysis

**Example Pattern**:
```python
class Intelligence:
    def detect_scope_creep(self, ticket: Ticket, history: List[Ticket]) -> float:
        """Return % increase in scope"""
        old_size = self._estimate_historical(ticket.key, history)
        new_size = auto_sizer.estimate(ticket.summary)
        return (new_size - old_size) / old_size * 100
```

### 5. Configuration Layer (`config_loader.py`)
**Purpose**: Configuration resolution and validation

**Responsibilities**:
- Load master config from `~/.claude/jira/config.json`
- Load repo config from `.claude/claude.json`
- Merge with proper override semantics
- Validate against schema
- Provide resolved config to commands

**Config Hierarchy**:
```
Master Config (~/.claude/jira/config.json)
    ↓ Read
Repo Config (.claude/claude.json)
    ↓ Merge (repo overrides master)
Resolved Config (used by commands)
```

### 6. Guardrails Layer (`guardrails.py`)
**Purpose**: Safety enforcement and permission gating

**Responsibilities**:
- Confirmation gates for sensitive operations
- Rate limiting and batch operation guards
- Audit logging
- User consent tracking

**Example Pattern**:
```python
class Guardrails:
    def require_confirmation(self, action: str, context: dict) -> bool:
        """True if user must confirm this action"""
        return action in self.config["requireConfirmationFor"]
    
    def confirm_with_user(self, prompt: str) -> bool:
        """Get explicit user approval"""
        return input(f"{prompt} (y/n): ").lower() == 'y'
```

### 7. Workflow Layer (`workflow_engine.py`)
**Purpose**: Orchestrate multi-step operations

**Responsibilities**:
- PR-to-ticket linking with auto-transition
- Auto-reassignment with workload balancing
- Bulk operations with guardrails
- Rollback on partial failures

**Example Pattern**:
```python
class WorkflowEngine:
    def link_pr_and_transition(self, pr_url: str, ticket_key: str):
        """Link PR and move ticket to In Progress"""
        # 1. Create remote link
        self.jira.create_remote_link(ticket_key, pr_url)
        # 2. Check guardrails
        if self.guardrails.should_auto_transition():
            # 3. Transition ticket
            self.jira.transition(ticket_key, "In Progress")
```

## Design Patterns (Model)

### Pattern 1: Dependency Injection
Each layer receives its dependencies on construction, not global state:
```python
def __init__(self, config: JiraConfig, api: JiraAPI, guardrails: Guardrails):
    self.config = config
    self.api = api
    self.guardrails = guardrails
```

### Pattern 2: Error Handling
Exceptions are caught at CLI layer and converted to user messages:
```python
try:
    result = intelligence.detect_scope_creep(ticket, history)
except JiraAPIError as e:
    logger.error(f"API call failed: {e}")
    print(f"❌ Could not check scope creep: {e.message}")
    return 1  # Exit code
```

### Pattern 3: Configuration Resolution
Master config is authoritative; repo config specifies overrides:
```python
config = loader.load()  # Reads master + repo, merges with proper precedence
# Guardrails, defaults, project metadata all come from resolved config
```

### Pattern 4: Command Symmetry
Each command follows consistent pattern:
```python
def cmd_<action>(args):
    """Description for --help"""
    config = load_config()  # Load config
    validate_args(args)     # Validate user input
    guardrails.gate(args)   # Check confirmations
    result = execute(args)  # Perform action
    display(result)         # Format output
    return 0 if success else 1
```

## Documentation Model

### User-Facing (SKILL.md)
- Quick start examples
- Feature overview
- Core commands with descriptions
- Troubleshooting

### Developer-Facing (docs/)
- ARCHITECTURE.md: System design and layer responsibilities
- COMMANDS.md: Complete command reference with options
- CONFIG.md: Configuration schema and examples
- EXAMPLES.md: Workflow walkthroughs
- README.md: Development setup

### Integration (. claude/SKILL.md)
- How Claude Code/Desktop should use the skill
- When to invoke which commands
- Guardrails and safety requirements
- Configuration and testing

## Testing Model

### Structure
```
tests/
├── unit/
│   ├── test_jira_api.py       # API wrapper tests
│   ├── test_models.py         # Data structure tests
│   ├── test_config_loader.py  # Config resolution tests
│   ├── test_intelligence.py   # Algorithm tests
│   └── ...
├── integration/
│   ├── test_e2e_create_epic.py    # End-to-end workflows
│   ├── test_e2e_link_pr.py        # Full command execution
│   └── ...
├── fixtures/
│   ├── sample_config.json     # Test configurations
│   ├── mock_tickets.json      # Test data
│   └── ...
└── conftest.py                # pytest setup
```

### Coverage
- Unit tests for each module (mocked dependencies)
- Integration tests with mock Jira API
- Edge cases: malformed input, API errors, missing config
- Target: >90% code coverage

### Running Tests
```bash
pytest tests/                    # All tests
pytest tests/unit/               # Unit only
pytest tests/ -k test_config     # By pattern
pytest --cov=src tests/          # With coverage
```

## Deployment Model

### Installation
```bash
pip install -e /path/to/jira-skill
```

This:
1. Installs dependencies (requests, jsonschema)
2. Registers `jira` command in PATH via entry point
3. Makes skill discoverable by Claude Code & Desktop
4. Enables editable development mode

### Configuration
```bash
~/.claude/jira/config.json       # Master config (user controls)
.claude/claude.json              # Per-repo binding (deployed by script)
JIRA_API_TOKEN                   # API authentication (environment)
```

### Version Management
- Semantic versioning (MAJOR.MINOR.PATCH)
- Version in `__init__.py`, `pyproject.toml`, `SKILL.md`
- Display via `jira --version`
- Release notes in `v2_RELEASE_NOTES.md`

## Quality Standards

### Code Quality
- Black formatting (line-length 100)
- Ruff linting (E, F, W, I, N rules)
- MyPy type checking (strict mode)
- No hardcoded values (use config)

### Security
- API tokens from environment variables, never hardcoded
- Input validation on all user input
- API request validation (schema validation)
- Audit logging for sensitive operations

### Documentation
- Docstrings on all public functions
- Type hints on all parameters and returns
- Examples in docstrings for complex functions
- README at package level and module level

### Testing
- >90% code coverage
- All public APIs have unit tests
- Integration tests for workflows
- Edge cases and error paths covered
- Mocked external dependencies

## Lessons for Skill Development

1. **Layered Architecture**: Separate concerns (CLI, API, business logic, safety)
2. **Configuration Hierarchy**: Master config + per-repo overrides
3. **Guardrails First**: Build safety into architecture, not as afterthought
4. **Complete Documentation**: User docs + developer docs + integration guide
5. **Comprehensive Testing**: Unit + integration + edge cases
6. **Semantic Versioning**: Clear versioning for backward compatibility
7. **Type Safety**: Use type hints and validation throughout
8. **Single Entry Point**: One `main()` function for all CLI invocation
9. **Error Handling**: Convert errors to user messages at CLI layer
10. **Dependency Injection**: Make dependencies explicit, not global

## Model Checklist for New Skills

- [ ] Layered architecture (CLI, API, Business Logic, Safety)
- [ ] Configuration schema with validation (JSON Schema)
- [ ] Comprehensive help text and examples
- [ ] Error handling with user-friendly messages
- [ ] Type hints on all public APIs
- [ ] Unit tests (>80% coverage)
- [ ] Integration tests with mocked dependencies
- [ ] Documentation: user guide + developer guide + architecture
- [ ] Entry point registered in pyproject.toml
- [ ] Version management (MAJOR.MINOR.PATCH)
- [ ] Security: no hardcoded secrets, environment variable auth
- [ ] Guardrails: confirmation gates for sensitive operations
- [ ] Configuration validation on startup

---

**Status**: This skill serves as a model for how Claude skills should be architected and deployed.
