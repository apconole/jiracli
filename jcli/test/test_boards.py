from click.testing import CliRunner
from jcli.boards import list_cmd
from jcli.boards import show_cmd
from jcli.boards import get_config_cmd
from jcli.boards import sprints_cmd
from jcli.boards import create_sprint_cmd
from jcli.test.stubs import JiraConnectorStub
import json
import pytest
import random
from unittest.mock import patch


@pytest.fixture
def cli_runner():
    return CliRunner()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_list_boards_default_limit(cli_runner):
    """Test listing boards with default limit"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(list_cmd)
    assert result.exit_code == 0
    assert result.output != ''

    # Check for table headers
    lines = result.output.split("\n")
    assert "name" in lines[1].lower()
    assert "type" in lines[1].lower()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_list_boards_custom_limit(cli_runner):
    """Test listing boards with custom limit"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(list_cmd, ['--limit', '3'])
    assert result.exit_code == 0
    assert result.output != ''


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_show_board_basic(cli_runner):
    """Test showing a basic board"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(show_cmd, ['Sprint Board'])
    assert result.exit_code == 0
    assert result.output != ''

    # Check for column headers
    assert "To Do" in result.output or "In Progress" in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_show_board_with_assignee_filter(cli_runner):
    """Test showing a board filtered by assignee"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(show_cmd, ['Sprint Board', '--assignee', 'a@a.com'])
    assert result.exit_code == 0
    assert result.output != ''


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_show_board_with_project_filter(cli_runner):
    """Test showing a board filtered by project"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(show_cmd, ['Sprint Board', '--project', 'TEST'])
    assert result.exit_code == 0
    assert result.output != ''


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_show_board_with_quick_filter(cli_runner):
    """Test showing a board with quick filter applied"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(show_cmd, ['Sprint Board', '--filter', 'My Issues'])
    assert result.exit_code == 0
    assert result.output != ''


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_show_board_with_summary(cli_runner):
    """Test showing a board with summary included"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(show_cmd, ['Sprint Board', '--summary-len', '50'])
    assert result.exit_code == 0
    assert result.output != ''


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_show_board_with_issue_pagination(cli_runner):
    """Test showing a board with issue offset and max"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(show_cmd,
                               ['Sprint Board',
                                '--issue-offset', '10',
                                '--max-issues', '50'])
    assert result.exit_code == 0
    assert result.output != ''


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_get_config_basic(cli_runner):
    """Test getting board configuration"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(get_config_cmd, ['Sprint Board'])
    assert result.exit_code == 0
    assert result.output != ''

    # Should contain filter and column information
    assert "filter" in result.output.lower() or "column" in result.output.lower()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_get_config_with_quickfilters(cli_runner):
    """Test getting board configuration with quick filters"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(get_config_cmd, ['Sprint Board'])
    assert result.exit_code == 0

    # Should contain quickfilter information
    assert "quickfilter" in result.output.lower()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_sprints_show_active_only(cli_runner):
    """Test showing only active sprints (default)"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(sprints_cmd, ['Sprint Board'])
    assert result.exit_code == 0
    assert result.output != ''

    # Should contain sprint information
    assert "Sprint" in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_sprints_show_all(cli_runner):
    """Test showing all sprints including closed ones"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(sprints_cmd, ['Sprint Board', '--show-all'])
    assert result.exit_code == 0
    assert result.output != ''


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_sprints_filter_by_name(cli_runner):
    """Test showing a specific sprint by name"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(sprints_cmd, ['Sprint Board', '--name', 'Sprint 1'])
    assert result.exit_code == 0
    assert result.output != ''
    assert "Sprint 1" in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_sprints_my_issues_only(cli_runner):
    """Test showing only issues assigned to me in sprints"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(sprints_cmd, ['Sprint Board', '--my-issues'])
    assert result.exit_code == 0
    assert result.output != ''


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_sprints_no_issues(cli_runner):
    """Test showing sprints without querying issues"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(sprints_cmd, ['Sprint Board', '--no-issues'])
    assert result.exit_code == 0
    assert result.output != ''

    # Should contain sprint information but not issue columns
    assert "Sprint" in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_sprints_json_output(cli_runner):
    """Test sprints output in JSON format"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(sprints_cmd, ['Sprint Board', '--json'])
    assert result.exit_code == 0
    assert result.output != ''

    # Parse JSON and verify structure
    json_obj = json.loads(result.output)
    assert isinstance(json_obj, list)

    if len(json_obj) > 0:
        sprint = json_obj[0]
        assert "name" in sprint
        assert "id" in sprint
        assert "columns" in sprint


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_sprints_json_with_my_issues(cli_runner):
    """Test sprints JSON output with my-issues filter"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(5, 20)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(sprints_cmd,
                               ['Sprint Board', '--json', '--my-issues'])
    assert result.exit_code == 0

    json_obj = json.loads(result.output)
    assert isinstance(json_obj, list)


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_create_sprint_basic(cli_runner):
    """Test creating a basic sprint"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(create_sprint_cmd,
                               ['Sprint Board', 'New Sprint'])
    assert result.exit_code == 0
    assert "created" in result.output.lower()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_create_sprint_with_dates(cli_runner):
    """Test creating a sprint with start and end dates"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(create_sprint_cmd,
                               ['Sprint Board', 'New Sprint',
                                '--start-date', '2025-10-15',
                                '--end-date', '2025-10-29'])
    assert result.exit_code == 0
    assert "created" in result.output.lower()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_create_sprint_with_goal(cli_runner):
    """Test creating a sprint with a goal"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(create_sprint_cmd,
                               ['Sprint Board', 'New Sprint',
                                '--goal', 'Complete feature X'])
    assert result.exit_code == 0
    assert "created" in result.output.lower()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_create_sprint_with_all_options(cli_runner):
    """Test creating a sprint with all options"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(create_sprint_cmd,
                               ['Sprint Board', 'Complete Sprint',
                                '--start-date', '2025-10-15',
                                '--end-date', '2025-10-29',
                                '--goal', 'Deliver MVP'])
    assert result.exit_code == 0
    assert "created" in result.output.lower()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_is_issue_assigned_to_helper(cli_runner):
    """Test the is_issue_assigned_to helper function"""
    from jcli.boards import is_issue_assigned_to

    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.setup_add_random_issue()

    s = JiraConnectorStub()
    issues = s._query_issues("", 0, 1)

    if len(issues) > 0:
        issue = issues[0]
        # Test with email
        if issue.fields.assignee:
            assert is_issue_assigned_to(issue, issue.fields.assignee['name'])
            # Test with display name
            assert is_issue_assigned_to(issue, issue.fields.assignee['displayName'])
            # Test case insensitivity
            assert is_issue_assigned_to(issue, issue.fields.assignee['name'].upper())


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_is_issue_in_column_helper(cli_runner):
    """Test the is_issue_in_column helper function"""
    from jcli.boards import is_issue_in_column

    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.setup_add_random_issue()

    s = JiraConnectorStub()
    issues = s._query_issues("", 0, 1)
    columns = s.fetch_column_config_by_board("Sprint Board")

    if len(issues) > 0:
        issue = issues[0]
        # Test if issue is in any column
        found_in_column = False
        for column_name, column_statuses in columns.items():
            if is_issue_in_column(issue, column_statuses, s):
                found_in_column = True
                break

        # Every issue should be in at least one column
        assert found_in_column or not hasattr(issue, 'fields')


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_show_board_empty(cli_runner):
    """Test showing a board with no issues"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(show_cmd, ['Sprint Board'])
    assert result.exit_code == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_sprints_no_matching_name(cli_runner):
    """Test sprints command with non-matching name filter"""
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(sprints_cmd,
                               ['Sprint Board', '--name', 'NonExistentSprint'])
    assert result.exit_code == 0
    # Output should be minimal/empty when no sprints match
    assert "NonExistentSprint" not in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_show_board_combined_filters(cli_runner):
    """Test showing a board with multiple filters combined"""
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(10, 30)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(show_cmd,
                               ['Sprint Board',
                                '--assignee', 'a@a.com',
                                '--project', 'TEST',
                                '--summary-len', '40',
                                '--max-issues', '20'])
    assert result.exit_code == 0
