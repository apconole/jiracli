from click.testing import CliRunner
from jcli.issues import list_cmd
from jcli.issues import add_comment_cmd
from jcli.issues import create_issue_cmd
from jcli.issues import get_field_cmd
from jcli.issues import bulk_import_cmd
from jcli.issues import _bulk_parse_file
from jcli.issues import _bulk_topo_sort
from jcli.test.stubs import JiraConnectorStub
import json
import pprint
import pytest
import random
import re
import yaml
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
However, the hokey flag never seems to have gotten cleared.  We can see from the turn_about() function that _sometimes_ it works but detect_that_we_turned_around() doesn't always work.
*important* we can verify this with a good test.
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
However, the hokey flag never seems to have gotten cleared.  We can see from the turn_about() function that *sometimes* it works but detect_that_we_turned_around() doesn't always work.
**important** we can verify this with a good test.
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
            if isinstance(mock_run.call_args_list[0][0][0], str):
                assert 'vim' == mock_run.call_args_list[0][0][0].split()[0]
            else:
                assert 'vim' == mock_run.call_args_list[0][0][0][0]
            assert result.stdout_bytes == b'Error: No comment provided.\n'
            assert result.exit_code == 1


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_editor_with_args(cli_runner):
    JiraConnectorStub.setup_clear_issues()
    s = JiraConnectorStub()
    for _ in range(random.randint(1, 100)):
        JiraConnectorStub.setup_add_random_issue()

    for issue in s._query_issues("", 0, 10):
        with patch("subprocess.run") as mock_run:
            result = cli_runner.invoke(add_comment_cmd, [issue['key']],
                                       env={"EDITOR": 'vim -d --noplugin'})

            if isinstance(mock_run.call_args_list[0][0][0], str):
                result_str = mock_run.call_args_list[0][0][0]
            else:
                result_str = mock_run.call_args_list[0][0][0][0]

            assert 'vim' == result_str.split()[0]
            assert '-d' == result_str.split()[1]
            assert '--noplugin' == result_str.split()[2]
            assert result.stdout_bytes == b'Error: No comment provided.\n'
            assert result.exit_code == 1


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_create(cli_runner, tmpdir):
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

    # Now test with set-commands
    issue_project = "DEF"
    result = cli_runner.invoke(create_issue_cmd,
                               ['--verbose',
                                '--summary', issue_summary,
                                '--description', issue_description,
                                '--project', issue_project,
                                '--issue-type', 'Bug',
                                '--set-field', 'priority', 'Medium',
                                '--set-field', 'duedate', '2025-07-15'], obj={})
    assert result.exit_code == 0
    assert JiraConnectorStub.last_issue is not None
    print(result.output)
    print(f"Issue: {pprint.pformat(JiraConnectorStub.last_issue)}")
    assert 'priority' in JiraConnectorStub.last_issue
    assert 'duedate' in JiraConnectorStub.last_issue

    # Now test 'forced' flag
    issue_set_text = f"""# Starting an issue
{issue_summary} - from file.

DESC: {issue_description}

# set-project: {issue_project}
# issue-type: Bug
# set-field: --forced "priority" int(1234)
# set-field: "duedate" 2025-07-15
"""
    f = tmpdir.join("issue_txt")
    f.write(issue_set_text)
    cli_runner.invoke(create_issue_cmd,
                      ['--verbose',
                       '--from-file', str(f)],
                      obj={})
    assert result.exit_code == 0
    assert JiraConnectorStub.last_issue is not None
    assert 'priority' in JiraConnectorStub.last_issue
    assert JiraConnectorStub.last_issue['priority'] == 1234


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_create_json(cli_runner):
    JiraConnectorStub.setup_clear_issues()

    issue_summary = "JSON output test"
    issue_description = "Testing JSON output for create."
    issue_project = "ABC"

    result = cli_runner.invoke(create_issue_cmd,
                               ['--json',
                                '--summary', issue_summary,
                                '--description', issue_description,
                                '--project', issue_project,
                                '--issue-type', 'Bug'], obj={})
    assert result.exit_code == 0
    json_obj = json.loads(result.output)
    assert 'fields' in json_obj
    assert json_obj['fields']['summary'] == issue_summary


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_case_cmp(cli_runner):
    JiraConnectorStub.setup_clear_issues()

    s = JiraConnectorStub()
    for _ in range(random.randint(1, 100)):
        JiraConnectorStub.setup_add_random_issue()

    issue = random.choice(s._query_issues("", 0, 100))
    # First - ensure that case matters
    result = cli_runner.invoke(get_field_cmd,
                               [issue['key'],
                                'component'], obj={})

    print(result.output)
    assert result.exit_code == 0
    assert "component: \n" in result.output

    # Check that the case does match
    result = cli_runner.invoke(get_field_cmd,
                               [issue['key'],
                                'Component'], obj={})
    assert result.exit_code == 0
    assert "Component: component\n" in result.output

    # Now 'force' case insensitive
    cfg = JiraConnectorStub.config
    cfg['jira']['default']['case_sensitive'] = False
    JiraConnectorStub.reset_config(cfg)

    result = cli_runner.invoke(get_field_cmd,
                               [issue['key'],
                                'component'], obj={})

    assert result.exit_code == 0
    assert "component: component\n" in result.output


