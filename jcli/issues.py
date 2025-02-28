import click
import csv
import logging
import os
import pprint
import re
import shutil
import sys

from jcli import connector
from jcli.utils import display_via_pager
from jcli.utils import fitted_blocks
from jcli.utils import get_text_via_editor
from jcli.utils import git_get_commit_oneline
from jcli.utils import git_get_commit_formatted
from jcli.utils import issue_eval
from jcli.utils import str_containing
from jcli.utils import str_contained
from jcli.utils import trim_text
from tabulate import tabulate

LOG = logging.getLogger(__name__)

ISSUE_DETAILS_MAP = {
    "key": "key",
    "project": "raw['fields']['project']['name']",
    "priority": "raw['fields']['priority']['name']",
    "summary": "raw['fields']['summary']",
    "status": "raw['fields']['status']['name']",
    "assignee": "raw['fields']['assignee']['name']",
}


@click.command(
    name='list'
)
@click.option('--assignee', type=str, default="",
              help="The name of the assignee (defaults to current user)")
@click.option('--project', type=str, default=None,
              help="The name of the project (defaults to '')")
@click.option('--jql', type=str, default=None,
              help="A raw JQL string to execute against the issues search")
@click.option("--closed", type=bool, default=False,
              help="Whether to include closed issues (default is False).")
@click.option("--summary-len", 'len_', type=int, default=45,
              help="Trim the summary length to certain number of chars (45 default, 0 for no trim)")
@click.option('--output', type=click.Choice(['table', 'csv', 'simple']),
              default='table',
              help="Output format (default is 'table')")
@click.option("--matching-eq", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-neq", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-contains", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-not", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-in", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-gt", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-lt", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-ge", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-le", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--mentions", type=bool, is_flag=True, default=False,
              help="Checks for mentions on all issues.")
@click.option("--updated-since", type=str, default=None,
              help="Only issues that have been updated since [ARG] - could be a date or an offset (like -1d or -3h, etc.)")
@click.option('--issue-offset', type=int, default=0,
              help="Sets the offset for pulling issues")
@click.option('--max-issues', type=int, default=100,
              help="Sets the max number of issues to pull")
@click.option('--sort',
              type=click.Choice(["prio-asc", "prio-desc",
                                 "type-asc", "type-desc",
                                 "created-asc", "created-desc",
                                 "duedate-asc", "duedate-desc",
                                 "status-asc", "status-desc",
                                 "project-asc", "project-desc",
                                 "none"],
                                case_sensitive=False),
              default="none", help="Sort the output")
def list_cmd(assignee, project, jql, closed, len_, output, matching_eq,
             matching_neq, matching_contains, matching_not,
             matching_in, matching_gt, matching_lt, matching_ge, matching_le,
             mentions, updated_since,
             issue_offset, max_issues, sort) -> None:
    jobj = connector.JiraConnector()
    jobj.login()

    if jql is not None:
        issues_query = jql
    else:
        qd = {}
        for matches in [(matching_eq, "="), (matching_neq, "!="),
                        (matching_contains, "~"),
                        (matching_not, "is not"),
                        (matching_in, "in"), (matching_gt, ">"),
                        (matching_lt, "<"), (matching_ge, ">="),
                        (matching_le, "<=")]:
            for f, v in matches[0]:
                qd[f] = (matches[1], v)

        if assignee == "-":
            assignee = None
        if mentions:
            # Mentions is special case, so we will fill up the query
            # to check for comments that contain our user info.
            assignee = None
            qd["comment"] = ("~", "currentUser()")
        if updated_since:
            qd["updatedDate"] = (">=", updated_since)

        if sort != "none":
            qd["ORDER BY"] = jobj.order_by_from_string(sort)

        issues_query = jobj.build_issues_query(assignee, project, closed,
                                               fields_dict=qd)

    issues = jobj._query_issues(issues_query, issue_offset, max_issues)
    ISSUE_HEADER = []

    if len(issues) != 0:
        issue_list = []
        summary_pos = None

        for header in ISSUE_DETAILS_MAP:
            if header not in ISSUE_HEADER:
                ISSUE_HEADER.append(header)

        if "summary" in ISSUE_HEADER:
            summary_pos = ISSUE_HEADER.index("summary")

        for issue in issues:
            issue_details = issue_eval(issue, ISSUE_DETAILS_MAP)
            if summary_pos is not None:
                issue_details[summary_pos] = trim_text(
                    issue_details[summary_pos], len_
                )
            issue_list.append(issue_details)

        if output == 'table':
            final = tabulate(issue_list, ISSUE_HEADER, 'psql')
        elif output == 'simple':
            final = tabulate(issue_list, ISSUE_HEADER, 'simple')
        elif output == 'csv':
            final = ",".join(ISSUE_HEADER) + "\n"
            for line in issue_list:
                final += ",".join(line) + "\n"

        click.echo(final)


