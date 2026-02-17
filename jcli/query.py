import click
import os

from jcli import connector
from jcli.issues import format_issue_output, reporting_choices
from tabulate import tabulate


@click.command(
    name='list-all'
)
def list_all_cmd():
    """List all saved queries from the configuration."""
    jobj = connector.JiraConnector(load_safe=True)

    saved = jobj._config_get_nested("jira.saved_queries")
    if not saved:
        click.echo("No saved queries found.")
        return

    rows = []
    for name, entry in saved.items():
        desc = entry.get("description", "")
        jql = entry.get("jql", "")
        rows.append((name, desc, jql))

    click.echo(tabulate(rows, ("Name", "Description", "JQL"), "psql"))


@click.command(
    name='run'
)
@click.argument('name')
@click.option('--output', type=click.Choice(reporting_choices),
              default='table',
              help="Output format (default is 'table')")
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
@click.option('--max-issues', type=int, default=100,
              help="Sets the max number of issues to pull")
@click.option('--issue-offset', type=int, default=0,
              help="Sets the offset for pulling issues")
@click.option("--summary-len", 'len_', type=int, default=45,
              help="Trim the summary length to certain number of chars")
@click.option('--template-file',
              type=click.Path(),
              default=os.path.join(os.path.expanduser("~"), "template.jcli"),
              help="Use the jinja2 engine to write out the list of issues.")
def run_cmd(name, output, sort, max_issues, issue_offset, len_,
            template_file):
    """Execute a saved query by name."""
    jobj = connector.JiraConnector()

    saved = jobj._config_get_nested("jira.saved_queries")
    if not saved or name not in saved:
        raise click.UsageError(f"Saved query '{name}' not found.")

    jql = saved[name].get("jql")
    if not jql:
        raise click.UsageError(f"Saved query '{name}' has no JQL defined.")

    if output == 'template' and not os.path.isfile(template_file):
        raise click.UsageError(f"Invalid template file {template_file}.")

    jobj.login()

    issues = jobj._query_issues(jql, issue_offset, max_issues)
    final = format_issue_output(jobj, issues, output, len_, sort,
                                template_file)
    click.echo(final)


@click.command(
    name='build'
)
@click.option('--name', required=True, help="Name for the saved query")
@click.option('--description', 'desc', default="",
              help="Description of the saved query")
@click.option('--assignee', type=str, default=None,
              help="The name of the assignee (use '' for current user)")
@click.option('--project', type=str, default=None,
              help="The name of the project")
@click.option("--closed", type=bool, default=False,
              help="Whether to include closed issues")
@click.option("--jql", type=str, default=None,
              help="JQL to use for the query.")
@click.option("--matching-eq", multiple=True, nargs=2,
              help="Custom JQL pair")
@click.option("--matching-neq", multiple=True, nargs=2,
              help="Custom JQL pair")
@click.option("--matching-contains", multiple=True, nargs=2,
              help="Custom JQL pair")
@click.option("--matching-not", multiple=True, nargs=2,
              help="Custom JQL pair")
@click.option("--matching-in", multiple=True, nargs=2,
              help="Custom JQL pair")
@click.option("--matching-gt", multiple=True, nargs=2,
              help="Custom JQL pair")
@click.option("--matching-lt", multiple=True, nargs=2,
              help="Custom JQL pair")
@click.option("--matching-ge", multiple=True, nargs=2,
              help="Custom JQL pair")
@click.option("--matching-le", multiple=True, nargs=2,
              help="Custom JQL pair")
@click.option("--mentions", type=bool, is_flag=True, default=False,
              help="Checks for mentions on all issues.")
@click.option("--updated-since", type=str, default=None,
              help="Only issues updated since [ARG]")
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
def build_cmd(name, desc, assignee, project, closed, jql, matching_eq,
              matching_neq, matching_contains, matching_not,
              matching_in, matching_gt, matching_lt, matching_ge,
              matching_le, mentions, updated_since, sort):
    """Build a JQL query from CLI options and save it to the configuration."""
    jobj = connector.JiraConnector()
    jobj.login()

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
        assignee = None
        qd["comment"] = ("~", "currentUser()")
    if updated_since:
        qd["updatedDate"] = (">=", updated_since)

    if sort != "none":
        qd["ORDER BY"] = jobj.order_by_from_string(sort)

    if not jql or jql == '':
        jql = jobj.build_issues_query(assignee, project, closed, fields_dict=qd)

    entry = {"jql": jql}
    if desc:
        entry["description"] = desc

    jobj._config_set_nested(f"jira.saved_queries.{name}", entry)
    jobj._save_cfg()

    click.echo(f"Saved query '{name}': {jql}")


@click.command(
    name='remove'
)
@click.argument('name')
def remove_cmd(name):
    """Remove a saved query from the configuration."""
    jobj = connector.JiraConnector(load_safe=True)

    saved = jobj._config_get_nested("jira.saved_queries")
    if not saved or name not in saved:
        raise click.UsageError(f"Saved query '{name}' not found.")

    jobj._config_clear_nested(f"jira.saved_queries.{name}")
    jobj._save_cfg()

    click.echo(f"Removed saved query '{name}'.")
