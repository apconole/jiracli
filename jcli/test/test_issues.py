from click.testing import CliRunner
from jcli.issues import list_cmd
from jcli.issues import add_comment_cmd
from jcli.issues import create_issue_cmd
from jcli.test.stubs import JiraConnectorStub
import json
import pytest
import random
import re
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
    assert lines[0] == "+----------------+-----------+------------+-------------------------------------------------+-------------+------------+"
    assert lines[1] == "| key            | project   | priority   | summary                                         | status      | assignee   |"
    assert lines[2] == "|----------------+-----------+------------+-------------------------------------------------+-------------+------------|"


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_list_cmd_with_assignee(cli_runner):
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(1, 100)):
        JiraConnectorStub.setup_add_random_issue()
    result = cli_runner.invoke(list_cmd, ['--assignee', 'a@a.com'])

    assert JiraConnectorStub._last_jql == 'assignee = "a@a.com" AND status not in ("Closed","Done")'
    assert result.exit_code == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_list_cmd_json(cli_runner):
    JiraConnectorStub.setup_clear_issues()
    for _ in range(random.randint(1, 100)):
        JiraConnectorStub.setup_add_random_issue()
    result = cli_runner.invoke(list_cmd, ['--output', 'json'])
    assert result.exit_code == 0

    json_obj = json.loads(result.output)
    assert "field_maps" in json_obj
    assert "issues" in json_obj
    assert "issues_count" in json_obj


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_jira_to_md_and_back(cli_runner):

    comment_jira = """
In comment foo at [this|https://issue.test.com/browse/PROJMAIN-123?focusedId=12345678&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-12345678], we see that there is a problem.
h1. Define the problem:
* Put your right foot in.
* Put your right foot out.
* Notice that [~a@a.com] did not do the hokey pokey before turning about.
The spec requires that
{noformat}
Doing the hokey pokey always preceeds turning yourself about.

This is not an optional prerequisite.
{noformat}
Looking at the code, we see::
{code:java}
if (hokey)
    self.turn_about()
{code}
However, the hokey flag never seems to have gotten cleared.
I pulled the details from [here|https://www.example.com/hokey-pokey-spec/2025/01/01/spec.txt] and the pdf [here|ftp://www.example.com/hokey-pokey-spec/2025/01/01/spec.pdf]
"""

    md_ref = """
In comment foo at [this](PROJMAIN-123#12345678), we see that there is a problem.
# Define the problem:
- Put your right foot in.
- Put your right foot out.
- Notice that [~a@a.com] did not do the hokey pokey before turning about.
The spec requires that
> Doing the hokey pokey always preceeds turning yourself about.
>
> This is not an optional prerequisite.
Looking at the code, we see::
```java
if (hokey)
    self.turn_about()

```
However, the hokey flag never seems to have gotten cleared.
I pulled the details from [here](https://www.example.com/hokey-pokey-spec/2025/01/01/spec.txt) and the pdf [here](ftp://www.example.com/hokey-pokey-spec/2025/01/01/spec.pdf)
"""

    t = JiraConnectorStub()

    txt = t.jira_text_field_to_md(comment_jira)
    print(txt)
    assert re.sub(r"^> $", ">", txt, flags=re.MULTILINE) == re.sub(
        r"^> $", ">", md_ref, flags=re.MULTILINE
    )

    back = t.md_text_to_jira_text_field(txt)
    print(back)
    assert re.sub(r"^> $", ">", back, flags=re.MULTILINE) == re.sub(
        r"^> $", ">", comment_jira, flags=re.MULTILINE
    )


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_reply_to_cmd(cli_runner):
    JiraConnectorStub.setup_clear_issues()
    s = JiraConnectorStub()
    for _ in range(random.randint(1, 100)):
        JiraConnectorStub.setup_add_random_issue()

    for issue in s._query_issues("", 0, 10):
        s.add_comment(issue["key"], "Test string rand", {})

    for issue in s._query_issues("", 0, 10):
        result = cli_runner.invoke(add_comment_cmd, [issue['key'],
                                                     '--comment', 'Something',
                                                     '--in-reply-to', '12345'])
        assert result.exit_code == 1

        # get a comment and really try the reply
        cid = issue.fields.comment.comments[0].id

        with patch("subprocess.run") as mock_run:
            result = cli_runner.invoke(add_comment_cmd, [issue['key'],
                                                         '--in-reply-to', cid],
                                       env={"EDITOR": 'vim'})
            assert 'vim' == mock_run.call_args_list[0][0][0][0]
            assert result.stdout_bytes == b'Error: No comment provided.\n'
            assert result.exit_code == 1


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_create(cli_runner):
    JiraConnectorStub.setup_clear_issues()

    result = cli_runner.invoke(create_issue_cmd, obj={})
    assert result.exit_code == 1
    assert "Please fill in project, summary, and description." in result.output

    issue_summary = "Testing an issue create"
    issue_description = "Describe an issue here.  This can be multiline."
    issue_project = "ABC"

    result = cli_runner.invoke(create_issue_cmd,
                               ['--summary', issue_summary,
                                '--description', issue_description,
                                '--project', issue_project,
                                '--issue-type', 'Bug'], obj={})
    assert result.exit_code == 0
    assert "done - Result: " in result.output