@click.command(
    name='show'
)
@click.argument('issuekey')
@click.option("--raw", is_flag=True, default=False,
              help="Dump the issue details in 'raw' form.")
@click.option("--width", type=int, default=0,
              help="Use a set width for display.  Default of '0' will set the display based on the terminal width.")
def show_cmd(issuekey, raw, width):
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)

    if issue is None:
        click.echo(f"Unable to find issue: {issuekey}")
        return

    if raw is True:
        click.echo(pprint.pprint(vars(issue)))
        click.echo(jobj._fetch_custom_fields())
        return

    # Get terminal width and adjust max width
    if width == 0:
        width = shutil.get_terminal_size().columns - 2
    max_width = max(width, 79)

    issue_details = issue_eval(issue, ISSUE_DETAILS_MAP)
    if issue_details is None:
        click.echo(f"Error with {issuekey}")
        return

    excluded = jobj.excluded_fields()

    output = "+" + '-' * (max_width - 2) + "+\n"
    pname = jobj.get_field(issue, 'project', 'name')
    aname = jobj.get_field(issue, 'assignee', 'name')

    output += f"| {issue.key:<10} | {pname:<20} | {aname:<39} |\n"
    output += "+" + '-' * (max_width - 2) + "+\n"
    prio = jobj.get_field(issue, 'priority', 'name')
    status = jobj.get_field(issue, 'status', 'name')

    summ = jobj.get_field(issue, 'summary')

    reporter = jobj.get_field(issue, 'reporter', 'name')

    output += f"| priority: {prio:<20} | status: {status:<34} |\n"
    output += "+" + '-' * (max_width - 2) + "+\n"
    output += f"| Reporter: {reporter:<{max_width - 14}} |\n"
    output += "+" + '-' * (max_width - 2) + "+\n"

    if 'url' not in excluded:
        output += f"| URL: {jobj.issue_url(issuekey):<{max_width - 9}} |\n"
        output += "+" + '-' * (max_width - 2) + "+\n"

    if 'summary' not in excluded:
        output += f"| summary: {' ' * (max_width - 13)} |\n"
        output += f"| ------- {' ' * (max_width - 12)} |\n"

    for issue_field in jobj.requested_fields():
        output += f"| {issue_field:<25}: {jobj.get_field(issue, issue_field):<{max_width - 31}} |\n"

    if len(summ) <= max_width - 4:
        output += f"| {summ:<{max_width - 4}} |\n"
    else:
        while len(summ) > 0:
            output += f"| {summ[:max_width - 4]:<{max_width - 4}} |\n"
            summ = summ[max_width - 4:]
    output += "+" + '-' * (max_width - 2) + "+\n\n"

    if 'eausm' not in excluded and 'eausm' in issue.raw['fields']:
        output += "+" + '-' * (max_width - 2) + "+\n"
        output += f"| EZ Agile: {' ' * (max_width - 14)} |\n"

        if 'votes' in issue.raw['fields']['eausm']:
            total = 0
            if not len(issue.raw['fields']['eausm']['votes']):
                output += f"| No Votes{' ' * (max_width - 12)} |\n"
            for vote in issue.raw['fields']['eausm']['votes']:
                total += int(vote['vote'])
                user = jobj.find_users_by_name(vote['userId'])
                if len(user):
                    user = user[0].displayName
                else:
                    user = f"[{vote['userId']}]?"
                output += f"| Vote: {vote['vote']} by {user} {' ' * (max_width - (15 + len(user) + len(str(vote['vote']))))} |\n"
            output += "|" + '-' * (max_width - 2) + "|\n"
            output += f"| Total: {str(total)} {' ' * (max_width - (len(str(total)) + 12))} |\n"
        else:
            output += f"| No votes. {' ' * (max_width - 14)} |\n"

        output += "+" + '-' * (max_width - 2) + "+\n\n"

    if 'links' not in excluded and issue.fields.issuelinks is not None and \
       len(issue.fields.issuelinks) > 0:
        output += f"| Links: {' ' * (max_width - 11)} |\n"
        output += f"|{'-' * (max_width - 2)}|\n"
        for link in issue.fields.issuelinks:
            link_text = ""
            if hasattr(link, "outwardIssue"):
                link_text = f"| - Linked To Issue: {link.outwardIssue}"
            if hasattr(link, "inwardIssue"):
                link_text = f"| - Linked From Issue: {link.inwardIssue}"
            if hasattr(link, "type") and hasattr(link.type, "name"):
                link_text += f", Relationship: {link.type.name}"
            if len(link_text):
                output += link_text + ' ' * (max_width - (len(link_text) + 1))
                output += "|\n"

        remote_links = jobj.jira.remote_links(issue.key)
        for link_id in remote_links:
            link = jobj.jira.remote_link(issuekey, link_id)
            if hasattr(link, "object"):
                url = ""
                title = ""
                if hasattr(link.object, "url"):
                    url = link.object.url
                if hasattr(link.object, "title"):
                    title = link.object.title
                    url = f"[{title}|{url}]"
                link_text = f"| - Remote: {url}"
                output += link_text + ' ' * (max_width - (len(link_text) + 1))
                output += "|\n"
        output += "\n"

    if 'attachments' not in excluded and issue.fields.attachment is not None \
       and len(issue.fields.attachment) > 0:
        output += f"| Attachments: {' ' * (max_width - 17)} |\n"
        output += f"|{'-' * (max_width - 2)}|\n"
        attach_display = []
        for attachment in issue.fields.attachment:
            attach = (attachment.filename, attachment.created, attachment.size,
                      attachment.author.displayName)
            attach_display.append(attach)
        final = tabulate(attach_display, ('File', 'Created', 'Size', 'Creator'),
                         'psql')
        output += final + "\n\n"

    descr = jobj.jira_text_field_to_md(jobj.get_field(issue, 'description'))
    if 'description' not in excluded and len(descr) > 0:
        output += f"| Description: {' ' * (max_width - 17)} |\n"
        output += f"|{'-' * (max_width - 2)}|\n"
        output += fitted_blocks(descr, max_width - 4, "|")

    comments_block = f"+ Comments: {' ' * (max_width - 14)} |\n"
    for comment in issue.fields.comment.comments:
        if max_width < 80:
            comments_block += f"| Author: {comment.author.displayName:<14} [~{comment.author.name:<18}] | {comment.created:<20} |\n"
        else:
            v = "all"
            try:
                v = f"{comment.visibility.value}"
            except:
                pass
            visibility = f"{v:<20} | "
            add_ln = f"| Author: {comment.author.displayName:<20} [~{comment.author.name:<20}] | {comment.id:<18} | {visibility}{comment.created:<20}"
            if len(add_ln) > max_width:
                add_ln += "\n"
            else:
                diff = max_width - (len(add_ln) + 1)
                add_ln += " " * diff
                add_ln += "|\n"
            comments_block += add_ln
        comments_block += f"|{'-' * (max_width - 2)}|\n"
        comments_block += fitted_blocks(jobj.jira_text_field_to_md(comment.body),
                                        max_width - 4, "|")
        comments_block += "+" + '-' * (max_width - 2) + "+\n"

    if 'comments' not in excluded:
        output += comments_block

    display_via_pager(output, f"Issue: {issuekey}")


