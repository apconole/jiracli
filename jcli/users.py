import click
from jcli import connector
import json as JSON


@click.command(
    name='find'
)
@click.option('--by', type=click.Choice(["name", "username", "email"]),
              default="name", help="Which field to search (default is 'name').")
@click.option('--json', is_flag=True, default=False)
@click.argument('user', type=str)
def users_find_cmd(by, json, user):
    jobj = connector.JiraConnector()
    jobj.login()

    if by == "name":
        userlist = jobj.find_users_by_name(user)
    elif by == "username":
        userlist = jobj.find_users_by_username(user)
    elif by == "email":
        userlist = jobj.find_users_by_email(user)

    if not json:
        click.echo(f"Found {len(userlist)} users.")
        click.echo(f"{userlist}")
    else:
        users = []
        for user in userlist:
            userD = {"name": user.displayName, "username": user.name,
                     "id": user.key}
            users.append(userD)
        click.echo(f"{JSON.dumps(users)}")
