from click.testing import CliRunner
from jcli.query import list_all_cmd
from jcli.query import run_cmd
from jcli.query import build_cmd
from jcli.query import remove_cmd
from jcli.test.stubs import JiraConnectorStub
import pytest
import random
from unittest.mock import patch


@pytest.fixture
def cli_runner():
    return CliRunner()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_list_all_no_queries(cli_runner):
    """Test list-all when no saved queries exist."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()

    result = cli_runner.invoke(list_all_cmd)
    assert result.exit_code == 0
    assert "No saved queries found." in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_list_all_with_queries(cli_runner):
    """Test list-all when saved queries exist."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()
    JiraConnectorStub.config['jira']['saved_queries'] = {
        'my-bugs': {
            'description': 'All open bugs assigned to me',
            'jql': 'assignee = currentUser() AND type = Bug'
        },
        'team-blockers': {
            'description': 'Critical blockers',
            'jql': 'priority = Critical AND status != Done'
        }
    }

    result = cli_runner.invoke(list_all_cmd)
    assert result.exit_code == 0
    assert 'my-bugs' in result.output
    assert 'team-blockers' in result.output
    assert 'All open bugs assigned to me' in result.output
    assert 'Critical blockers' in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_run_missing_query(cli_runner):
    """Test run with a query name that doesn't exist."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()

    result = cli_runner.invoke(run_cmd, ['nonexistent'])
    assert result.exit_code != 0
    assert "not found" in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_run_query(cli_runner):
    """Test run executes the saved JQL and displays results."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()
    for _ in range(random.randint(1, 10)):
        JiraConnectorStub.setup_add_random_issue()

    JiraConnectorStub.config['jira']['saved_queries'] = {
        'test-query': {
            'description': 'A test query',
            'jql': 'project = TEST AND status != Done'
        }
    }

    result = cli_runner.invoke(run_cmd, ['test-query'])
    assert result.exit_code == 0
    assert JiraConnectorStub._last_jql == 'project = TEST AND status != Done'
    # Should have table output with headers
    assert 'key' in result.output
    assert 'summary' in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_run_query_json_output(cli_runner):
    """Test run with JSON output format."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()
    for _ in range(3):
        JiraConnectorStub.setup_add_random_issue()

    JiraConnectorStub.config['jira']['saved_queries'] = {
        'test-json': {
            'jql': 'project = TEST'
        }
    }

    result = cli_runner.invoke(run_cmd, ['test-json', '--output', 'json'])
    assert result.exit_code == 0
    assert 'issues_count' in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_run_query_no_jql(cli_runner):
    """Test run with a query that has no JQL defined."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()
    JiraConnectorStub.config['jira']['saved_queries'] = {
        'empty': {
            'description': 'No JQL here'
        }
    }

    result = cli_runner.invoke(run_cmd, ['empty'])
    assert result.exit_code != 0
    assert "no JQL defined" in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_build_saves_query(cli_runner):
    """Test build constructs JQL and saves to config."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()

    result = cli_runner.invoke(build_cmd, [
        '--name', 'my-new-query',
        '--description', 'Testing build',
        '--project', 'MYPROJ'
    ])
    assert result.exit_code == 0
    assert "Saved query 'my-new-query'" in result.output

    saved = JiraConnectorStub.config['jira']['saved_queries']['my-new-query']
    assert 'jql' in saved
    assert 'MYPROJ' in saved['jql']
    assert saved['description'] == 'Testing build'


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_build_with_matching_options(cli_runner):
    """Test build with custom matching options."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()

    result = cli_runner.invoke(build_cmd, [
        '--name', 'custom-match',
        '--matching-eq', 'priority', 'Critical',
        '--matching-neq', 'status', 'Done'
    ])
    assert result.exit_code == 0

    saved = JiraConnectorStub.config['jira']['saved_queries']['custom-match']
    assert 'priority = Critical' in saved['jql']
    assert 'status != Done' in saved['jql']


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_build_no_description(cli_runner):
    """Test build without a description omits it from config."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()

    result = cli_runner.invoke(build_cmd, [
        '--name', 'no-desc',
        '--project', 'TEST'
    ])
    assert result.exit_code == 0

    saved = JiraConnectorStub.config['jira']['saved_queries']['no-desc']
    assert 'description' not in saved


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_remove_existing_query(cli_runner):
    """Test remove deletes a saved query."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()
    JiraConnectorStub.config['jira']['saved_queries'] = {
        'to-delete': {
            'description': 'Will be removed',
            'jql': 'project = TEST'
        },
        'to-keep': {
            'description': 'Should remain',
            'jql': 'project = OTHER'
        }
    }

    result = cli_runner.invoke(remove_cmd, ['to-delete'])
    assert result.exit_code == 0
    assert "Removed saved query 'to-delete'" in result.output

    # Verify it was removed
    assert 'to-delete' not in JiraConnectorStub.config['jira']['saved_queries']
    # Verify the other query remains
    assert 'to-keep' in JiraConnectorStub.config['jira']['saved_queries']


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_remove_nonexistent_query(cli_runner):
    """Test remove with a query name that doesn't exist."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()

    result = cli_runner.invoke(remove_cmd, ['nonexistent'])
    assert result.exit_code != 0
    assert "not found" in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_build_then_list_then_run_then_remove(cli_runner):
    """Test full lifecycle: build, list, run, remove."""
    JiraConnectorStub.setup_clear_issues()
    JiraConnectorStub.reset_config()
    for _ in range(5):
        JiraConnectorStub.setup_add_random_issue()

    # Build a query
    result = cli_runner.invoke(build_cmd, [
        '--name', 'lifecycle-test',
        '--description', 'Full lifecycle',
        '--project', 'TEST'
    ])
    assert result.exit_code == 0

    # List should show it
    result = cli_runner.invoke(list_all_cmd)
    assert result.exit_code == 0
    assert 'lifecycle-test' in result.output
    assert 'Full lifecycle' in result.output

    # Run it
    result = cli_runner.invoke(run_cmd, ['lifecycle-test'])
    assert result.exit_code == 0
    assert 'TEST' in JiraConnectorStub._last_jql

    # Remove it
    result = cli_runner.invoke(remove_cmd, ['lifecycle-test'])
    assert result.exit_code == 0

    # List should no longer show it
    result = cli_runner.invoke(list_all_cmd)
    assert result.exit_code == 0
    assert 'lifecycle-test' not in result.output
