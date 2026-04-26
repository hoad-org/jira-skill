"""Tests for config loading and merging."""

import pytest
import json
import tempfile
from pathlib import Path
from src.config_loader import ConfigLoader
from src.models import JiraConfig


@pytest.fixture
def skill_root():
    """Get the skill root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def loader(skill_root):
    """Create config loader."""
    return ConfigLoader(skill_root)


def test_load_default_config(loader):
    """Test loading default config."""
    config = loader.load_default_config()
    assert "jira" in config
    assert config["jira"]["cloudId"] == "your-instance"


def test_load_schema(loader):
    """Test loading schema."""
    schema = loader.load_schema()
    assert "$schema" in schema
    assert "properties" in schema


def test_validate_default_config(loader):
    """Test that default config is valid."""
    config = loader.load_default_config()
    # Should not raise
    loader.validate_config(config)


def test_validate_invalid_config(loader):
    """Test validation fails on invalid config."""
    invalid = {}
    with pytest.raises(ValueError, match="Config validation failed"):
        loader.validate_config(invalid)


def test_merge_configs(loader):
    """Test merging master and project configs."""
    master = loader.load_default_config()

    project = {
        "jira": {
            "projectKey": "TG"
        },
        "guardrails": {
            "requireConfirmationFor": ["reassign"]
        }
    }

    merged = loader.merge_configs(master, project)

    # Master values preserved
    assert merged["jira"]["cloudId"] == master["jira"]["cloudId"]

    # Project overrides
    assert merged["guardrails"]["requireConfirmationFor"] == ["reassign"]


def test_merge_deep_dict(loader):
    """Test that merging handles nested dicts."""
    master = {"jira": {"a": 1, "b": 2}}
    project = {"jira": {"b": 3, "c": 4}}

    merged = loader.merge_configs(master, project)

    assert merged["jira"]["a"] == 1
    assert merged["jira"]["b"] == 3
    assert merged["jira"]["c"] == 4


def test_create_jira_config(loader):
    """Test converting dict to JiraConfig object."""
    config_dict = loader.load_default_config()
    config = loader.create_jira_config(config_dict)

    assert isinstance(config, JiraConfig)
    assert config.cloud_id == "your-instance"
    assert config.default_assignee == "craig"


def test_project_configs_created(loader):
    """Test that project configs are created."""
    config_dict = loader.load_default_config()
    config = loader.create_jira_config(config_dict)

    assert "TG" in config.projects
    assert "HCP" in config.projects
    assert config.projects["TG"].name == "TerrorGems"
    assert config.projects["HCP"].name == "HCP Platform"


def test_load_and_merge_no_project(loader, monkeypatch):
    """Test loading without project override."""
    # Mock load_master_config to return a predictable value
    def mock_load_master():
        return loader.load_default_config()

    monkeypatch.setattr(loader, "load_master_config", mock_load_master)
    config = loader.load_and_merge(project_dir=None)

    assert isinstance(config, JiraConfig)
    assert config.cloud_id == "your-instance"


def test_show_config(loader):
    """Test config display."""
    summary = loader.show_config()

    assert "cloudId" in summary
    assert "useMcpAuth" in summary
    assert "projects" in summary
