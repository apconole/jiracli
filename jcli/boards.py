import click
import json as JSON
import logging
import pprint

import jira
from jcli import connector
from jcli.utils import display_via_pager
from jcli.utils import issue_eval
from jcli.utils import trim_text

from tabulate import tabulate

LOG = logging.getLogger(__name__)

BOARD_HEADER_MAP = {
    "name": "raw['name']",
    "type": "raw['type']",
}

BOARD_DETAILS_MAP = {
    "key": "key",
    "project": "raw['fields']['project']['name']",
    "priority": "raw['fields']['priority']['name']",
    "summary": "raw['fields']['summary']",
    "status": "raw['fields']['status']['name']",
    "assignee": "raw['fields']['assignee']['name']",
}


def is_issue_assigned_to(issue, assignee):
    return issue.fields.assignee and \
        (issue.fields.assignee.name.lower() == assignee.lower() or
         issue.fields.assignee.displayName.lower() == assignee.lower())


def is_issue_in_column(issue, column_statuses, jobj):
    return hasattr(issue, 'fields') and \
        issue.fields.status in column_statuses or \
        hasattr(issue, 'statusId') and \
        jobj.get_status_detail(issue.statusId) in column_statuses


@click.command(
    name="list"
)
@click.option("--limit", type=int, default=25,
              help="Limit the number of entries to display (default 25)")
@click.option("--name", type=str, default=None, help="Search for a board by name")
def list_cmd(limit, name):
    """
    Displays all the boards on the instance (can be crazy)
    """
    jobj = connector.JiraConnector()
    jobj.login()

    boards = jobj.fetch_boards(limit, name)

    boards_out = []

    for board in boards:
        board_details = issue_eval(board, BOARD_HEADER_MAP)
        boards_out.append(board_details)

    out = tabulate(boards_out, BOARD_HEADER_MAP, 'psql')
    display_via_pager(out, "Jira Board List")


@click.command(
    name='show'
)
@click.argument('boardname')
@click.option('--assignee', type=str, default=None,
              help="The name of the assignee (defaults to all)")
@click.option('--project', type=str, default=None,
              help="The name of the project (defaults to '')")
@click.option("--filter", type=str, default=None,
              help="Applies a quick filter to the results (defaults to None)")
@click.option("--summary-len", type=int, default=0,
              help="Includes a summary of the length specified when set (defaults to 0, meaning no summary)")
@click.option('--issue-offset', type=int, default=0,
              help="Sets the offset for pulling issues")
@click.option('--max-issues', type=int, default=100,
              help="Sets the max number of issues to pull")
def show_cmd(boardname, assignee, project, filter, summary_len, issue_offset, max_issues):
    """
    Displays the board specified by 'name'
    """
    jobj = connector.JiraConnector()
    jobj.login()

    columns = jobj.fetch_column_config_by_board(boardname)
    ISSUE_HEADER = [column for column in columns]
    issue_col_store = {column: [] for column in columns}

    if filter:
        issues = jobj.fetch_issues_by_board_qf(boardname, issue_offset, max_issues, filter)
    else:
        issues = jobj.fetch_issues_by_board(boardname, issue_offset, max_issues)

    for issue in issues:
        if assignee and not is_issue_assigned_to(issue, assignee):
            continue
        for column in columns:
            if is_issue_in_column(issue, columns[column], jobj):
                issuestr = f"{issue.key}"
                if summary_len:
                    issuestr += f"\n{'-' * summary_len}\n{trim_text(issue.summary, summary_len)}\n{'_' * summary_len}"
                issue_col_store[column].append(issuestr)

    final_output = tabulate(issue_col_store, ISSUE_HEADER, 'psql')
    display_via_pager(final_output, f"Board: {boardname}")


