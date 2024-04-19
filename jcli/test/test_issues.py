from click.testing import CliRunner
from jcli.issues import list_cmd
from jcli.test.stubs import JiraConnectorStub
import pytest
import random
from unittest.mock import patch


@pytest.fixture
def cli_runner():
    return CliRunner()


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_list_cmd_no_args(cli_runner):
    # Add some fake issues
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(1, 100)):
        JiraConnectorStub.setup_add_random_issue()

    result = cli_runner.invoke(list_cmd)
    assert result.exit_code == 0
    assert result.output != ''

    assert JiraConnectorStub._last_jql == 'assignee = "None" AND status not in ("Closed","Done")'

    lines = result.output.split("\n")
    assert lines[0] == "+----------------+-----------+------------+-------------------------------------------------+----------+------------+"
    assert lines[1] == "| key            | project   | priority   | summary                                         | status   | assignee   |"
    assert lines[2] == "|----------------+-----------+------------+-------------------------------------------------+----------+------------|"


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_list_cmd_with_assignee(cli_runner):
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(1, 100)):
        JiraConnectorStub.setup_add_random_issue()
    result = cli_runner.invoke(list_cmd, ['--assignee', 'a@a.com'])

    assert JiraConnectorStub._last_jql == 'assignee = "a@a.com" AND status not in ("Closed","Done")'
    assert result.exit_code == 0
