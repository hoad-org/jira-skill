"""Jira Skill CLI Dispatcher."""

import sys
import json
from pathlib import Path
from typing import Optional

from .config_loader import ConfigLoader
from .jira_api import JiraAPI, JiraAPIError
from .requirement_parser import RequirementParser
from .auto_sizer import AutoSizer
from .pr_linker import PRLinker
from .guardrails import Guardrails
from .code_auditor import CodeAuditor
from .workflow_engine import WorkflowEngine
from .intelligence import Intelligence


class JiraSkillCLI:
    """Jira Skill CLI."""

    def __init__(self):
        """Initialize CLI."""
        self.skill_root = Path(__file__).parent.parent
        self.config_loader = ConfigLoader(self.skill_root)
        self.config = None
        self.jira_api = None
        self.parser = None
        self.sizer = None
        self.pr_linker = None
        self.guardrails = None
        self.auditor = None
        self.workflow = None
        self.intelligence = None

    def _init_modules(self, project_dir: Optional[Path] = None):
        """Initialize all modules."""
        if self.config:
            return  # Already initialized

        self.config = self.config_loader.load_and_merge(project_dir)
        self.jira_api = JiraAPI(self.config)
        self.parser = RequirementParser(self.config)
        self.sizer = AutoSizer(self.config)
        self.pr_linker = PRLinker(self.config)
        self.guardrails = Guardrails(self.config)
        self.auditor = CodeAuditor(self.config, project_dir)
        self.workflow = WorkflowEngine(self.config, self.jira_api, self.guardrails)
        self.intelligence = Intelligence(self.config)

    def cmd_config_init(self):
        """Initialize master config."""
        try:
            path = self.config_loader.init_master_config(interactive=True)
            self._print_success(f"✅ Config initialized at {path}")
            return True
        except FileExistsError:
            self._print_error("Config already exists. Delete ~/.claude/jira/config.json to reinitialize.")
            return False
        except Exception as e:
            self._print_error(f"Failed to initialize config: {e}")
            return False

    def cmd_config_show(self, project_dir: Optional[Path] = None):
        """Show resolved config."""
        self._init_modules(project_dir)
        summary = self.config_loader.show_config(project_dir)
        self._print_json(summary)
        return True

    def cmd_new_epic(self, requirement: str, project: Optional[str] = None, auto_approve: bool = False):
        """Create epic from requirement."""
        self._init_modules()

        try:
            # Parse requirement
            self._print_info("📋 Parsing requirement...")
            scope = self.parser.parse(requirement)

            # Display scope tree
            self._print_info("\nSCOPE TREE:")
            print(self.parser.format_scope(scope))

            # Get user confirmation
            if not auto_approve:
                response = input("\nCreate epic? [y/n]: ").strip().lower()
                if response != "y":
                    self._print_info("Cancelled.")
                    return True

            # Create epic
            self._print_info("\n✨ Creating epic...")
            plan = self._create_epic_from_scope(scope, project)

            executed, errors = self.workflow.execute_plan(plan, self._confirm_callback)

            if errors:
                for error in errors:
                    self._print_error(error)

            self._print_success(f"✅ Created {executed} items")
            return len(errors) == 0

        except Exception as e:
            self._print_error(f"Failed to create epic: {e}")
            return False

    def cmd_link_pr(
        self,
        pr_url: str,
        ticket: Optional[str] = None,
        auto_approve: bool = False
    ):
        """Link PR to ticket."""
        self._init_modules()

        try:
            # Extract PR details from URL or use provided ticket
            if ticket:
                ticket_key = ticket
            else:
                # Try to detect from git
                ticket_key = self._detect_ticket_from_git()

            if not ticket_key:
                self._print_error("Could not detect ticket. Use --ticket to specify.")
                return False

            # Plan linking
            plan = self.workflow.plan_pr_linking(ticket_key, pr_url, auto_transition=True)

            # Execute
            self._print_info(f"🔗 Linking PR to {ticket_key}...")
            executed, errors = self.workflow.execute_plan(plan, self._confirm_callback)

            if errors:
                for error in errors:
                    self._print_error(error)

            self._print_success(f"✅ Linked PR")
            return len(errors) == 0

        except Exception as e:
            self._print_error(f"Failed to link PR: {e}")
            return False

    def cmd_audit(self, project: str, since_days: int = 7, fix: bool = False):
        """Audit tickets vs code."""
        self._init_modules()

        try:
            self._print_info(f"🔍 Auditing {project} project...")

            # Get tickets
            tickets = self.jira_api.get_tickets(project)

            # Audit
            findings = self.auditor.audit(tickets, since_days)

            if not findings:
                self._print_success("✅ No issues found")
                return True

            # Display findings
            errors = [f for f in findings if f.severity == "error"]
            warnings = [f for f in findings if f.severity == "warning"]

            if errors:
                self._print_error(f"\nERRORS ({len(errors)}):")
                for finding in errors:
                    print(f"  ❌ {finding}")

            if warnings:
                self._print_warning(f"\nWARNINGS ({len(warnings)}):")
                for finding in warnings:
                    print(f"  ⚠️  {finding}")

            self._print_info(f"\nSUMMARY: {len(errors)} errors, {len(warnings)} warnings")

            return len(errors) == 0

        except JiraAPIError as e:
            self._print_error(f"Jira API error: {e}")
            return False
        except Exception as e:
            self._print_error(f"Audit failed: {e}")
            return False

    def cmd_status(self, project: str):
        """Show project status."""
        self._init_modules()

        try:
            self._print_info(f"📊 {project} Status")

            # Get epics
            epics = self.jira_api.get_epics(project)

            if not epics:
                self._print_warning("No epics found")
                return True

            # Calculate velocity
            completed = [t for epic in epics for t in epic.tickets if t.status == "Done"]
            velocity = self.intelligence.calculate_velocity(completed)

            # Display status
            for epic in epics[:5]:  # Show first 5
                health = self.intelligence.calculate_epic_health(epic)
                emoji = {"complete": "✅", "good": "🟢", "fair": "🟡", "slow": "🔴"}
                status_emoji = emoji.get(health["health"], "❓")

                print(f"\n{epic.key} {status_emoji} {epic.name}")
                print(f"  {health['summary']}")

            print(f"\n📈 Velocity: {velocity:.1f} points/day")

            return True

        except JiraAPIError as e:
            self._print_error(f"Jira API error: {e}")
            return False
        except Exception as e:
            self._print_error(f"Status check failed: {e}")
            return False

    def cmd_list_stale(self, project: str, days: int = 14):
        """List stale tickets."""
        self._init_modules()

        try:
            self._print_info(f"🧊 Stale tickets in {project} (>{days} days, In Progress)")

            # Get tickets
            tickets = self.jira_api.get_tickets(project)

            # Find stale
            stale = self.intelligence.find_stale_tickets(tickets, days)

            if not stale:
                self._print_success("✅ No stale tickets")
                return True

            for ticket in stale:
                print(f"\n{ticket.key}: {ticket.summary}")
                print(f"  Status: {ticket.status}")
                print(f"  Assignee: {ticket.assignee or 'Unassigned'}")

            return True

        except JiraAPIError as e:
            self._print_error(f"Jira API error: {e}")
            return False
        except Exception as e:
            self._print_error(f"Failed: {e}")
            return False

    def cmd_reassign(self, ticket: str, assignee: str):
        """Reassign ticket."""
        self._init_modules()

        try:
            plan = self.workflow.plan_reassignment(ticket, assignee)

            # Get confirmation if needed
            executed, errors = self.workflow.execute_plan(plan, self._confirm_callback)

            if errors:
                for error in errors:
                    self._print_error(error)
                return False

            self._print_success(f"✅ Reassigned {ticket} to {assignee}")
            return True

        except Exception as e:
            self._print_error(f"Failed to reassign: {e}")
            return False

    def cmd_show_ticket(self, ticket: str):
        """Show ticket details."""
        self._init_modules()

        try:
            ticket_obj = self.jira_api.get_ticket(ticket)

            print(f"\n📋 {ticket_obj.key}: {ticket_obj.summary}")
            print(f"   Status: {ticket_obj.status}")
            print(f"   Assignee: {ticket_obj.assignee or 'Unassigned'}")
            print(f"   Points: {ticket_obj.story_points or '-'}")
            if ticket_obj.description:
                print(f"   Description: {ticket_obj.description[:100]}...")
            if ticket_obj.epic_key:
                print(f"   Epic: {ticket_obj.epic_key}")
            if ticket_obj.sub_tasks:
                print(f"   Subtasks: {len(ticket_obj.sub_tasks)}")

            return True

        except Exception as e:
            self._print_error(f"Failed to fetch ticket: {e}")
            return False

    def cmd_move_to_epic(self, ticket: str, epic: str, auto_approve: bool = False):
        """Move ticket to epic."""
        self._init_modules()

        try:
            self._print_info(f"🔗 Moving {ticket} to {epic}...")

            plan = self.workflow.plan_move_to_epic(ticket, epic)

            # Get confirmation if needed
            if not auto_approve:
                response = input("\nProceed? [y/n]: ").strip().lower()
                if response != "y":
                    self._print_info("Cancelled.")
                    return True

            executed, errors = self.workflow.execute_plan(plan, self._confirm_callback)

            if errors:
                for error in errors:
                    self._print_error(error)
                return False

            self._print_success(f"✅ Moved {ticket} to {epic}")
            return True

        except Exception as e:
            self._print_error(f"Failed to move ticket: {e}")
            return False

    def cmd_add_comment(self, ticket: str, message: str):
        """Add comment to ticket."""
        self._init_modules()

        try:
            self._print_info(f"💬 Adding comment to {ticket}...")
            self.jira_api.add_comment(ticket, message)
            self._print_success(f"✅ Comment added")
            return True

        except Exception as e:
            self._print_error(f"Failed to add comment: {e}")
            return False

    def cmd_find_blockers(self, project: str):
        """Find blocked tickets."""
        self._init_modules()

        try:
            self._print_info(f"🚧 Blocked tickets in {project}...")

            tickets = self.jira_api.get_tickets(project)
            blocked = self.intelligence.detect_blocked_tickets(tickets)

            if not blocked:
                self._print_success("✅ No blocked tickets")
                return True

            print(f"\nFound {len(blocked)} blocked tickets:")
            for ticket in blocked[:10]:  # Show first 10
                print(f"\n{ticket['ticket'].key}: {ticket['ticket'].summary}")
                if ticket.get('blocker_text'):
                    print(f"  Blocked by: {ticket['blocker_text']}")

            return True

        except Exception as e:
            self._print_error(f"Failed to find blockers: {e}")
            return False

    def cmd_estimate_epic(self, epic: str):
        """Estimate epic completion date."""
        self._init_modules()

        try:
            epic_obj = self.jira_api.get_epic(epic)

            if not epic_obj:
                self._print_error(f"Epic {epic} not found")
                return False

            # Get completed tickets for velocity
            project = epic.split("-")[0]
            all_tickets = self.jira_api.get_tickets(project)
            completed = [t for t in all_tickets if t.status == "Done"]
            velocity = self.intelligence.calculate_velocity(completed)

            if velocity <= 0:
                self._print_warning("⚠️  Cannot estimate: no velocity data")
                return False

            completion = self.intelligence.estimate_completion_date(epic_obj, velocity)

            print(f"\n📊 {epic_obj.key}: {epic_obj.name}")
            print(f"   Completed: {epic_obj.completed_points}/{epic_obj.total_points} pts")
            print(f"   Progress: {epic_obj.progress_percent}%")
            print(f"   Velocity: {velocity:.1f} pts/day")
            if completion:
                print(f"   Estimated completion: {completion['estimated_date']}")
                print(f"   Days remaining: {completion['days_remaining']}")

            return True

        except Exception as e:
            self._print_error(f"Failed to estimate epic: {e}")
            return False

    def cmd_suggest_consolidation(self, project: str):
        """Suggest ticket consolidation."""
        self._init_modules()

        try:
            self._print_info(f"🔍 Finding consolidation opportunities in {project}...")

            # Get tickets
            tickets = self.jira_api.get_tickets(project)

            # Find consolidation suggestions
            suggestions = self.intelligence.suggest_ticket_consolidation(tickets)

            if not suggestions:
                self._print_success("✅ No consolidation suggestions")
                return True

            print(f"\nFound {len(suggestions)} consolidation opportunities:")
            for suggestion in suggestions[:10]:  # Show first 10
                print(f"\n{suggestion['primary'].key}: {suggestion['primary'].summary}")
                print(f"   Similar to:")
                for similar in suggestion.get('similar_tickets', [])[:3]:
                    print(f"     - {similar.key}: {similar.summary}")

            return True

        except Exception as e:
            self._print_error(f"Failed to find consolidation suggestions: {e}")
            return False

    def cmd_list_epics(self, project: str):
        """List all epics in project."""
        self._init_modules()

        try:
            self._print_info(f"📋 Epics in {project}")

            epics = self.jira_api.get_epics(project)

            if not epics:
                self._print_warning("No epics found")
                return True

            for epic in epics:
                status_emoji = {"To Do": "🔵", "In Progress": "🟡", "Done": "🟢"}.get(epic.status, "❓")
                print(f"\n{epic.key} {status_emoji} {epic.name}")
                print(f"   Status: {epic.status}")
                if epic.assignee:
                    print(f"   Assignee: {epic.assignee}")

            return True

        except Exception as e:
            self._print_error(f"Failed to list epics: {e}")
            return False

    def cmd_epic_info(self, epic: str):
        """Show complete epic with all tickets."""
        self._init_modules()

        try:
            epic_obj = self.jira_api.get_epic(epic)

            if not epic_obj:
                self._print_error(f"Epic {epic} not found")
                return False

            print(f"\n📊 {epic_obj.key}: {epic_obj.name}")
            print(f"   Status: {epic_obj.status}")
            if epic_obj.assignee:
                print(f"   Assignee: {epic_obj.assignee}")
            print(f"   Progress: {epic_obj.progress_percent}% ({epic_obj.completed_points}/{epic_obj.total_points} pts)")

            if not epic_obj.tickets:
                print("   No tickets")
                return True

            # Breakdown by status
            by_status = {}
            for ticket in epic_obj.tickets:
                status = ticket.status
                if status not in by_status:
                    by_status[status] = []
                by_status[status].append(ticket)

            print("\n   Tickets:")
            for status in ["To Do", "In Progress", "In Review", "Done"]:
                if status in by_status:
                    emoji = {"To Do": "🔵", "In Progress": "🟡", "In Review": "🟠", "Done": "🟢"}.get(status)
                    print(f"     {emoji} {status} ({len(by_status[status])})")
                    for ticket in by_status[status]:
                        points = f" ({ticket.story_points}pts)" if ticket.story_points else ""
                        print(f"       • {ticket.key}: {ticket.summary}{points}")

            return True

        except Exception as e:
            self._print_error(f"Failed to get epic info: {e}")
            return False

    def cmd_quick_create(self, project: str, summary: str, points: int = 3):
        """Create a single ticket quickly."""
        self._init_modules()

        try:
            self._print_info(f"🎯 Creating ticket in {project}...")

            # Estimate points if not specified
            if points == 3:
                points = self.sizer.estimate(summary)

            print(f"   Summary: {summary}")
            print(f"   Points: {points}")

            response = input("\nCreate ticket? [y/n]: ").strip().lower()
            if response != "y":
                self._print_info("Cancelled.")
                return True

            key = self.jira_api.create_ticket(
                project_key=project,
                summary=summary,
                description=f"Created by quick-create",
                story_points=points
            )

            self._print_success(f"✅ Created {key}")
            return True

        except Exception as e:
            self._print_error(f"Failed to create ticket: {e}")
            return False

    def cmd_create_subtask(self, parent: str, summary: str, points: int = 1):
        """Create subtask under ticket."""
        self._init_modules()

        try:
            self._print_info(f"📌 Creating subtask under {parent}...")
            print(f"   Summary: {summary}")
            print(f"   Points: {points}")

            response = input("\nCreate subtask? [y/n]: ").strip().lower()
            if response != "y":
                self._print_info("Cancelled.")
                return True

            key = self.jira_api.create_subtask(
                parent_key=parent,
                summary=summary,
                story_points=points
            )

            self._print_success(f"✅ Created {key}")
            return True

        except Exception as e:
            self._print_error(f"Failed to create subtask: {e}")
            return False

    def cmd_transition(self, ticket: str, status: str, auto_approve: bool = False):
        """Manually transition ticket to status."""
        self._init_modules()

        try:
            self._print_info(f"🔄 Transitioning {ticket} to {status}...")

            if not auto_approve:
                response = input("\nProceed? [y/n]: ").strip().lower()
                if response != "y":
                    self._print_info("Cancelled.")
                    return True

            self.jira_api.transition_ticket(ticket, status)
            self._print_success(f"✅ Transitioned to {status}")
            return True

        except Exception as e:
            self._print_error(f"Failed to transition: {e}")
            return False

    def cmd_detect_scope_creep(self, project: str):
        """Find tickets with significant scope creep."""
        self._init_modules()

        try:
            self._print_info(f"📈 Finding scope creep in {project}...")

            tickets = self.jira_api.get_tickets(project)
            creeping = self.intelligence.detect_scope_creep_tickets(tickets)

            if not creeping:
                self._print_success("✅ No significant scope creep detected")
                return True

            print(f"\nFound {len(creeping)} tickets with scope creep:")
            for ticket in creeping[:10]:
                print(f"\n{ticket['ticket'].key}: {ticket['ticket'].summary}")
                if ticket.get('growth_percent'):
                    print(f"   Growth: {ticket['growth_percent']:.0f}%")
                if ticket.get('original_estimate'):
                    print(f"   Original: {ticket['original_estimate']}pts → Current: {ticket['ticket'].story_points}pts")

            return True

        except Exception as e:
            self._print_error(f"Failed to detect scope creep: {e}")
            return False

    def cmd_risk_assessment(self, epic: str):
        """Get risk assessment for epic."""
        self._init_modules()

        try:
            epic_obj = self.jira_api.get_epic(epic)

            if not epic_obj:
                self._print_error(f"Epic {epic} not found")
                return False

            # Get velocity for risk assessment
            project = epic.split("-")[0]
            all_tickets = self.jira_api.get_tickets(project)
            completed = [t for t in all_tickets if t.status == "Done"]
            velocity = self.intelligence.calculate_velocity(completed)

            if velocity <= 0:
                self._print_warning("⚠️  Cannot assess risk: no velocity data")
                return False

            risk = self.intelligence.risk_assessment(epic_obj, velocity)

            print(f"\n⚠️  {epic_obj.key}: {epic_obj.name}")
            print(f"\n   Risk Assessment:")
            if risk.get('overall_risk'):
                print(f"   Overall Risk: {risk['overall_risk']}")
            if risk.get('schedule_risk'):
                print(f"   Schedule Risk: {risk['schedule_risk']}")
            if risk.get('unassigned_count'):
                print(f"   Unassigned: {risk['unassigned_count']}")
            if risk.get('blocker_count'):
                print(f"   Blockers: {risk['blocker_count']}")
            if risk.get('scope_risk'):
                print(f"   Scope Risk: {risk['scope_risk']}")

            return True

        except Exception as e:
            self._print_error(f"Failed to assess risk: {e}")
            return False

    def cmd_decompose_preview(self, requirement: str):
        """Preview decomposition without creating."""
        self._init_modules()

        try:
            self._print_info("📋 Decomposing requirement...\n")
            scope = self.parser.parse(requirement)
            print(self.parser.format_scope(scope))
            self._print_info(f"\nThis would create: {len([s for s in scope.sub_items] if scope.sub_items else [])} items")
            return True

        except Exception as e:
            self._print_error(f"Failed to decompose: {e}")
            return False

    def cmd_handle_pr_merge(self, ticket: str, auto_approve: bool = False):
        """Handle PR merge (auto-transition ticket)."""
        self._init_modules()

        try:
            self._print_info(f"🔄 Handling PR merge for {ticket}...")

            plan = self.workflow.plan_pr_merge(ticket, auto_transition=True)

            if not auto_approve:
                response = input("\nProceed with auto-transition? [y/n]: ").strip().lower()
                if response != "y":
                    self._print_info("Cancelled.")
                    return True

            executed, errors = self.workflow.execute_plan(plan, self._confirm_callback)

            if errors:
                for error in errors:
                    self._print_error(error)
                return False

            self._print_success(f"✅ Handled merge for {ticket}")
            return True

        except Exception as e:
            self._print_error(f"Failed to handle merge: {e}")
            return False

    def cmd_create_ticket_in_epic(self, project: str, epic: str, summary: str, points: int = 3):
        """Create ticket and link to epic."""
        self._init_modules()

        try:
            self._print_info(f"🎯 Creating ticket in {project} under {epic}...")
            print(f"   Summary: {summary}")
            print(f"   Points: {points}")
            print(f"   Epic: {epic}")

            response = input("\nCreate ticket? [y/n]: ").strip().lower()
            if response != "y":
                self._print_info("Cancelled.")
                return True

            plan = self.workflow.plan_ticket_creation(project, summary, f"Created under {epic}", points, epic)
            executed, errors = self.workflow.execute_plan(plan, self._confirm_callback)

            if errors:
                for error in errors:
                    self._print_error(error)
                return False

            self._print_success(f"✅ Created ticket under {epic}")
            return True

        except Exception as e:
            self._print_error(f"Failed to create ticket: {e}")
            return False

    def _create_epic_from_scope(self, scope, project=None):
        """Create an execution plan from scope."""
        from .models import ExecutionPlan

        plan = ExecutionPlan()

        # Determine project
        if not project:
            project = list(self.config.projects.keys())[0]

        # Add epic creation
        plan.creations.append({
            "type": "ticket",
            "project": project,
            "summary": scope.title,
            "description": scope.description,
            "points": scope.estimated_points,
        })

        # Add sub-items
        for sub in scope.sub_items:
            if sub.type == "ticket":
                plan.creations.append({
                    "type": "ticket",
                    "project": project,
                    "summary": sub.title,
                    "description": sub.description,
                    "points": sub.estimated_points,
                })

        return plan

    def _detect_ticket_from_git(self) -> Optional[str]:
        """Detect ticket from git branch."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                branch = result.stdout.strip()
                ticket = self.pr_linker.detect_ticket_from_branch(branch)
                if ticket:
                    return ticket
        except:
            pass

        return None

    def _confirm_callback(self, message: str) -> bool:
        """Ask user for confirmation."""
        response = input(f"\n{message}\nProceed? [y/n]: ").strip().lower()
        return response == "y"

    # Output helpers
    def _print_success(self, msg: str):
        """Print success message."""
        print(f"\033[92m{msg}\033[0m")

    def _print_error(self, msg: str):
        """Print error message."""
        print(f"\033[91m{msg}\033[0m", file=sys.stderr)

    def _print_warning(self, msg: str):
        """Print warning message."""
        print(f"\033[93m{msg}\033[0m")

    def _print_info(self, msg: str):
        """Print info message."""
        print(f"{msg}")

    def _print_json(self, obj):
        """Print JSON."""
        print(json.dumps(obj, indent=2))


def main():
    """Main CLI entry point."""
    import argparse
    from . import __version__

    cli = JiraSkillCLI()

    parser = argparse.ArgumentParser(description="Jira Skill - Intelligent Jira management")
    parser.add_argument("--version", action="version", version=f"Jira Skill {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # config commands
    config_parser = subparsers.add_parser("config", help="Configuration commands")
    config_subs = config_parser.add_subparsers(dest="config_command")
    config_subs.add_parser("init", help="Initialize master config")
    config_subs.add_parser("show", help="Show resolved config")

    # jira commands
    subparsers.add_parser("config-show", help="Show resolved config")
    subparsers.add_parser("config-init", help="Initialize config")

    epic_parser = subparsers.add_parser("new-epic", help="Create epic from requirement")
    epic_parser.add_argument("requirement", help="Requirement description")
    epic_parser.add_argument("--project", help="Project key")
    epic_parser.add_argument("--auto-approve", action="store_true")

    pr_parser = subparsers.add_parser("link-pr", help="Link PR to ticket")
    pr_parser.add_argument("url", help="PR URL")
    pr_parser.add_argument("--ticket", help="Ticket key")
    pr_parser.add_argument("--auto", action="store_true")

    audit_parser = subparsers.add_parser("audit", help="Audit code vs tickets")
    audit_parser.add_argument("project", help="Project key")
    audit_parser.add_argument("--since", type=int, default=7, help="Days back")
    audit_parser.add_argument("--fix", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show project status")
    status_parser.add_argument("project", help="Project key")

    stale_parser = subparsers.add_parser("list-stale", help="List stale tickets")
    stale_parser.add_argument("project", help="Project key")
    stale_parser.add_argument("--days", type=int, default=14)

    reassign_parser = subparsers.add_parser("reassign", help="Reassign ticket")
    reassign_parser.add_argument("ticket", help="Ticket key")
    reassign_parser.add_argument("assignee", help="Assignee username")

    show_parser = subparsers.add_parser("show", help="Show ticket details")
    show_parser.add_argument("ticket", help="Ticket key")

    move_parser = subparsers.add_parser("move-to-epic", help="Move ticket to epic")
    move_parser.add_argument("ticket", help="Ticket key")
    move_parser.add_argument("epic", help="Epic key")
    move_parser.add_argument("--auto-approve", action="store_true")

    comment_parser = subparsers.add_parser("add-comment", help="Add comment to ticket")
    comment_parser.add_argument("ticket", help="Ticket key")
    comment_parser.add_argument("message", help="Comment message")

    blockers_parser = subparsers.add_parser("find-blockers", help="Find blocked tickets")
    blockers_parser.add_argument("project", help="Project key")

    estimate_parser = subparsers.add_parser("estimate-epic", help="Estimate epic completion")
    estimate_parser.add_argument("epic", help="Epic key")

    consolidate_parser = subparsers.add_parser("suggest-consolidation", help="Suggest consolidation")
    consolidate_parser.add_argument("project", help="Project key")

    list_epics_parser = subparsers.add_parser("list-epics", help="List all epics")
    list_epics_parser.add_argument("project", help="Project key")

    epic_info_parser = subparsers.add_parser("epic-info", help="Show epic with all tickets")
    epic_info_parser.add_argument("epic", help="Epic key")

    quick_create_parser = subparsers.add_parser("quick-create", help="Create single ticket")
    quick_create_parser.add_argument("project", help="Project key")
    quick_create_parser.add_argument("summary", help="Ticket summary")
    quick_create_parser.add_argument("--points", type=int, default=3, help="Story points")

    subtask_parser = subparsers.add_parser("create-subtask", help="Create subtask")
    subtask_parser.add_argument("parent", help="Parent ticket key")
    subtask_parser.add_argument("summary", help="Subtask summary")
    subtask_parser.add_argument("--points", type=int, default=1, help="Story points")

    transition_parser = subparsers.add_parser("transition", help="Change ticket status")
    transition_parser.add_argument("ticket", help="Ticket key")
    transition_parser.add_argument("status", help="Target status")
    transition_parser.add_argument("--auto-approve", action="store_true")

    scope_creep_parser = subparsers.add_parser("detect-scope-creep", help="Find scope creep")
    scope_creep_parser.add_argument("project", help="Project key")

    risk_parser = subparsers.add_parser("risk-assessment", help="Epic risk analysis")
    risk_parser.add_argument("epic", help="Epic key")

    decompose_parser = subparsers.add_parser("decompose-preview", help="Preview decomposition")
    decompose_parser.add_argument("requirement", help="Requirement text")

    merge_parser = subparsers.add_parser("handle-pr-merge", help="Handle PR merge")
    merge_parser.add_argument("ticket", help="Ticket key")
    merge_parser.add_argument("--auto-approve", action="store_true")

    create_in_epic_parser = subparsers.add_parser("create-ticket-in-epic", help="Create ticket in epic")
    create_in_epic_parser.add_argument("project", help="Project key")
    create_in_epic_parser.add_argument("epic", help="Epic key")
    create_in_epic_parser.add_argument("summary", help="Ticket summary")
    create_in_epic_parser.add_argument("--points", type=int, default=3, help="Story points")

    args = parser.parse_args()

    # Route commands
    if args.command == "config":
        if args.config_command == "init":
            return cli.cmd_config_init()
        elif args.config_command == "show":
            return cli.cmd_config_show()
    elif args.command == "config-init":
        return cli.cmd_config_init()
    elif args.command == "config-show":
        return cli.cmd_config_show()
    elif args.command == "new-epic":
        return cli.cmd_new_epic(args.requirement, args.project, args.auto_approve)
    elif args.command == "link-pr":
        return cli.cmd_link_pr(args.url, args.ticket, args.auto)
    elif args.command == "audit":
        return cli.cmd_audit(args.project, args.since, args.fix)
    elif args.command == "status":
        return cli.cmd_status(args.project)
    elif args.command == "list-stale":
        return cli.cmd_list_stale(args.project, args.days)
    elif args.command == "reassign":
        return cli.cmd_reassign(args.ticket, args.assignee)
    elif args.command == "show":
        return cli.cmd_show_ticket(args.ticket)
    elif args.command == "move-to-epic":
        return cli.cmd_move_to_epic(args.ticket, args.epic, args.auto_approve)
    elif args.command == "add-comment":
        return cli.cmd_add_comment(args.ticket, args.message)
    elif args.command == "find-blockers":
        return cli.cmd_find_blockers(args.project)
    elif args.command == "estimate-epic":
        return cli.cmd_estimate_epic(args.epic)
    elif args.command == "suggest-consolidation":
        return cli.cmd_suggest_consolidation(args.project)
    elif args.command == "list-epics":
        return cli.cmd_list_epics(args.project)
    elif args.command == "epic-info":
        return cli.cmd_epic_info(args.epic)
    elif args.command == "quick-create":
        return cli.cmd_quick_create(args.project, args.summary, args.points)
    elif args.command == "create-subtask":
        return cli.cmd_create_subtask(args.parent, args.summary, args.points)
    elif args.command == "transition":
        return cli.cmd_transition(args.ticket, args.status, args.auto_approve)
    elif args.command == "detect-scope-creep":
        return cli.cmd_detect_scope_creep(args.project)
    elif args.command == "risk-assessment":
        return cli.cmd_risk_assessment(args.epic)
    elif args.command == "decompose-preview":
        return cli.cmd_decompose_preview(args.requirement)
    elif args.command == "handle-pr-merge":
        return cli.cmd_handle_pr_merge(args.ticket, args.auto_approve)
    elif args.command == "create-ticket-in-epic":
        return cli.cmd_create_ticket_in_epic(args.project, args.epic, args.summary, args.points)
    else:
        parser.print_help()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