# ---------------------------------------------------------------------------
# _bulk_parse_file tests
# ---------------------------------------------------------------------------

def test_bulk_parse_file_yaml(tmp_path):
    data = {'issues': [{'id': 'a', 'summary': 'Foo'}]}
    f = tmp_path / 'import.yaml'
    f.write_text(yaml.dump(data))
    assert _bulk_parse_file(str(f)) == data


def test_bulk_parse_file_json(tmp_path):
    data = {'issues': [{'id': 'a', 'summary': 'Foo'}]}
    f = tmp_path / 'import.json'
    f.write_text(json.dumps(data))
    assert _bulk_parse_file(str(f)) == data


# ---------------------------------------------------------------------------
# _bulk_topo_sort tests
# ---------------------------------------------------------------------------

def test_topo_sort_no_deps():
    issues = [
        {'id': 'a', 'summary': 'A'},
        {'id': 'b', 'summary': 'B'},
    ]
    result = _bulk_topo_sort(issues)
    assert len(result) == 2
    assert {i['id'] for i in result} == {'a', 'b'}


def test_topo_sort_respects_dependency():
    # b depends on a → a must come first
    issues = [
        {'id': 'b', 'summary': 'B', 'links': [{'target': 'a'}]},
        {'id': 'a', 'summary': 'A'},
    ]
    result = _bulk_topo_sort(issues)
    ids = [i['id'] for i in result]
    assert ids.index('a') < ids.index('b')


def test_topo_sort_chain():
    # c depends on b, b depends on a → order must be a, b, c
    issues = [
        {'id': 'c', 'summary': 'C', 'links': [{'target': 'b'}]},
        {'id': 'b', 'summary': 'B', 'links': [{'target': 'a'}]},
        {'id': 'a', 'summary': 'A'},
    ]
    result = _bulk_topo_sort(issues)
    ids = [i['id'] for i in result]
    assert ids.index('a') < ids.index('b')
    assert ids.index('b') < ids.index('c')


def test_topo_sort_external_key_not_treated_as_dep():
    # PROJ-99 is a real Jira key, not a local alias → no ordering constraint
    issues = [
        {'id': 'a', 'summary': 'A', 'links': [{'target': 'PROJ-99'}]},
        {'id': 'b', 'summary': 'B'},
    ]
    result = _bulk_topo_sort(issues)
    assert len(result) == 2


def test_topo_sort_cycle_raises():
    issues = [
        {'id': 'a', 'summary': 'A', 'links': [{'target': 'b'}]},
        {'id': 'b', 'summary': 'B', 'links': [{'target': 'a'}]},
    ]
    import click
    with pytest.raises(click.UsageError, match="Cycle"):
        _bulk_topo_sort(issues)


