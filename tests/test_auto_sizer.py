"""Tests for auto-sizing logic."""

import pytest

from src.auto_sizer import AutoSizer
from src.models import JiraConfig


@pytest.fixture
def config():
    """Create test config."""
    return JiraConfig(cloud_id="test-instance")


@pytest.fixture
def sizer(config):
    """Create sizer instance."""
    return AutoSizer(config)


def test_base_points(sizer):
    """Test base story points."""
    points = sizer.estimate("Simple feature")
    assert points >= 1
    assert points <= 21


def test_complexity_keyword_integrate(sizer):
    """Test points for 'integrate' keyword."""
    simple = sizer.estimate("Simple feature")
    integration = sizer.estimate("Integrate with third-party API")
    assert integration > simple


def test_complexity_keyword_refactor(sizer):
    """Test points for 'refactor' keyword."""
    simple = sizer.estimate("Add feature")
    refactor = sizer.estimate("Refactor authentication module")
    assert refactor > simple


def test_length_adjustment(sizer):
    """Test that longer descriptions add points."""
    short = sizer.estimate("Add button")
    long = sizer.estimate(
        "Add button with multiple features, validation, testing, documentation and performance optimization"
    )
    assert long > short


def test_clamping(sizer):
    """Test that points are clamped to 1-21."""
    very_complex = sizer.estimate(
        "integrate refactor database migration security cross-team "
        "api testing performance optimization documentation unknown research spike"
    )
    assert 1 <= very_complex <= 21


def test_estimate_with_description(sizer):
    """Test estimation with both summary and description."""
    summary = "User authentication"
    description = "Implement OAuth2 integration with third-party provider, including testing and documentation"
    points = sizer.estimate(summary, description)
    assert points > 5


def test_multiple_keywords(sizer):
    """Test that multiple keywords accumulate points."""
    text = "Integrate with API and refactor database schema"
    points = sizer.estimate(text)
    assert points >= 5