@click.command(
    name="add-comment"
)
@click.argument('issuekey')
@click.option("--comment", type=str, default=None,
              help="The comment text to add.  Defaults to opening an editor.")
@click.option("--visibility", type=str, default='all',
              help="Sets the group / role for visibility.  Defaults to 'all'.")
def add_comment_cmd(issuekey, comment, visibility):
    jobj = connector.JiraConnector()
    jobj.login()

    if comment is None:
        comment = get_text_via_editor()

    if comment is None or len(comment) == 0 or comment.isspace():
        click.echo("Error: No comment provided.")
        sys.exit(1)

    comment = jobj.md_text_to_jira_text_field(comment)
    jobj.add_comment(issuekey, comment, visibility)


@click.command(
    name="del-comment"
)
@click.argument('issuekey')
@click.argument('comment_id')
def del_comment_cmd(issuekey, comment_id):
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)
    if issue is None:
        click.echo(f"Issue {issuekey} not found.")
        return

    comment = jobj.get_comment(issue.raw['key'], comment_id)
    if comment is not None:
        comment.delete()
        click.echo(f"Comment {comment_id} deleted.")
    else:
        click.echo(f"Comment {comment_id} for issue {issuekey} not found.")


@click.command('update-comment')
@click.argument('issuekey')
@click.argument('comment_id')
@click.option("--body", type=str, default=None,
              help="Set new body to the argument.")