@click.command(name='get-config')
@click.argument('boardname')
def get_config_cmd(boardname):
    """
    Displays the board configuration specified by 'boardname'
    """

    jobj = connector.JiraConnector()
    jobj.login()

    settings = {}

    settings["filter"] = jobj.fetch_jql_config_by_board(boardname)
    cols = jobj.fetch_column_config_by_board(boardname)

    for k, v in cols.items():
        settings[f"column.{k}"] = v

    click.echo(pprint.pprint(settings))

    f = jobj.fetch_quickfilters_by_board(boardname)
    if f:
        for filt in f.quickFilters:
            click.echo(f"quickfilter.name = \"{filt.name}\"")
            click.echo(f"quickfilter.query = \"{filt.query}\"")
            click.echo(f"quickfilter.id = \"{filt.id}\"")


@click.command('sprints')
@click.argument('boardname')
@click.option('--name', type=str, default=None,
              help='Display details for a specific sprint.')
@click.option('--show-all', type=bool, is_flag=True, default=False,
              help='Display all sprints, including closed sprints.')
@click.option('--my-issues', type=bool, is_flag=True, default=False,
              help='Display only those issues in the sprint where assignee is me.')
@click.option("--no-issues", type=bool, is_flag=True, default=False,
              help="Do not query or display issues.")
@click.option("--json", type=bool, is_flag=True, default=False,
              help="Print the details in JSON format.")
def sprints_cmd(boardname, name, show_all, my_issues, no_issues, json):
    """
    Displays the sprints of a board, optionally specified by 'name'
    """
    jobj = connector.JiraConnector()
    jobj.login()

    sprints = jobj.fetch_sprints_by_board(boardname)
    columns = jobj.fetch_column_config_by_board(boardname)
    ISSUE_HEADER = [column for column in columns]

    final_output = ""
    json_sprints = []
    for sprint in sprints:
        current_sprint = {}

        if not show_all and sprint.state == "closed":
            continue

        if name and name.lower() != sprint.name.lower():
            continue

        issue_col_store = {column: [] for column in columns}
        try:
            start_date = sprint.startDate
        except:
            start_date = "0000-00-00T00:00:00.000Z"

        try:
            end_date = sprint.endDate
        except:
            end_date = "0000-00-00T00:00:00.000Z"

        if not json:
            final_output += f"Sprint: {sprint}, id: {sprint.id}\n   start: {start_date} -> end: {end_date}\n"
        else:
            current_sprint["name"] = sprint.name
            current_sprint["id"] = sprint.id
            current_sprint["start_date_str"] = start_date
            current_sprint["end_date_str"] = end_date

        issues_query = f'sprint = {sprint.id}'
        if not no_issues:
            issues = jobj._query_issues(issues_query, 0, 250)
        else:
            issues = []

        match_assignee = None
        if my_issues:
            match_assignee = jobj.myself()

        for issue in issues:
            for column in columns:
                if is_issue_in_column(issue, columns[column], jobj):
                    if my_issues and \
                       jobj.get_field(issue, 'assignee', 'name') != match_assignee:
                        continue

                    if not json:
                        issuestr = f"{issue.key}"
                        issue_col_store[column].append(issuestr)
                    else:
                        jsissue = {}
                        jsissue["key"] = issue.key
                        jsissue["summary"] = jobj.get_field(issue, "summary")
                        jsissue["assignee"] = jobj.get_field(issue, "assignee")
                        jsissue["status"] = jobj.get_field(issue, "status")
                        issue_col_store[column].append(jsissue)

        if len(issues) and not json:
            final_output += tabulate(issue_col_store, ISSUE_HEADER, 'psql')
            final_output += "\n\n"
        else:
            current_sprint["columns"] = issue_col_store
            json_sprints.append(current_sprint)

    if not json:
        click.echo(final_output)
    else:
        click.echo(JSON.dumps(json_sprints))


@click.command("create-sprint")
@click.argument("board")
@click.argument("name")
@click.option("--start-date", type=click.DateTime(),
              help="Starting date for the sprint", default=None)
@click.option("--end-date", type=click.DateTime(),
              help="Ending date for the sprint", default=None)
@click.option("--goal", type=str,
              help="Sprint Goal.", default=None)
def create_sprint_cmd(board, name, start_date, end_date, goal):
    """
    Creates a sprint for BOARD called NAME.
    """
    jobj = connector.JiraConnector()
    jobj.login()

    s = jobj.create_sprint(board, name, start_date, end_date, goal)

    if s:
        click.echo(f"Sprint {s['id']} created.")
    else:
        click.echo(f"Error creating sprint '{name}'.")


