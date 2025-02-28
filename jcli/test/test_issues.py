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


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_jira_to_md_and_back(cli_runner):
    comment_jira = "In comment foo at [this|https://issue.test.com/browse/PROJMAIN-123?focusedId=12345678&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-12345678], we see that there is a problem.\nh1. Define the problem:\n* Put your right foot in.\n* Put your right foot out.\n* Notice that [~a@a.com] did not do the hokey pokey before turning about.\nThe spec requires that\n{noformat}\nDoing the hokey pokey always preceeds turning yourself about.\nThis is not an optional prerequisite.\n{noformat}\nLooking at the code, we see::\n{code:java}\nif (hokey)\n    self.turn_about()\n{code}\nHowever, the hokey flag never seems to have gotten cleared.\nI pulled the details from [here|https://www.example.com/hokey-pokey-spec/2025/01/01/spec.txt] and the pdf [here|ftp://www.example.com/hokey-pokey-spec/2025/01/01/spec.pdf]"
    md_ref = "In comment foo at [this](PROJMAIN-123#12345678), we see that there is a problem.\n# Define the problem:\n- Put your right foot in.\n- Put your right foot out.\n- Notice that [~a@a.com] did not do the hokey pokey before turning about.\nThe spec requires that\n> Doing the hokey pokey always preceeds turning yourself about.\n> This is not an optional prerequisite.\nLooking at the code, we see::\n```java\nif (hokey)\n    self.turn_about()\n\n```\nHowever, the hokey flag never seems to have gotten cleared.\nI pulled the details from [here](https://www.example.com/hokey-pokey-spec/2025/01/01/spec.txt) and the pdf [here](ftp://www.example.com/hokey-pokey-spec/2025/01/01/spec.pdf)"

    t = JiraConnectorStub()

    txt = t.jira_text_field_to_md(comment_jira)
    assert txt == md_ref

    back = t.md_text_to_jira_text_field(txt)
    print(back)
    assert back == comment_jira