@click.option('--visibility', type=str, default=None,
              help="Sets the group / role for visibility.  Use 'all' for no restriction.")
def update_comment_cmd(issuekey, comment_id, body, visibility):
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)
    if issue is None:
        click.echo(f"Issue {issuekey} not found.")
        return

    comment = jobj.get_comment(issue.raw['key'], comment_id)
    if comment is None:
        click.echo(f"Comment {comment_id} for issue {issuekey} not found.")

    update = {}
    body_text = None
    if body is None:
        ctext = jobj.jira_text_field_to_md(comment.body)
        body_text = get_text_via_editor(ctext)
    elif body != "":
        body_text = body

    if body_text:
        update['body'] = jobj.md_text_to_jira_text_field(body_text)

    if visibility is not None:
        if visibility.lower() == 'all':
            update['visibility'] = {'identifier': None}
        else:
            update['visibility'] = {'type': 'group', 'value': visibility}

    if len(update) == 0:
        click.echo("No Changes.")
        return

    comment.update(**update)
    click.echo(f"Comment {comment_id} updated.")


@click.command(
    name="states"
)
@click.argument('issuekey')
def states_cmd(issuekey):
    jobj = connector.JiraConnector()
    jobj.login()

    states = jobj.get_states_for_issue(issuekey)

    click.echo(states)


@click.command(
    name="set-status"
)
@click.argument("issuekey")
@click.argument("status")
def set_state_cmd(issuekey, status):
    jobj = connector.JiraConnector()
    jobj.login()

    jobj.set_state_for_issue(issuekey, status)
    click.echo("done.")


@click.command(
    name="add-watcher"
)
@click.argument('issuekey')
@click.argument('watcher')
def add_watcher_cmd(issuekey, watcher):
    jobj = connector.JiraConnector()
    jobj.login()

    jobj.add_watcher(issuekey, watcher)
    click.echo('done.')


@click.command(
    name="del-watcher"
)
@click.argument('issuekey')
@click.argument('watcher')
def del_watcher_cmd(issuekey, watcher):
    jobj = connector.JiraConnector()
    jobj.login()

    jobj.del_watcher(issuekey, watcher)
    click.echo('done.')


@click.command(
    name="get-field"
)
@click.argument('issuekey')
@click.argument('fieldname')
def get_field_cmd(issuekey, fieldname):
    jobj = connector.JiraConnector()
    jobj.login()
    issue = jobj.get_issue(issuekey)
    field = jobj.get_field(issue, fieldname)
    click.echo(f"{fieldname}: {field}")


@click.command(
    name="set-field"
)
@click.argument('issuekey')
@click.argument('fieldname')
@click.argument('fieldvalue')
@click.option("--forced", is_flag=True, default=False,
              help="Force the value to be run through python eval and used as-is.")