@click.command("autoexec")
@click.argument("boardname")
@click.argument("source_sprint")
@click.argument("destination_sprint")
@click.option("--run", type=bool, is_flag=True, default=False, help="Actually make the changes.")
def autoexec_cmd(boardname, source_sprint, destination_sprint, run):
    """
    Automatically close tickets labeled as 'auto-close' and recreate tickets
    labeled as 'recurring'.
    """
    jobj = connector.JiraConnector()
    jobj.login()

    sprints = jobj.fetch_sprints_by_board(boardname)

    old_sprint = None
    new_sprint = None

    for sprint in sprints:
        if sprint.name == source_sprint:
            if old_sprint is not None:
                click.echo(f"Found multiple {source_sprint}")
                return
            old_sprint = sprint
        elif sprint.name == destination_sprint:
            if new_sprint is not None:
                click.echo(f"Found multiple {destination_sprint}")
                return
            new_sprint = sprint

    if old_sprint is None:
        click.echo(f"Could not find {source_sprint}")
        return

    if new_sprint is None:
        click.echo(f"Could not find {destination_sprint}")
        return

    default_actions = {
        "auto-close": {
            "recreate": False,
            "status": "Closed"
        },
        "recurring": {
            "recreate": True,
            "status": "Closed",
            "copy-fields": [
                "Story Points",
                "components",
                "OS",
                "AssignedTeam",
                "Sub-System Group",
                "security"
            ]
        },
        "template": {
            "recreate": True,
            "status": "Closed",
            "copy-fields": [
                "components",
                "OS",
                "AssignedTeam",
                "Sub-System Group"
            ],
            "default-fields": {
                "Story Points": 5.0
            }
        }
    }

    actions = jobj.config.get("auto_exec") or default_actions
    fields = jobj._fetch_custom_fields()

    def _field_xlate(val):
        """ Translate from JIRA custom fields into create issue field. """
        if isinstance(val, list):
            return list(map(_field_xlate, val))

        # translate classes
        if isinstance(val, jira.resources.CustomFieldOption):
            val = val.raw
        elif isinstance(val, jira.resources.User):
            return {"accountId", val.key}

        if isinstance(val, str):
            return val
        elif isinstance(val, dict):
            if "id" in val:
                return {"id": val['id']}
            elif "key" in val:
                return {"key": val['key']}

        # Default action
        return val

    for label, action in actions.items():
        issues = jobj._query_issues(f"sprint = {old_sprint.id} AND labels = {label} AND status != {action['status']}")
        for issue in issues:
            click.echo(f'Processing {issue.key} - {jobj.get_field(issue, "summary")} - with label {label}')
            if run is not True:
                continue

            if action.get("recreate", False) is True:
                new_issue = {}
                new_issue["project"] = issue.fields.project.key
                new_issue["summary"] = jobj._get_field(issue, "summary")
                new_issue["description"] = jobj._get_field(issue, "description")
                new_issue["issuetype"] = {"name": jobj._get_field(issue, "issuetype")}
                new_issue["assignee"] = {"name": issue.fields.assignee.name}

                for field_id, field_name in fields.items():
                    if field_name == "Sprint":
                        new_issue[field_id] = new_sprint.id
                        continue

                    for copy_field in action.get("copy-fields", []):
                        if field_name != copy_field:
                            continue
                        cur_val = jobj._get_field(issue, field_name)
                        new_issue[field_id] = _field_xlate(cur_val)

                    for default_field, default_value in action.get("default-fields", {}).items():
                        if field_name != default_field:
                            continue
                        new_issue[field_id] = default_value

                create_result = jobj.create_issue(new_issue)
                jobj.set_state_for_issue(create_result.key, jobj._get_field(issue, "status"))
                click.echo(f"\t{issue.key} -> {create_result.key}")

            jobj.set_state_for_issue(issue.key, action['status'])
            click.echo(f"\t{issue.key} -> {action['status']}")
