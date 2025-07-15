import click
from jcli import connector


@click.command(name='clear')
@click.argument("key")
def clear_config_cmd(key):
    """Clear a configuration entry from the jira yaml configuration.

    KEY is the dot-notation key in the yaml to clear.
    """
    jobj = connector.JiraConnector()
    jobj._config_clear_nested(key)
    jobj._save_cfg()
    click.echo(f"# {key} cleared")


@click.command(name='get')
@click.argument("key")
def get_config_cmd(key):
    """Display a configured value, if one is set.

    KEY is the dot-notation key in the yaml.
    """
    jobj = connector.JiraConnector()

    v = jobj._config_get_nested(key)

    # need to compare with None vs just 'not v'
    # due to some variables being boolean
    if v is None:
        click.echo(f"# {key} is not set.")
    else:
        click.echo(f"{key} = {v}")


@click.command(name='set')
@click.argument("key")
@click.argument("value")
@click.option("--forced", is_flag=True, default=False,
              help="Pass 'value' to a python eval() before storing the value.")
def set_config_cmd(key, value, forced):
    """Set a configuration key to the value specified.

    KEY is the dot-notation key in the yaml to set.  It will be created
    if it doesn't already exist.

    You can use the 'forced' flag to do complex python statements that will
    be evaluated before writing.
    """
    jobj = connector.JiraConnector()
    if forced:
        value = eval(value)
    jobj._config_set_nested(key, value)
    jobj._save_cfg()
    click.echo(f"{key} = {value}")
