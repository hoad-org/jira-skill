"""Jira-specific configuration with DevArmor integration.

Implements 4-level configuration hierarchy:
1. Code defaults (in config/jira.default.json)
2. Master config (~/.claude/jira/config.json)
3. Repo config (.claude/jira.json)
4. Environment variables (JIRA_*)

Also integrates with DevArmor policy configuration for governance.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema
from devarmor import ConfigLoader as DevArmorConfigLoader
from devarmor import PolicyConfig

from .models import JiraConfig, ProjectConfig

logger = logging.getLogger(__name__)


class JiraConfigLoader:
    """Load and merge master + per-project Jira configs with DevArmor integration."""

    def __init__(self, skill_root: Path):
        """Initialize with skill root directory.

        Args:
            skill_root: Root directory of the skill package
        """
        self.skill_root = skill_root
        self.schema_path = skill_root / "config" / "schema.json"
        self.default_config_path = skill_root / "config" / "jira.default.json"
        self.master_config_path = Path.home() / ".claude" / "jira" / "config.json"

        # DevArmor config loader (for policy config)
        self.devarmor_config_loader = DevArmorConfigLoader()

    def load_schema(self) -> Dict[str, Any]:
        """Load the config schema.

        Returns:
            Parsed JSON schema

        Raises:
            FileNotFoundError: If schema file doesn't exist
        """
        with open(self.schema_path) as f:
            return json.load(f)

    def load_default_config(self) -> Dict[str, Any]:
        """Load the default configuration.

        Returns:
            Default configuration dictionary

        Raises:
            FileNotFoundError: If default config doesn't exist
        """
        with open(self.default_config_path) as f:
            return json.load(f)

    def load_master_config(self) -> Dict[str, Any]:
        """Load the master config from ~/.claude/jira/config.json.

        Returns:
            Master configuration, or default if master config doesn't exist
        """
        if not self.master_config_path.exists():
            logger.debug("Master config not found, using defaults")
            return self.load_default_config()

        logger.debug(f"Loading master config from {self.master_config_path}")
        with open(self.master_config_path) as f:
            return json.load(f)

    def load_project_config(self, project_dir: Path) -> Optional[Dict[str, Any]]:
        """Load per-project config from .claude/jira.json.

        Args:
            project_dir: Project directory to load config from

        Returns:
            Project configuration, or None if not found
        """
        config_path = project_dir / ".claude" / "jira.json"
        if not config_path.exists():
            logger.debug(f"No project config found at {config_path}")
            return None

        logger.debug(f"Loading project config from {config_path}")
        with open(config_path) as f:
            return json.load(f)

    def load_env_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from environment variables.

        Environment variables follow pattern: JIRA_<PATH>_<TO>_<KEY>=value
        Example: JIRA_CLOUD_ID=abc123

        Returns:
            Environment configuration, or None if no JIRA_ variables set
        """
        import os

        config: Dict[str, Any] = {}

        for key, value in os.environ.items():
            if not key.startswith("JIRA_"):
                continue

            # Parse variable path (e.g., CLOUD_ID -> cloud_id)
            path_parts = key[5:].lower().split("_")  # Strip "JIRA_" prefix

            # Try to parse as JSON for structured values
            try:
                parsed_value: Any = json.loads(value)
            except json.JSONDecodeError:
                # Fallback to string
                parsed_value = value

            # Construct nested dictionary
            current = config
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[path_parts[-1]] = parsed_value

        return config if config else None

    def merge_configs(
        self,
        master: Dict[str, Any],
        project_override: Optional[Dict[str, Any]] = None,
        env_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Merge master, project, and environment configs.

        Priority (highest to lowest):
        1. Environment variables
        2. Project config
        3. Master config
        4. Code defaults

        Args:
            master: Master configuration
            project_override: Project-specific overrides
            env_override: Environment variable overrides

        Returns:
            Merged configuration dictionary
        """
        merged = json.loads(json.dumps(master))  # Deep copy

        # Apply project config
        if project_override:
            logger.debug("Merging project config overrides")
            for key in ["jira", "guardrails", "defaults", "prLinking", "requirements"]:
                if key in project_override:
                    if isinstance(merged.get(key), dict) and isinstance(
                        project_override[key], dict
                    ):
                        merged[key].update(project_override[key])
                    else:
                        merged[key] = project_override[key]

        # Apply environment config
        if env_override:
            logger.debug("Merging environment config overrides")
            for key in ["jira", "guardrails", "defaults", "prLinking", "requirements"]:
                if key in env_override:
                    if isinstance(merged.get(key), dict) and isinstance(env_override[key], dict):
                        merged[key].update(env_override[key])
                    else:
                        merged[key] = env_override[key]

        return merged

    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validate config against schema.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If config validation fails
        """
        schema = self.load_schema()
        try:
            jsonschema.validate(config, schema)
            logger.debug("Config validation passed")
        except jsonschema.ValidationError as e:
            raise ValueError(f"Config validation failed: {e.message}")

    def create_jira_config(self, config_dict: Dict[str, Any]) -> JiraConfig:
        """Convert dict to JiraConfig object.

        Args:
            config_dict: Configuration dictionary

        Returns:
            JiraConfig object
        """
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
                require_confirmation_for=guardrails.get(
                    "requireConfirmationFor", ["reassign", "move_epic"]
                ),
                critical_labels=guardrails.get(
                    "criticalLabels", ["critical", "security", "compliance"]
                ),
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
            require_confirmation_for=guardrails.get(
                "requireConfirmationFor", ["reassign", "move_epic"]
            ),
            never_auto_transition=guardrails.get("neverAutoTransition", ["Done", "Closed"]),
            never_auto_reassign_critical=guardrails.get("neverAutoReassignCritical", True),
            critical_labels=guardrails.get(
                "criticalLabels", ["critical", "security", "compliance", "blocker"]
            ),
            max_auto_create_subtasks=guardrails.get("maxAutoCreateSubtasks", 3),
            stale_days_threshold=guardrails.get("staleDaysThreshold", 14),
            complexity_keywords=requirements.get("complexityKeywords", {}),
            branch_pattern=pr_linking.get(
                "branchPattern", r"^(feat|fix|refactor|docs|test|chore)/([A-Z]+-[0-9]+)"
            ),
            title_pattern=pr_linking.get("titlePattern", r"^\[?([A-Z]+-[0-9]+)\]?"),
            auto_transition_on_pr_open=pr_linking.get("autoTransitionOnOpen", True),
            auto_transition_on_pr_merge=pr_linking.get("autoTransitionOnMerge", True),
            projects=projects,
        )

    def load_and_merge(self, project_dir: Optional[Path] = None) -> JiraConfig:
        """Load master + project + env config, validate, and return JiraConfig.

        Args:
            project_dir: Optional project directory for project-specific config

        Returns:
            Loaded and merged JiraConfig

        Raises:
            ValueError: If config validation fails
        """
        master = self.load_master_config()
        project = None
        if project_dir:
            project = self.load_project_config(project_dir)

        env = self.load_env_config()

        merged = self.merge_configs(master, project, env)
        self.validate_config(merged)
        return self.create_jira_config(merged)

    def init_master_config(self, interactive: bool = True) -> Path:
        """Initialize master config file.

        Args:
            interactive: If True, prompt for configuration values

        Returns:
            Path to created master config file

        Raises:
            FileExistsError: If config already exists
        """
        config_dir = self.master_config_path.parent
        config_dir.mkdir(parents=True, exist_ok=True)

        if self.master_config_path.exists():
            raise FileExistsError(f"Config already exists at {self.master_config_path}")

        if interactive:
            # Prompt for configuration
            config = self.load_default_config()

            cloud_id = input(
                "Enter your Jira Cloud ID (from https://your-instance.atlassian.net): "
            ).strip()
            if cloud_id:
                config["jira"]["cloudId"] = cloud_id

            assignee = input("Enter default assignee username [craig]: ").strip() or "craig"
            config["defaults"]["assignee"] = assignee
            config["defaults"]["reporter"] = assignee

            # Write config
            with open(self.master_config_path, "w") as f:
                json.dump(config, f, indent=2)

            logger.info(f"Created master config at {self.master_config_path}")
            return self.master_config_path
        else:
            # Just copy default
            default = self.load_default_config()
            with open(self.master_config_path, "w") as f:
                json.dump(default, f, indent=2)

            logger.info(f"Created master config at {self.master_config_path}")
            return self.master_config_path

    def show_config(self, project_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Show resolved config (for debugging).

        Args:
            project_dir: Optional project directory

        Returns:
            Config summary dictionary
        """
        config = self.load_and_merge(project_dir)
        return {
            "cloudId": config.cloud_id,
            "useMcpAuth": config.use_mcp_auth,
            "defaultAssignee": config.default_assignee,
            "projects": [p.key for p in config.projects.values()],
            "guardrails": {
                "requireConfirmationFor": config.require_confirmation_for,
                "criticalLabels": config.critical_labels,
            },
        }

    def load_devarmor_config(self) -> PolicyConfig:
        """Load DevArmor policy configuration.

        Returns:
            PolicyConfig for governance
        """
        logger.debug("Loading DevArmor policy configuration")
        return self.devarmor_config_loader.load_policy_config()