def set_field_cmd(issuekey, fieldname, fieldvalue, forced):
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)

    if issue is None:
        click.echo(f"Error: {issuekey} not found.")
        sys.exit(1)

    old = jobj.get_field(issue, fieldname)

    jobj.set_field(issue, fieldname, fieldvalue, forced)

    new = jobj.get_field(issue, fieldname)

    click.echo(f"Updated {issuekey}, set {fieldname}: {old} -> {new}")


@click.command(
    name="set-field-from-csv"
)
@click.argument('csvfile', type=click.Path(exists=True))
def set_field_from_csv_cmd(csvfile):
    jobj = connector.JiraConnector()
    jobj.login()

    with open(csvfile, mode='r', newline='') as file:
        reader = csv.reader(file)
        # we assume no header is set, if one is set we can ignore it with:
        # next(reader, None)

        for row in reader:
            if len(row) < 3:
                click.echo(f"Skipping invalid row: {row}")
                continue

            issuekey = row[0]
            fvp = row[1:]

            issue = jobj.get_issue(issuekey)

            if issue is None:
                click.echo(f"Error: {issuekey} not found - skipping row.")
                continue

            # iterate through fieldname, fieldvalue pairs in the remaining elements of the row
            for i in range(0, len(fvp), 2):
                fieldname = fvp[i]
                fieldvalue = fvp[i + 1]

                old = jobj.get_field(issue, fieldname)
                jobj.set_field(issue, fieldname, fieldvalue)
                new = jobj.get_field(issue, fieldname)
                click.echo(f"Updated {issuekey}, set {fieldname}: {old} -> {new}")


def issue_extract_blocks(issue_block):
    parse_as_git = False

    # Split the text into blocks separated by blank lines
    if issue_block.startswith("From ") and "\n---\n" in issue_block:
        parse_as_git = True

    lines = issue_block.split('\n')

    # Initialize variables to store summary, description, and comments, and
    # track the git sections
    summary = ''
    description = ''
    comments = []
    git_state = 0

    # Flag to indicate whether we are currently parsing the summary or description
    parsing_summary = True

    # Iterate over each line
    for line in lines:
        tabbed = True if line.startswith("\t") else False

        line = line.strip()

        # Skip empty lines
        # Check if we move on to description
        if not line.strip() and parsing_summary:
            parsing_summary = False
            continue

        # If git parsing - check for the subject line, and handle
        # overcontinuation
        if parse_as_git:
            if git_state == 0:
                if line.startswith("Subject:"):
                    pos = line.find("]")
                    line = line[pos + 1:]
                    git_state = 1
                    summary += line
                # ignore lines until 'Subject'
                continue

            if git_state == 1:
                if not parsing_summary:
                    # we move the git-state along
                    # but let it process as normal through the rest of the
                    # machine.
                    git_state = 2
                else:
                    if not tabbed:
                        continue

                    summary += " " + line.lstrip()
                    # this needs to be here to skip double add later
                    # due to the git detection code being here.
                    continue

            # detect the cutline, and switch to flag the 'diff' as the final
            # parse
            if git_state == 2 and line == "---":
                git_state = 3
                continue

            if git_state == 3:
                if line.startswith("diff --git") or \
                   str_containing(line, ["|", "changed", "created mode"]):
                    break

        # accumulate comments
        if line.startswith('#'):
            comments.append(line)
            continue

        if parsing_summary:
            summary += line
        else:
            description += line + '\n'

    summary = summary.strip()
    description = description.strip()
    return summary, description, comments


@click.command(
    name='create'
)
@click.option("--summary", type=str, default=None,
              help="The summary for the issue.  Default is to use the text editor interpretation.")
@click.option("--description", type=str, default=None,
              help="Description of the issue.  Default is to use the text editor interpretation.")
@click.option("--project", type=str, default=None,
              help="The project to open.  Default is to use the text editor interpretation.")
@click.option("--issue-type",
              type=click.Choice(["Epic", "Bug", "Story", "Task", "Subtask"],
                                case_sensitive=False),
              default='bug',
              help="Specific issue type.  Defaults to 'bug'.")