def test_topo_sort_no_id_issues():
    # Issues without 'id' have no local deps and should sort fine
    issues = [
        {'summary': 'No-id issue 1'},
        {'summary': 'No-id issue 2'},
    ]
    result = _bulk_topo_sort(issues)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# bulk_import_cmd integration tests (via CliRunner + JiraConnectorStub)
# ---------------------------------------------------------------------------

@pytest.fixture
def bulk_yaml(tmp_path):
    """Write a two-issue YAML file and return its path."""
    def _make(issues):
        f = tmp_path / 'bulk.yaml'
        f.write_text(yaml.dump({'issues': issues}))
        return str(f)
    return _make


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_dry_run(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'spike', 'summary': 'Spike', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Story'},
    ])
    result = cli_runner.invoke(bulk_import_cmd, ['--dry-run', path], obj={})
    assert result.exit_code == 0
    assert '[DRY-RUN]' in result.output
    # No real issues created
    assert len(JiraConnectorStub._created_issues) == 0
    assert len(JiraConnectorStub._issue_links) == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_creates_issues(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'Issue A', 'description': 'Desc A',
         'project': 'PROJ', 'issue_type': 'Bug'},
        {'id': 'b', 'summary': 'Issue B', 'description': 'Desc B',
         'project': 'PROJ', 'issue_type': 'Story'},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    assert len(JiraConnectorStub._created_issues) == 2
    summaries = [i['summary'] for i in JiraConnectorStub._created_issues]
    assert 'Issue A' in summaries
    assert 'Issue B' in summaries


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_dependency_order(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    # b depends on a via local alias → a must be created first
    path = bulk_yaml([
        {'id': 'b', 'summary': 'Issue B', 'description': 'B desc',
         'project': 'PROJ', 'issue_type': 'Bug',
         'links': [{'link_type': 'Depends', 'direction': 'outward', 'target': 'a'}]},
        {'id': 'a', 'summary': 'Issue A', 'description': 'A desc',
         'project': 'PROJ', 'issue_type': 'Bug'},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    summaries = [i['summary'] for i in JiraConnectorStub._created_issues]
    assert summaries.index('Issue A') < summaries.index('Issue B')


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_links_resolved(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'alpha', 'summary': 'Alpha', 'description': 'Alpha desc',
         'project': 'PROJ', 'issue_type': 'Bug'},
        {'id': 'beta', 'summary': 'Beta', 'description': 'Beta desc',
         'project': 'PROJ', 'issue_type': 'Bug',
         'links': [{'link_type': 'Depends', 'direction': 'outward',
                    'target': 'alpha'}]},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    assert len(JiraConnectorStub._issue_links) == 1
    link = JiraConnectorStub._issue_links[0]
    # source is the real key of 'beta', target is the real key of 'alpha'
    assert link['link_type'] == 'Depends'
    assert link['isinward'] is False
    # The target must be a real Jira key (not the alias 'alpha')
    assert link['target'] != 'alpha'
    assert link['target'].startswith('ISSUE-')


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_link_to_existing_issue(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    # Seed an existing issue
    JiraConnectorStub.setup_add_random_issue()
    existing_key = JiraConnectorStub._issues_list[0]['key']

    path = bulk_yaml([
        {'id': 'new', 'summary': 'New issue', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug',
         'links': [{'link_type': 'Relates', 'direction': 'outward',
                    'target': existing_key}]},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    assert len(JiraConnectorStub._issue_links) == 1
    assert JiraConnectorStub._issue_links[0]['target'] == existing_key


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_link_inward_direction(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'x', 'summary': 'X', 'description': 'Desc X',
         'project': 'PROJ', 'issue_type': 'Bug'},
        {'id': 'y', 'summary': 'Y', 'description': 'Desc Y',
         'project': 'PROJ', 'issue_type': 'Bug',
         'links': [{'link_type': 'Blocks', 'direction': 'inward',
                    'target': 'x'}]},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    link = JiraConnectorStub._issue_links[0]
    assert link['link_type'] == 'Blocks'
    assert link['isinward'] is True


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_missing_link_type_warns(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug'},
        {'id': 'b', 'summary': 'B', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug',
         'links': [{'direction': 'outward', 'target': 'a'}]},  # no link_type
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    assert 'WARNING' in result.output
    # No link should have been created
    assert len(JiraConnectorStub._issue_links) == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_empty_file(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    assert 'No issues found' in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_default_project_and_type(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    # Issues with no project/issue_type should pick up the CLI defaults
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc A'},
    ])
    result = cli_runner.invoke(
        bulk_import_cmd,
        ['--project', 'PROJ', '--issue-type', 'Task', path],
        obj={})
    assert result.exit_code == 0
    assert JiraConnectorStub._created_issues[0]['project'] == 'PROJ'
    assert JiraConnectorStub._created_issues[0]['issuetype'] == 'Task'


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_custom_fields(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Story',
         'fields': {'story_points': '5', 'priority': 'High'}},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    created = JiraConnectorStub._created_issues[0]
    assert created['story_points'] == '5'
    assert created['priority'] == 'High'


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_bulk_import_dry_run_links_not_created(cli_runner, bulk_yaml):
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug'},
        {'id': 'b', 'summary': 'B', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug',
         'links': [{'link_type': 'Depends', 'direction': 'outward',
                    'target': 'a'}]},
    ])
    result = cli_runner.invoke(bulk_import_cmd, ['--dry-run', path], obj={})
    assert result.exit_code == 0
    assert len(JiraConnectorStub._created_issues) == 0
    assert len(JiraConnectorStub._issue_links) == 0
    assert '[DRY-RUN]' in result.output


# ---------------------------------------------------------------------------
# issue_ref_fields tests
# ---------------------------------------------------------------------------

@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_ref_field_resolved_via_yaml(cli_runner, bulk_yaml, tmp_path):
    """A field declared in issue_ref_fields in the YAML is resolved through
    the alias map before the issue is submitted."""
    JiraConnectorStub.setup_clear_issues()
    f = tmp_path / 'ref.yaml'
    f.write_text(yaml.dump({
        'issue_ref_fields': ['parent'],
        'issues': [
            {'id': 'epic', 'summary': 'The Epic', 'description': 'Desc',
             'project': 'PROJ', 'issue_type': 'Epic'},
            {'id': 'story', 'summary': 'Child Story', 'description': 'Desc',
             'project': 'PROJ', 'issue_type': 'Story',
             'fields': {'parent': 'epic'}},
        ],
    }))
    result = cli_runner.invoke(bulk_import_cmd, [str(f)], obj={})
    assert result.exit_code == 0
    assert len(JiraConnectorStub._created_issues) == 2
    story = JiraConnectorStub._created_issues[1]
    # alias resolved to a real key; wire format is plain string when field
    # type is unknown (no "issuelinks" entry in the stub's type map)
    assert story['parent'] != 'epic'
    assert story['parent'].startswith('ISSUE-')


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_ref_field_parent_default(cli_runner, bulk_yaml):
    """'parent' is resolved by default without any explicit declaration."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'epic', 'summary': 'The Epic', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Epic'},
        {'id': 'story', 'summary': 'Child Story', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Story',
         'fields': {'parent': 'epic'}},
    ])
    # No --issue-ref-field flag and no issue_ref_fields in YAML needed
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    story = JiraConnectorStub._created_issues[1]
    assert story['parent'] != 'epic'
    assert story['parent'].startswith('ISSUE-')


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_ref_field_resolved_via_cli(cli_runner, bulk_yaml):
    """A field declared via --issue-ref-field on the CLI is resolved the same
    way as one listed in the YAML."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'epic', 'summary': 'The Epic', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Epic'},
        {'id': 'story', 'summary': 'Child Story', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Story',
         'fields': {'custom_parent_field': 'epic'}},
    ])
    result = cli_runner.invoke(
        bulk_import_cmd, ['--issue-ref-field', 'custom_parent_field', path],
        obj={})
    assert result.exit_code == 0
    story = JiraConnectorStub._created_issues[1]
    assert story['custom_parent_field'] != 'epic'
    assert story['custom_parent_field'].startswith('ISSUE-')


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_ref_field_real_key_passthrough(cli_runner, bulk_yaml):
    """If the field value is a real Jira key (not a local alias) it is passed
    through unchanged.  The key must exist on the server (validation checks)."""
    JiraConnectorStub.setup_clear_issues()
    # Seed a real issue so validation can confirm it exists
    JiraConnectorStub.setup_add_random_issue()
    existing_key = JiraConnectorStub._issues_list[0]['key']

    path = bulk_yaml([
        {'id': 'story', 'summary': 'Story', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Story',
         'fields': {'parent': existing_key}},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    assert JiraConnectorStub._created_issues[0]['parent'] == existing_key


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_ref_field_ordering(cli_runner, bulk_yaml):
    """An issue whose issue_ref_field points to a local alias must be created
    after the referenced issue even if listed first in the file."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        # story listed first but depends on epic via parent field
        {'id': 'story', 'summary': 'Child Story', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Story',
         'fields': {'parent': 'epic'}},
        {'id': 'epic', 'summary': 'The Epic', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Epic'},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    summaries = [i['summary'] for i in JiraConnectorStub._created_issues]
    assert summaries.index('The Epic') < summaries.index('Child Story')


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_ref_field_non_ref_field_unchanged(cli_runner, bulk_yaml):
    """A field NOT listed in issue_ref_fields is not looked up in the alias
    map even if its value happens to match a local alias."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'epic', 'summary': 'Epic', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Epic'},
        {'id': 'story', 'summary': 'Story', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Story',
         # 'label' is NOT an issue-ref field; value 'epic' should stay literal
         'fields': {'label': 'epic'}},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    story = JiraConnectorStub._created_issues[1]
    assert story['label'] == 'epic'


def test_topo_sort_issue_ref_field_dep():
    """_bulk_topo_sort treats issue_ref_fields values that are local aliases
    as ordering dependencies."""
    issues = [
        {'id': 'story', 'summary': 'Story',
         'fields': {'parent': 'epic'}},
        {'id': 'epic', 'summary': 'Epic'},
    ]
    result = _bulk_topo_sort(issues, issue_ref_fields={'parent'})
    ids = [i['id'] for i in result]
    assert ids.index('epic') < ids.index('story')


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_issue_ref_field_issuelinks_type_wraps_key(cli_runner, bulk_yaml):
    """When a field's schema type is 'issuelinks', the value is wrapped in
    {"key": ...} so the Jira API accepts it."""
    JiraConnectorStub.setup_clear_issues()
    # Tell the stub that 'parent' is an issuelinks-type field
    JiraConnectorStub._field_type_mapping = {'parent': 'issuelinks'}
    path = bulk_yaml([
        {'id': 'epic', 'summary': 'The Epic', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Epic'},
        {'id': 'story', 'summary': 'Child Story', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Story',
         'fields': {'parent': 'epic'}},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 0
    story = JiraConnectorStub._created_issues[1]
    assert story['parent'] == {"key": story['parent']['key']}
    assert story['parent']['key'].startswith('ISSUE-')


def test_topo_sort_issue_ref_field_cycle_raises():
    """A cycle that runs through issue_ref_fields is detected."""
    issues = [
        {'id': 'a', 'fields': {'parent': 'b'}},
        {'id': 'b', 'fields': {'parent': 'a'}},
    ]
    import click
    with pytest.raises(click.UsageError, match="Cycle"):
        _bulk_topo_sort(issues, issue_ref_fields={'parent'})


# ---------------------------------------------------------------------------
# --validate tests
# ---------------------------------------------------------------------------

@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_validate_flag_passes_and_creates_nothing(cli_runner, bulk_yaml):
    """--validate exits 0 when everything is valid and creates no issues."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug'},
    ])
    result = cli_runner.invoke(bulk_import_cmd, ['--validate', path], obj={})
    assert result.exit_code == 0
    assert 'Validation passed' in result.output
    assert len(JiraConnectorStub._created_issues) == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_validate_catches_bad_project(cli_runner, bulk_yaml):
    """--validate reports an error for an unknown project."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'NOEXIST', 'issue_type': 'Bug'},
    ])
    result = cli_runner.invoke(bulk_import_cmd, ['--validate', path], obj={})
    assert result.exit_code == 1
    assert 'project/issue-type invalid' in result.output
    assert len(JiraConnectorStub._created_issues) == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_validate_catches_bad_link_type(cli_runner, bulk_yaml):
    """--validate reports an error for an unknown link type."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug'},
        {'id': 'b', 'summary': 'B', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug',
         'links': [{'link_type': 'BOGUS_TYPE', 'direction': 'outward',
                    'target': 'a'}]},
    ])
    result = cli_runner.invoke(bulk_import_cmd, ['--validate', path], obj={})
    assert result.exit_code == 1
    assert 'unknown link type' in result.output
    assert len(JiraConnectorStub._created_issues) == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_validate_catches_missing_external_link_target(cli_runner, bulk_yaml):
    """--validate reports an error when an external link target doesn't exist."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug',
         'links': [{'link_type': 'Depends', 'direction': 'outward',
                    'target': 'PROJ-DOESNOTEXIST'}]},
    ])
    result = cli_runner.invoke(bulk_import_cmd, ['--validate', path], obj={})
    assert result.exit_code == 1
    assert 'not found' in result.output
    assert len(JiraConnectorStub._created_issues) == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_validate_accepts_local_alias_targets(cli_runner, bulk_yaml):
    """--validate does not try to fetch local aliases from the server."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug'},
        {'id': 'b', 'summary': 'B', 'description': 'Desc',
         'project': 'PROJ', 'issue_type': 'Bug',
         'links': [{'link_type': 'Depends', 'direction': 'outward',
                    'target': 'a'}]},
    ])
    result = cli_runner.invoke(bulk_import_cmd, ['--validate', path], obj={})
    assert result.exit_code == 0
    assert 'Validation passed' in result.output


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_live_run_aborts_on_validation_error(cli_runner, bulk_yaml):
    """A live run (no --dry-run) validates first and aborts before creating
    any issues when validation fails."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'NOEXIST', 'issue_type': 'Bug'},
    ])
    result = cli_runner.invoke(bulk_import_cmd, [path], obj={})
    assert result.exit_code == 1
    assert len(JiraConnectorStub._created_issues) == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_dry_run_skips_validation(cli_runner, bulk_yaml):
    """--dry-run makes no server contact at all — even an invalid project is
    not caught."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'NOEXIST', 'issue_type': 'Bug'},
    ])
    result = cli_runner.invoke(bulk_import_cmd, ['--dry-run', path], obj={})
    assert result.exit_code == 0
    assert 'Validat' not in result.output
    assert len(JiraConnectorStub._created_issues) == 0


@patch('jcli.connector.JiraConnector', JiraConnectorStub)
def test_validate_accumulates_all_errors(cli_runner, bulk_yaml):
    """--validate reports every error found, not just the first one."""
    JiraConnectorStub.setup_clear_issues()
    path = bulk_yaml([
        {'id': 'a', 'summary': 'A', 'description': 'Desc',
         'project': 'NOEXIST', 'issue_type': 'Bug'},
        {'id': 'b', 'summary': 'B', 'description': 'Desc',
         'project': 'ALSO_BAD', 'issue_type': 'Bug'},
    ])
    result = cli_runner.invoke(bulk_import_cmd, ['--validate', path], obj={})
    assert result.exit_code == 1
    # Both errors should appear
    assert result.output.count('ERROR:') >= 2
