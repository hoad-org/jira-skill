"""Load and merge master + per-project Jira configs."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import jsonschema

from .models import JiraConfig, ProjectConfig


class ConfigLoader:
    """Load and validate Jira skill configuration."""

    def __init__(self, skill_root: Path):
        """Initialize with skill root directory."""
        self.skill_root = skill_root
        self.schema_path = skill_root / "config" / "schema.json"
        self.default_config_path = skill_root / "config" / "jira.default.json"
        self.master_config_path = Path.home() / ".claude" / "jira" / "config.json"

    def load_schema(self) -> Dict[str, Any]:
        """Load the config schema."""
        with open(self.schema_path) as f:
            return json.load(f)

    def load_default_config(self) -> Dict[str, Any]:
        """Load the default configuration."""
        with open(self.default_config_path) as f:
            return json.load(f)

    def load_master_config(self) -> Dict[str, Any]:
        """Load the master config from ~/.claude/jira/config.json."""
        if not self.master_config_path.exists():
            return self.load_default_config()

        with open(self.master_config_path) as f:
            return json.load(f)

    def load_project_config(self, project_dir: Path) -> Optional[Dict[str, Any]]:
        """Load per-project config from .claude/jira.json."""
        config_path = project_dir / ".claude" / "jira.json"
        if not config_path.exists():
            return None

        with open(config_path) as f:
            return json.load(f)

    def merge_configs(
        self,
        master: Dict[str, Any],
        project_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Merge master and project config (project overrides master)."""
        if not project_override:
            return master

        merged = json.loads(json.dumps(master))  # Deep copy

        # Shallow merge top-level keys
        for key in ["jira", "guardrails", "defaults", "prLinking", "requirements"]:
            if key in project_override:
                if isinstance(merged.get(key), dict) and isinstance(project_override[key], dict):
                    merged[key].update(project_override[key])
                else:
                    merged[key] = project_override[key]

        return merged

    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validate config against schema."""
        schema = self.load_schema()
        try:
            jsonschema.validate(config, schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Config validation failed: {e.message}")

    def create_jira_config(
        self,
        config_dict: Dict[str, Any]
    ) -> JiraConfig:
        """Convert dict to JiraConfig object."""
        jira_cfg = config_dict.get("jira", {})
        defaults = config_dict.get("defaults", {})
        guardrails = config_dict.get("guardrails", {})
        requirements = config_dict.get("requirements", {})
        pr_linking = config_dict.get("prLinking", {})

        # Create ProjectConfig objects
        projects = {}
        for key, proj_data in config_dict.get("projects", {}).items():
            projects[key] = ProjectConfig(
                key=key,
                name=proj_data.get("name", key),
                epic_link_field=proj_data.get("epicLinkField", "customfield_10001"),
                story_point_field=proj_data.get("storyPointField", "customfield_10000"),
                require_confirmation_for=guardrails.get("requireConfirmationFor", ["reassign", "move_epic"]),
                critical_labels=guardrails.get("criticalLabels", ["critical", "security", "compliance"]),
                max_auto_create_subtasks=guardrails.get("maxAutoCreateSubtasks", 3),
                stale_days_threshold=guardrails.get("staleDaysThreshold", 14),
            )

        return JiraConfig(
            cloud_id=jira_cfg.get("cloudId"),
            use_mcp_auth=jira_cfg.get("useMcpAuth", True),
            api_token=jira_cfg.get("apiToken"),
            max_auto_transitions_per_run=jira_cfg.get("maxAutoTransitionsPerRun", 10),
            max_auto_reassignments_per_run=jira_cfg.get("maxAutoReassignmentsPerRun", 5),
            default_assignee=defaults.get("assignee"),
            default_reporter=defaults.get("reporter"),
            default_labels=defaults.get("labels", []),
            require_confirmation_for=guardrails.get("requireConfirmationFor", ["reassign", "move_epic"]),
            never_auto_transition=guardrails.get("neverAutoTransition", ["Done", "Closed"]),
            never_auto_reassign_critical=guardrails.get("neverAutoReassignCritical", True),
            critical_labels=guardrails.get("criticalLabels", ["critical", "security", "compliance", "blocker"]),
            max_auto_create_subtasks=guardrails.get("maxAutoCreateSubtasks", 3),
            stale_days_threshold=guardrails.get("staleDaysThreshold", 14),
            complexity_keywords=requirements.get("complexityKeywords", {}),
            branch_pattern=pr_linking.get("branchPattern", r"^(feat|fix|refactor|docs|test|chore)/([A-Z]+-[0-9]+)"),
            title_pattern=pr_linking.get("titlePattern", r"^\[?([A-Z]+-[0-9]+)\]?"),
            auto_transition_on_pr_open=pr_linking.get("autoTransitionOnOpen", True),
            auto_transition_on_pr_merge=pr_linking.get("autoTransitionOnMerge", True),
            projects=projects,
        )

    def load_and_merge(
        self,
        project_dir: Optional[Path] = None
    ) -> JiraConfig:
        """Load master + project config, validate, and return JiraConfig."""
        master = self.load_master_config()
        project = None
        if project_dir:
            project = self.load_project_config(project_dir)

        merged = self.merge_configs(master, project)
        self.validate_config(merged)
        return self.create_jira_config(merged)

    def init_master_config(self, interactive: bool = True) -> Path:
        """Initialize master config file."""
        config_dir = self.master_config_path.parent
        config_dir.mkdir(parents=True, exist_ok=True)

        if self.master_config_path.exists():
            raise FileExistsError(f"Config already exists at {self.master_config_path}")

        if interactive:
            # Prompt for configuration
            config = self.load_default_config()

            cloud_id = input("Enter your Jira Cloud ID (from https://your-instance.atlassian.net): ").strip()
            if cloud_id:
                config["jira"]["cloudId"] = cloud_id

            assignee = input("Enter default assignee username [craig]: ").strip() or "craig"
            config["defaults"]["assignee"] = assignee
            config["defaults"]["reporter"] = assignee

            # Write config
            with open(self.master_config_path, "w") as f:
                json.dump(config, f, indent=2)

            return self.master_config_path
        else:
            # Just copy default
            default = self.load_default_config()
            with open(self.master_config_path, "w") as f:
                json.dump(default, f, indent=2)
            return self.master_config_path

    def show_config(self, project_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Show resolved config (for debugging)."""
        config = self.load_and_merge(project_dir)
        return {
            "cloudId": config.cloud_id,
            "useMcpAuth": config.use_mcp_auth,
            "defaultAssignee": config.default_assignee,
            "projects": [p.key for p in config.projects.values()],
            "guardrails": {
                "requireConfirmationFor": config.require_confirmation_for,
                "criticalLabels": config.critical_labels,
            }
        }