@click.option("--set-field", multiple=True, nargs=2,
              help="Sets a specific field.", default=None)
@click.option("--from-file", type=click.Path(exists=True),
              help="Uses a file (like a git patchfile).", default=None)
@click.option("--commit", multiple=True, type=str, default=None,
              help="Create an issue that will reference multiple commits.")
@click.option("--oneline", is_flag=True, default=False,
              help="When specifying a single commit, force the one-line version.")
@click.option("--verbose", is_flag=True, default=False,
              help="Will print the issue details being added.  Ignored with '--dry-run'.")
@click.option("--show-fields", is_flag=True, default=False,
              help="Will include the fields that can be set for the project and"
              " issue type.  Must specify valid values for both on the command line.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Do not actually commit the issue.")
def create_issue_cmd(summary, description, project, issue_type, set_field,
                     from_file, commit, oneline, verbose, show_fields, dry_run):
    jobj = connector.JiraConnector()
    jobj.login()

    filled_all = all((summary, description, project))
    special_lines = None
    fields = {}
    set_field = set_field or []

    if commit:
        if len(commit) == 1 and not oneline:
            # treat this as a from-file with a specific commit.
            as_email = git_get_commit_formatted(commit[0])
            summary, description, comments = issue_extract_blocks(as_email)
        else:
            description = "# The following commits will be referenced in the ticket:\n"
            for sha in commit:
                commit_line = git_get_commit_oneline(sha)
                if not commit_line or not len(commit_line):
                    click.echo(f"ERROR: Unable to find {sha}")
                    click.echo("Please make sure you are in a git tree, or GIT_DIR is defined.")
                    sys.exit(1)
                commit_lines = commit_line.split("\n")
                for commit_line in commit_lines:
                    if len(commit_line):
                        description += f"   {commit_line}\n"

    if from_file:
        with open(from_file, "r") as f:
            # We want to ensure that we always let the user edit the final
            # issue text before submitting it.
            filled_all = False

            summary, description, comments = issue_extract_blocks(f.read())
            if str_contained("# set-project: ", comments):
                special_lines = "\n".join(comments)
                for c in comments:
                    if c.startswith("# set-project: ") and not project:
                        project = c[15:]
    else:
        summary = summary or "# The first line in this will be treated as the summary."
        description = description or (
            "# Add your description here.  By default, all lines\n"
            "# starting with a '#' are used to denote special lines")

    project = project or jobj.get_default_str('project', "Default Project")

    if not special_lines:
        special_lines = (f"# set-project: {project}\n"
                         f"# issue-type: {issue_type}\n"
                         "# NOTE: you can use a line '# set-field: \"foo\" bar' to set field 'foo'\n"
                         "#       to value 'bar'.  The 'set-field' directive requires\n"
                         "#       field to be quoted as \"Some Foo\".")

    if project != "Default Project" and show_fields:
        # Try to pull the default fields for project and bug type
        special_lines += "# Assignable fields below:\n"

        for f in jobj.get_project_default_types(project, issue_type):
            f = '"' + f + '"'
            fields[f] = "value"

    for f in set_field:
        field = f[0]
        if not field.startswith('"'):
            field = '"' + f[0] + '"'
        special_lines += f"# set-field: {field} {f[1]}\n"

    for k, v in fields.items():
        special_lines += f"## set-field: {k} {v}\n"

    template_data = f"{summary}\n\n{description}\n\n{special_lines}"

    if not filled_all:
        issue_patch = get_text_via_editor(template_data)

        if issue_patch == template_data and not (from_file or
                                                 (commit and not oneline)):
            click.echo("Issue text not set.  Please fill in project, summary, and description.")
            sys.exit(1)
    else:
        issue_patch = template_data

    # process the results.
    issue = {}

    issue["summary"], issue["description"], comments = issue_extract_blocks(issue_patch)

    for c in comments:
        if c.startswith("# set-field:"):
            m = re.match(r'# set-field: "(.*)" (.*)', c)
            if m:
                f, v = m.groups()
                f = jobj._try_fieldname(f)
                v = jobj.convert_to_field_type(f, v)
                issue[f] = v
        elif c.startswith("# set-project: "):
            project = c[15:]
        elif c.startswith("# issue-type: "):
            issue_type = c[14:]

    issue["project"] = project
    issue["issuetype"] = issue_type
    if dry_run or verbose:
        click.echo(f"Creating: {pprint.pformat(issue)}")
    result = "DRY-OKAY" if dry_run else jobj.create_issue(issue)
    click.echo(f"done - Result: {result}.")


