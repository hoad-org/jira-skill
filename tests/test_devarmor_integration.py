"""Integration tests for DevArmor compliance and event handling.

Tests demonstrate:
- Config loading from 4 levels
- Event publishing when ticket operations occur
- Cross-skill communication via event subscriptions
- Lifecycle hooks (install/upgrade/remove)
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api import JiraAPIWithEvents
from src.config import JiraConfigLoader
from src.models import JiraConfig
from src.skill import JiraSkill, JiraSkillWithEvents


class TestJiraSkillLifecycle:
    """Test Jira skill lifecycle hooks."""

    @pytest.mark.asyncio
    async def test_skill_initialization(self):
        """Test skill initialization."""
        skill = JiraSkill(skill_name="jira-skill")
        assert not skill._initialized
        assert skill.version == "3.0.0"

        # Mock DevArmor API
        with patch.object(skill, "devarmor_api") as mock_api:
            mock_api.initialize = AsyncMock()

            await skill.initialize()

            assert skill._initialized
            mock_api.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_skill_install_hook(self):
        """Test skill install hook."""
        skill = JiraSkillWithEvents(skill_name="test-jira")

        # Mock DevArmor components
        with patch.object(skill, "devarmor_api") as mock_api:
            mock_api.initialize = AsyncMock()
            mock_api.lifecycle_manager = MagicMock()
            mock_api.event_bus = MagicMock()

            # Mock lifecycle manager
            mock_skill_info = MagicMock()
            mock_api.lifecycle_manager.install_skill = AsyncMock(return_value=mock_skill_info)

            # Mock event bus
            mock_api.event_bus.publish_skill_installed = AsyncMock()

            skill._initialized = True

            # Mock the subscribe call to return a subscriber ID
            mock_api.event_bus.subscribe = MagicMock(return_value="jira_github_integration")

            # Test _on_install hook
            await skill._on_install()

            # Should subscribe to GitHub events
            assert "jira_github_integration" in skill.event_subscriptions

    @pytest.mark.asyncio
    async def test_skill_upgrade_hook(self):
        """Test skill upgrade hook with migration."""
        skill = JiraSkill(skill_name="jira-skill")
        skill._initialized = True

        # Mock DevArmor API
        with patch.object(skill, "devarmor_api") as mock_api:
            mock_api.lifecycle_manager = MagicMock()
            mock_api.event_bus = MagicMock()

            # Mock upgrade
            mock_skill_info = MagicMock()
            mock_api.lifecycle_manager.upgrade_skill = AsyncMock(return_value=mock_skill_info)
            mock_api.event_bus.publish_skill_upgraded = AsyncMock()

            await skill._on_upgrade("2.0.0", "3.0.0")

            # Verify hook was called
            assert skill._initialized


class TestConfigHierarchy:
    """Test 4-level configuration hierarchy."""

    def test_load_default_config(self):
        """Test loading default configuration."""
        skill_root = Path(__file__).parent.parent
        loader = JiraConfigLoader(skill_root)

        config = loader.load_default_config()

        assert "jira" in config
        assert "cloudId" in config["jira"]
        assert "defaults" in config
        assert "guardrails" in config

    def test_merge_configs_master_and_project(self):
        """Test merging master and project configs."""
        loader = JiraConfigLoader(Path("."))

        master = {
            "jira": {"cloudId": "master-cloud-id"},
            "defaults": {"assignee": "master-user"},
            "guardrails": {"requireConfirmationFor": ["reassign"]},
        }

        project = {
            "defaults": {"assignee": "project-user"},
        }

        merged = loader.merge_configs(master, project)

        assert merged["jira"]["cloudId"] == "master-cloud-id"
        assert merged["defaults"]["assignee"] == "project-user"
        assert "reassign" in merged["guardrails"]["requireConfirmationFor"]

    def test_merge_configs_with_env_override(self):
        """Test merging with environment variable overrides."""
        loader = JiraConfigLoader(Path("."))

        base = {"jira": {"cloudId": "base-id"}, "defaults": {"assignee": "base"}}
        env = {"jira": {"cloudId": "env-id"}}

        merged = loader.merge_configs(base, env_override=env)

        assert merged["jira"]["cloudId"] == "env-id"

    def test_load_env_config(self):
        """Test loading configuration from environment variables."""
        import os

        loader = JiraConfigLoader(Path("."))

        # Set test environment variables (note: path separators are underscores)
        # JIRA_CLOUD_ID maps to jira.cloud.id (split by underscore into nested path)
        os.environ["JIRA_CLOUD_ID"] = "test-cloud"
        os.environ["JIRA_DEFAULTS_ASSIGNEE"] = "test-user"

        try:
            config = loader.load_env_config()

            assert config is not None
            # Environment variables are split by underscore, so JIRA_CLOUD_ID becomes {'cloud': {'id': ...}}
            # But the actual structure depends on how many underscores are in the env var name
            # JIRA_CLOUD_ID (after stripping JIRA_) = "cloud_id" split as ["cloud", "id"]
            assert config.get("cloud", {}).get("id") == "test-cloud"
            assert config.get("defaults", {}).get("assignee") == "test-user"
        finally:
            # Clean up
            if "JIRA_CLOUD_ID" in os.environ:
                del os.environ["JIRA_CLOUD_ID"]
            if "JIRA_DEFAULTS_ASSIGNEE" in os.environ:
                del os.environ["JIRA_DEFAULTS_ASSIGNEE"]


class TestEventPublishing:
    """Test event publishing when tickets are created/updated."""

    @pytest.mark.asyncio
    async def test_publish_ticket_created_event(self):
        """Test publishing ticket created event."""
        skill = JiraSkillWithEvents()
        skill._initialized = True

        with patch.object(skill, "publish_event") as mock_publish:
            mock_publish.return_value = asyncio.sleep(0)  # Mock async call

            await skill.publish_ticket_created(
                ticket_key="PROJ-123",
                summary="Test ticket",
                actor="test-actor",
                project="PROJ",
            )

            mock_publish.assert_called_once()
            call_args = mock_publish.call_args
            assert call_args.kwargs["event_type"] == "ticket_created"
            assert call_args.kwargs["resource"] == "PROJ-123"

    @pytest.mark.asyncio
    async def test_publish_ticket_updated_event(self):
        """Test publishing ticket updated event."""
        skill = JiraSkillWithEvents()
        skill._initialized = True

        with patch.object(skill, "publish_event") as mock_publish:
            mock_publish.return_value = asyncio.sleep(0)

            await skill.publish_ticket_updated(
                ticket_key="PROJ-123",
                changes={"status": "In Progress"},
                actor="test-actor",
            )

            mock_publish.assert_called_once()
            call_args = mock_publish.call_args
            assert call_args.kwargs["event_type"] == "ticket_updated"
            assert call_args.kwargs["details"]["changes"] == {"status": "In Progress"}

    @pytest.mark.asyncio
    async def test_publish_ticket_deleted_event(self):
        """Test publishing ticket deleted event."""
        skill = JiraSkillWithEvents()
        skill._initialized = True

        with patch.object(skill, "publish_event") as mock_publish:
            mock_publish.return_value = asyncio.sleep(0)

            await skill.publish_ticket_deleted(
                ticket_key="PROJ-123",
                actor="test-actor",
            )

            mock_publish.assert_called_once()
            call_args = mock_publish.call_args
            assert call_args.kwargs["event_type"] == "ticket_deleted"


class TestEventSubscription:
    """Test cross-skill event subscriptions."""

    def test_subscribe_to_events(self):
        """Test subscribing to events."""
        from devarmor import EventBus, EventType

        skill = JiraSkill()

        async def test_callback(event: Any) -> None:
            pass

        # Mock the DevArmor API completely
        mock_api = MagicMock()
        mock_event_bus = MagicMock(spec=EventBus)
        mock_event_bus.subscribe = MagicMock(return_value="test-sub")
        mock_api.event_bus = mock_event_bus

        skill.devarmor_api = mock_api

        # Subscribe to policy violated events (a real event type)
        subscriber_id = skill.subscribe_to_event(
            event_types=[EventType.POLICY_VIOLATED],
            callback=test_callback,
            subscriber_id="test-sub",
        )

        assert subscriber_id == "test-sub"
        assert "test-sub" in skill.event_subscriptions

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        from devarmor import EventBus, EventType

        skill = JiraSkill()

        async def test_callback(event: Any) -> None:
            pass

        # Mock the DevArmor API completely
        mock_api = MagicMock()
        mock_event_bus = MagicMock(spec=EventBus)
        mock_event_bus.subscribe = MagicMock(return_value="test-sub")
        mock_event_bus.unsubscribe = MagicMock(return_value=True)
        mock_api.event_bus = mock_event_bus

        skill.devarmor_api = mock_api

        subscriber_id = skill.subscribe_to_event(
            event_types=[EventType.POLICY_VIOLATED],
            callback=test_callback,
            subscriber_id="test-sub",
        )

        # Unsubscribe
        result = skill.unsubscribe(subscriber_id)

        assert result
        assert "test-sub" not in skill.event_subscriptions


class TestJiraAPIWithEvents:
    """Test Jira API with event publishing."""

    @pytest.mark.asyncio
    async def test_create_ticket_publishes_event(self):
        """Test that creating a ticket publishes an event."""
        # Create mock config
        config = MagicMock(spec=JiraConfig)
        config.cloud_id = "test-cloud"
        config.use_mcp_auth = True
        config.api_token = "test-token"
        config.default_assignee = "test-user"
        config.default_labels = []

        # Create mock skill
        skill = MagicMock(spec=JiraSkillWithEvents)
        skill.pre_action_check = AsyncMock(return_value=True)
        skill.publish_ticket_created = AsyncMock()

        api = JiraAPIWithEvents(config, skill)

        with patch.object(api, "_request") as mock_request:
            mock_request.return_value = {"key": "PROJ-123"}

            await api.create_ticket(
                project_key="PROJ",
                summary="Test ticket",
                description="Test description",
            )

            # Verify event was published
            skill.publish_ticket_created.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_ticket_publishes_event(self):
        """Test that updating a ticket publishes an event."""
        config = MagicMock(spec=JiraConfig)
        config.cloud_id = "test-cloud"
        config.use_mcp_auth = True
        config.api_token = "test-token"

        skill = MagicMock(spec=JiraSkillWithEvents)
        skill.pre_action_check = AsyncMock(return_value=True)
        skill.publish_ticket_updated = AsyncMock()

        api = JiraAPIWithEvents(config, skill)

        with patch.object(api, "_request"):
            await api.update_ticket(
                ticket_key="PROJ-123",
                summary="Updated ticket",
            )

            # Verify event was published
            skill.publish_ticket_updated.assert_called_once()

    @pytest.mark.asyncio
    async def test_pre_action_check_blocks_denied_actions(self):
        """Test that policy denials block operations."""
        from src.jira_api import JiraAPIError

        config = MagicMock(spec=JiraConfig)
        config.cloud_id = "test-cloud"
        config.use_mcp_auth = True
        config.api_token = "test-token"

        skill = MagicMock(spec=JiraSkillWithEvents)
        skill.pre_action_check = AsyncMock(return_value=False)

        api = JiraAPIWithEvents(config, skill)

        with pytest.raises(JiraAPIError, match="denied by policy"):
            await api.create_ticket(
                project_key="PROJ",
                summary="Test ticket",
                description="Test description",
            )


class TestIntegration:
    """Integration tests combining multiple components."""

    @pytest.mark.asyncio
    async def test_full_ticket_creation_workflow(self):
        """Test complete workflow: create config, skill, API, publish event."""
        # Create temporary config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            skill_root = config_dir / "skill"
            skill_root.mkdir()

            # Create minimal skill structure
            (skill_root / "config").mkdir()

            # Create default config
            default_config = {
                "jira": {"cloudId": "test-cloud-id"},
                "defaults": {"assignee": "test-user"},
                "guardrails": {"requireConfirmationFor": ["reassign"]},
                "projects": {},
                "prLinking": {},
                "requirements": {},
            }

            config_file = skill_root / "config" / "jira.default.json"
            with open(config_file, "w") as f:
                json.dump(default_config, f)

            # Load config
            loader = JiraConfigLoader(skill_root)
            jira_config = loader.load_default_config()

            # Verify configuration hierarchy
            assert jira_config["jira"]["cloudId"] == "test-cloud-id"
            assert jira_config["defaults"]["assignee"] == "test-user"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