@click.command(
    name='attachments'
)
@click.argument('issuekey')
@click.option("--pull", default=None,
              help="The attachment ID to download")
@click.option("--push", default=None,
              help="file to upload as attachment")
def attachments_cmd(issuekey, pull, push):
    jobj = connector.JiraConnector()
    jobj.login()
    issue = jobj.get_issue(issuekey)

    if pull and push:
        raise click.UsageError("Invalid pull and push specified.")

    if pull:
        i = 0
        for attachment in issue.fields.attachment:
            if pull == attachment.filename or pull == str(i):
                click.echo(f"Downloading: {attachment.filename}")
                jobj.fetch_attachment(attachment.id, attachment.filename)
                return
            i += 1
        click.echo(f"Unknown attachment {pull}.")
        return

    if push:
        with open(push, 'rb') as f:
            jobj.upload_attachment(issue, f, os.path.basename(push))
        return

    output = "Attachments:\n"
    if issue.fields.attachment is not None and \
       len(issue.fields.attachment) > 0:
        attach_display = []
        i = 0
        for attachment in issue.fields.attachment:
            attach = (i, attachment.filename, attachment.created,
                      attachment.size, attachment.author.displayName)
            attach_display.append(attach)
            i += 1
        final = tabulate(attach_display,
                         ('Id', 'File', 'Created', 'Size', 'Creator'),
                         'psql')
        output += final + "\n\n"
    click.echo(output)


@click.command(
    name='eausm-vote'
)
@click.argument('issuekey')
@click.argument('vote')
def eausm_vote_cmd(issuekey, vote):
    jobj = connector.JiraConnector()
    jobj.login()
    issue = jobj.get_issue(issuekey)
    if issue is None:
        raise click.UsageError("Issue not found")

    jobj.eausm_vote_issue(issue, vote)

    click.echo("Voted.")


def get_link_type_choices():
    jobj = connector.JiraConnector()
    try:
        jobj.login()
    except:
        return []

    return [x.name for x in jobj.jira.issue_link_types()]


@click.command(
    name="add-link"
)
@click.argument('issuekey')
@click.argument('url')
@click.argument('title')
@click.option("--relationship-type",
              type=click.Choice(["inward", "outward"],
                                case_sensitive=False),
              default='outward',
              help="Add a link to the issue.")
@click.option("--link-type",
              type=click.Choice(get_link_type_choices(),
                                case_sensitive=False),
              help="Set a relationship.")
def add_link_cmd(issuekey, url, title, relationship_type, link_type):
    """Adds a new link to URL to the issue at ISSUEKEY.

       TITLE will be used as a title if the URL is a remote url.  It will be
       treated as a comma if the remote link is another issue.  If it is set
       to the value 'none', it will be defaulted."""
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)
    if issue is None:
        raise ValueError(f"Issue {issuekey} not found")

    if title.lower() == "none":
        title = None

    if issue.fields.issuelinks is not None and \
       len(issue.fields.issuelinks) > 0:
        links = issue.fields.issuelinks if link_type == 'issue' else \
            jobj.jira.remote_links(issue.key)
        found = False
        for link in links:
            if hasattr(link, "object") and hasattr(link.object, "url") and \
               url == link.object.url:
                found = True
            elif hasattr(link, 'outwardIssue') and link.outwardIssue == url:
                found = True
            elif hasattr(link, 'inwardIssue') and link.inwardIssue == url:
                found = True
        if found:
            click.echo(f"{url} already added to issue.")
            return

    # if we got here, this is a new link
    jobj.add_issue_link(issuekey, url, title, link_type)
