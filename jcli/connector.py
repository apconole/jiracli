import datetime
import getpass
from jcli import utils
from jira import JIRA
from jira.exceptions import JIRAError
from jira.resources import User
from jira.utils import json_loads
import jira
import json
import os
import pathlib
import pprint
import re
import time
import types
import urllib
import yaml


try:
    import browser_cookie3

    def get_browser_cookies(server_info, spawned=False):
        orig_url = server_info
        if server_info.startswith('https://'):
            server_info = server_info[8:]
        if server_info.startswith('http://'):
            server_info = server_info[7:]
        for check in [browser_cookie3.chrome, browser_cookie3.chromium,
                      browser_cookie3.firefox]:
            cookies = check(domain_name=server_info)
            for cookie in cookies:
                if cookie.name in ['DWRSESSIONID', 'JSESSIONID',
                                   'JiraSDSamlssoLoginV2']:
                    return cookies
        if not spawned:
            try:
                import webbrowser
                print("Attempting web redirection...")
                webbrowser.open(orig_url + '/login')
                print("Retrying to pull cookies for the next minute...")

                for _ in range(60):
                    cookies = get_browser_cookies(server_info, True)
                    if cookies:
                        return cookies
                    time.sleep(1)

            except:
                pass
            print("Failed to pull cookies.")
            return None
        return None
except:
    def get_browser_cookies(server_info):
        return None


class JiraConnector(object):
    def __init__(self, config_file=None, load_safe=False):
        self.config_file = config_file or self._default_config_file()
        self.config = self._load_cfg(load_safe)
        self.report_weights = None
        self.jira = None
        self.last_call_time = 0  # Store last call timestamp

    def _ratelimit(self):
        current_time = time.time()
        elapsed_time = current_time - self.last_call_time

        call_interval = int(self.get_default_str("call_interval", "500"))
        wait_time = int(self.get_default_str("wait_time", "500"))

        if not call_interval:
            return

        if (elapsed_time * 1000) < call_interval:
            time.sleep(wait_time / 1000)

        self.last_call_time = elapsed_time

    def _load_cfg(self, load_safe):
        """Load a config yaml"""
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            config = {'jira': {}}

        if not load_safe and 'jira' not in config:
            raise ValueError("Missing jira section in config yaml")
        if not load_safe and 'server' not in config['jira']:
            raise ValueError("Missing server for jira config yaml")

        return config

    def _default_config_file(self):
        home_dir = os.path.expanduser("~")
        return os.path.join(home_dir, '.jira.yml')

    def _config_get_nested(self, key_path):
        config = self.config
        keys = key_path.split(".")
        for key in keys:
            if isinstance(config, dict):
                config = config.get(key)
            else:
                return None
        return config

    def _config_set_nested(self, key_path, value):
        keys = key_path.split(".")
        d = self.config
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
        return True

    def _config_clear_nested(self, key_path):
        keys = key_path.split(".")
        d = self.config
        for key in keys[:-1]:
            d = d.get(key)
            if d is None:
                return  # Key path doesn't exist
        d.pop(keys[-1], None)

    def _save_cfg(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            yaml.safe_dump(self.config, f)

    def _login(self):

        if self.jira is not None:
            # Hope this deletes the connection properly
            self.jira = None

        if 'auth' not in self.config:
            self.config['auth'] = {}

        auth_type = 'cookie_harvest'

        if 'type' in self.config['auth']:
            auth_type = self.config['auth']['type']

        username = None
        if auth_type == 'api':
            if 'key' not in self.config['auth']:
                raise ValueError("Missing 'key' for 'api' auth type")
            token = self.config['auth']['key']
            if 'pat' in self.config['auth'] and bool(self.config['auth']['pat']):
                self.jira = JIRA(self.config['jira'], token_auth=token)
        elif auth_type == 'kerberos':
            kerberos_options = None
            if 'kerberos_options' in self.config['auth']:
                kerberos_options = self.config['auth']['kerberos_options']
            self.jira = JIRA(self.config['jira'], kerberos=True,
                             kerberos_options=kerberos_options)
        elif auth_type == 'password':
            if 'password' not in self.config['auth']:
                token = getpass.getpass(prompt="Enter your Jira password: ")
            else:
                token = self.config['auth']['password']
        elif auth_type == 'authinfo':
            authinfo_file = None
            for f in ["~/.netrc", "~/.authinfo", "~/.authinfo.gpg"]:
                authinfo_file_tmp = os.path.expanduser(f)
                if not os.path.exists(authinfo_file_tmp):
                    continue
                authinfo_file = authinfo_file_tmp

            if not authinfo_file:
                raise ValueError("ERROR: No authinfo file to search.")

            jira_server = \
                urllib.parse.urlparse(self.config['jira']['server']).hostname

            entry = utils.get_authinfo_entry(authinfo_file, jira_server)
            if not entry:
                raise ValueError(f"ERROR: No authinfo entry for {jira_server}")

            if 'token' in self.config['auth'] and \
               bool(self.config['auth']['token']):
                self.jira = JIRA(self.config['jira'],
                                 token_auth=entry.get("password"))
            else:
                username = entry.get("login")
                token = entry.get("password")
        elif auth_type == 'cookie_harvest':
            cookies = get_browser_cookies(self.config['jira']['server'])
            if not cookies:
                raise ValueError("ERROR: No browser cookies detected (or browser_cookies3 not installed).")
            self.jira = JIRA(server=self.config['jira']['server'],
                             options={"cookies": cookies})
        else:
            raise ValueError(f"Unknown auth type: {auth_type}")

        if self.jira is None:
            if username is None:
                username = self.config['auth']['username']
            self.jira = JIRA(self.config['jira'], basic_auth=(username,
                                                              token))
            self._ratelimit()

    def login(self):
        cached_creds = pathlib.Path(f"/tmp/.{getpass.getuser()}.jirasess")
        if cached_creds.is_file():
            # found a cached credentials file
            pass
        else:
            throw_code = 0
            try:
                self._login()
            except jira.exceptions.JIRAError as je:
                throw_code = je.status_code

            if throw_code:
                if throw_code == 401:
                    raise RuntimeError(
                        "Error logging in: double check your key, and login.")
                else:
                    raise RuntimeError(f"Error logging in: {throw_code}")

            # pprint.pprint(vars(self.jira))
            # pprint.pprint(vars(self.jira._session))

    def user_sprint_field(self):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        # default field is called 'Sprint' for now.
        sprint_field = "Sprint"

        if 'issues' not in self.config['jira']:
            return sprint_field

        issues_cfg = self.config['jira']['issues']
        for issue in issues_cfg:
            if 'sprint' in issue:
                if bool(issue['sprint']):
                    sprint_field = issue['name']
        return sprint_field

    def get_default_str(self, key, default="") -> str:
        if 'default' not in self.config['jira'] or \
           key not in self.config['jira']['default']:
            return default

        return self.config['jira']['default'][key]

    def load_renderer(self, render_text):
        if not render_text or not len(render_text):
            raise RuntimeError("Render text is 'none'")

        allowed_builtins = {
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "sum": sum,
            "min": min,
            "max": max,
            "re": re,
            "sorted": sorted,
            # Add more if needed
        }

        try:
            render_func = eval(render_text, {"__builtins__": allowed_builtins}, {})
            if not callable(render_func):
                raise RuntimeError(f"Expr: {render_text} did not evaluate properly.")
            return render_func
        except Exception as e:
            raise ValueError(f"Invalid expr: {e}")

    def myself(self):
        if self.jira is None:
            raise RuntimeError("Need to log-in first")

        try:
            self._ratelimit()
            result = self.jira.myself()
        except JIRAError as e:
            result = {'key': f"ERROR retrieving information {e}", "name": f"Error: {e}"}

        return result['name']

    def _query_issues(self, query='', startAt=0, maxResults=100) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        issues_list = self.jira.search_issues(query, startAt, maxResults)
        return issues_list

    def get_issue(self, issue_identifier):
        """Retrieve a Jira issue based on either key or ID."""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        # Check if the issue_identifier is a numeric string (ID) or an
        # alphanumeric string (key)
        if issue_identifier.isdigit():
            # If numeric string, assume it's the issue ID
            issue = self.jira.issue(issue_identifier)
        else:
            # Otherwise, assume it's the issue key
            issue = self.jira.issue(issue_identifier, fields='*all')

        # Add support for the EZ Agile Planning Poker extension
        if issue is not None and 'eausm' not in self.config['jira'] or \
           bool(self.config['jira']['eausm']):
            # Check for the EZ Agile Planning Poker ext on the server
            EAUSM_url = self.jira.server_url + \
                f"/rest/eausm/latest/planningPoker/{issue.id}"

            self._ratelimit()
            r = self.jira._session.get(EAUSM_url)
            try:
                EAUSM_json = json_loads(r)
                issue.raw['fields']['eausm'] = EAUSM_json
            except:
                # set the in-memory config to false for now.  Future
                # requests won't trigger EAUSM code any more.
                self.config['jira']['eausm'] = False
        return issue

    def get_states_for_issue(self, issue_identifier) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        state_names = []
        issue = self.get_issue(issue_identifier)

        self._ratelimit()
        transitions = self.jira.transitions(issue)

        state_names = [t['to']['name'] for t in transitions]
        return state_names

    def set_state_for_issue(self, issue, status):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(issue, str):
            issue = self.get_issue(issue)

        self._ratelimit()
        self.jira.transition_issue(issue, transition=status)

    def issue_url(self, issue_identifier) -> str:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        # Construct the URL for the issue
        issue_url = f"{self.jira._options['server']}/browse/{issue_identifier}"

        return issue_url

    def add_comment(self, issue_identifier, comment_body, visibility):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        issue = self.get_issue(issue_identifier)

        if isinstance(visibility, str) and visibility != 'all':
            visibility = {'type': 'group', 'value': visibility}
        elif isinstance(visibility, str):
            visibility = None

        if issue is not None:
            self._ratelimit()
            self.jira.add_comment(issue, comment_body, visibility)

    def get_comment(self, issue_identifier, comment_id):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        if isinstance(comment_id, str) and comment_id == "last":
            return self.jira.comments(issue_identifier)[-1]
        comment = self.jira.comment(issue_identifier, comment_id)
        return comment

    def in_reply_to_start(self, comment):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if comment is None or not isinstance(comment, jira.resources.Comment):
            raise ValueError("Comment needs to be a comment type.")

        replyto = "On {{date}}, {{author_name}} writes:"
        if 'default' in self.config['jira'] and \
           'replyto' in self.config['jira']['default']:
            replyto = self.config['jira']['default']['replyto']

        replyto = replyto.replace("{{date}}", f"{comment.updated}")
        replyto = replyto.replace("{{author_name}}",
                                  f"{comment.author.displayName}")
        replyto = replyto.replace("{{author_id}}", f"{comment.author.name}")
        replyto = replyto.replace("{{comment_id}}", f"{comment.id}")

        if not replyto.endswith("\n"):
            replyto += "\n"

        return replyto

    def add_watcher(self, issue_identifier, watcher):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        issue = self.get_issue(issue_identifier)
        if issue is not None:
            self._ratelimit()
            self.jira.add_watcher(issue, watcher)

    def del_watcher(self, issue_identifier, watcher):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        issue = self.get_issue(issue_identifier)
        if issue is not None:
            self._ratelimit()
            self.jira.remove_watcher(issue, watcher)

    def _order_by_from_string(self, order_by_string) -> str:
        orders = [("none", ""),
                  ("prio-asc", "priority asc"),
                  ("prio-desc", "priority desc")]
        if not order_by_string:
            order_by_string = "none"

        for t in orders:
            if t[0] == order_by_string:
                return t[1]

        if "-" not in order_by_string and " " not in order_by_string:
            raise ValueError(f"Invalid order string '{order_by_string}'")

        if " " in order_by_string:
            return order_by_string

        lr = order_by_string.split("-")
        return f"{lr[0]} {lr[1]}"

    def order_by_from_string(self, order_by_string) -> str:
        orders = self._order_by_from_string(order_by_string)

        if orders != "":
            if "ORDER BY" not in orders:
                return f" ORDER BY {orders}"
            else:
                return f" {orders}"

        return ""

    def build_issues_query(self, assignee=None, project=None, closed=None,
                           fields_dict=None, **kwargs):
        """
        Returns a query for a list of issues based on provided criteria

        Args:
        - assignee (str): Assignee of the issues
        - project (str): Project name for the issues
        - closed (bool): Whether or not to include closed issues in the query
        - fields_dict (dict): Dictionary of fields, where key is the field to
                              match, and value may either be a string (with implied
                              equality), or a tuple of (operator, value)
        - kwargs: Additional kwargs to add to the query

        Returns:
        - str: The query
        """
        query_parts = []

        if assignee is not None:
            if assignee == "":
                assignee = self.myself()
            query_parts.append(f'assignee = "{assignee}"')

        if project is not None:
            query_parts.append(f'project = "{project}"')

        if closed is None or not closed:
            stat_query = "status not in ("
            statuses = ",".join(['"' + s + '"' for s in self.last_states_names()])
            stat_query += statuses
            stat_query += ")"
            query_parts.append(stat_query)

        def additional_args(query_parts, fields) -> list:
            if fields:
                for field, m in fields.items():
                    # need to check for field being custom.
                    if field == "ORDER BY":
                        continue
                    field = self._try_fieldname(field)
                    oper = "="
                    v = m
                    if isinstance(m, tuple):
                        oper = m[0]
                        v = m[1]
                    query_parts.append(f'{field} {oper} {v}')
            return query_parts

        def order_by_find(connector, fields) -> str:
            if fields:
                for field, m in fields.items():
                    if field == "ORDER BY":
                        return connector.order_by_from_string(m)

            return ""

        query_parts = additional_args(query_parts, fields_dict)
        query_parts = additional_args(query_parts, kwargs)

        order_by = order_by_find(self, fields_dict)
        order_by = order_by if order_by != "" else order_by_find(self, kwargs)

        return " AND ".join(query_parts) + order_by

    def _jira_fields(self):
        if not hasattr(self, "_fields"):
            self._ratelimit()
            self._fields = self.jira.fields()

        return self._fields

    def _fetch_custom_fields(self) -> dict:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if not hasattr(self, "_custom_field_mapping"):
            custom_fields = self._jira_fields()
            self._custom_field_mapping = {field['id']: field['name']
                                          for field in custom_fields if field['custom']}

        return self._custom_field_mapping

    def requested_fields(self) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        requested = []

        if 'issues' not in self.config['jira']:
            return requested

        issue_config = self.config['jira']['issues']
        for cfg in issue_config:
            if 'field' in cfg and cfg['field'] and 'name' in cfg['field']:
                if 'exclude' not in cfg['field'] or not cfg['field']['exclude']:
                    requested.append(cfg['field']['name'])

        return requested

    def excluded_fields(self) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        excluded = []

        if 'issues' not in self.config['jira']:
            return excluded

        issue_config = self.config['jira']['issues']
        for cfg in issue_config:
            if 'field' in cfg and cfg['field'] and 'name' in cfg['field']:
                if 'exclude' in cfg['field'] and cfg['field']['exclude']:
                    excluded.append(cfg['field']['name'])

        return excluded

    def _try_fieldname(self, fieldname) -> str:
        """Tries to pick the fieldname for a passed in field"""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        fields = self._fetch_custom_fields()

        if fieldname[0] == "^":
            return fieldname[1:]

        for k in fields:
            if fieldname == fields[k]:
                return k

        return fieldname

    def _get_field(self, issue, fieldname, substruct=None):
        """Get a raw field value for an issue."""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(issue, str):
            issue = self.get_issue(issue)

        casecmp = bool(self.get_default_str('case_sensitive', "true"))
        for rawfield in issue.raw['fields']:
            if not casecmp:
                if rawfield.lower() != fieldname.lower():
                    continue
                else:
                    # Since we are not caring about case, we found a
                    # match, so 'force' the case correctly.
                    fieldname = rawfield
            elif rawfield != fieldname:
                continue

            if issue.raw['fields'][fieldname] is None:
                return "None"
            if isinstance(issue.raw['fields'][fieldname], str):
                return issue.raw['fields'][fieldname]
            elif substruct is not None:
                return issue.raw['fields'][fieldname][substruct]
            else:
                if 'name' in issue.raw['fields'][fieldname]:
                    return issue.raw['fields'][fieldname]['name']
                if isinstance(issue.raw['fields'][fieldname], list):
                    results = []
                    for sf in issue.raw['fields'][fieldname]:
                        if 'name' in sf:
                            results.append(f"{sf['name']}")
                        elif 'vote' in sf:
                            results.append(f"{sf['vote']}")
                    return ",".join(results)
                elif isinstance(issue.raw['fields'][fieldname], dict):
                    return str(issue.raw['fields'][fieldname])
                return "(undecoded)"

        fields = self._fetch_custom_fields()
        val = None
        for field in fields:
            if not casecmp:
                if fields[field].lower() != fieldname.lower():
                    continue
                else:
                    fieldname = field
            elif fields[field] != fieldname:
                continue

            try:
                val = eval(f"issue.fields.{field}")
            except:
                val = None
        return val

    def get_field(self, issue, fieldname, substruct=None) -> str:
        """Get a field value as a string."""
        val = self._get_field(issue, fieldname, substruct)
        if val is None:
            return ""

        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            if 'name' in val:
                return val['name']

        if isinstance(val, jira.resources.PropertyHolder):
            return pprint.pformat(vars(val))

        try:
            return str(val)
        except:
            return "(unknown decode)"

    def get_field_rendered(self, issue, fieldname, substruct=None) -> str:

        val = self.get_field(issue, fieldname, substruct)

        # find the yaml for rendering the field
        issues_config = self._config_get_nested("jira.issues")
        if issues_config:
            for field_conf in issues_config:
                if 'field' not in field_conf:
                    continue
                issue_conf = field_conf['field']
                if not issue_conf or 'name' not in issue_conf or \
                   issue_conf['name'].lower() != fieldname.lower():
                    continue
                if 'render' in issue_conf:
                    rendered = self.load_renderer(issue_conf['render'])
                    val = rendered(val)
        return val

    def _get_field_allowed(self, issue, fieldname) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(issue, jira.resources.Issue):
            issue = issue.key

        meta = self.jira.editmeta(issue)
        fields = meta['fields']
        field = fields.get(fieldname)

        if field and "allowedValues" in field:
            result = []
            for x in field["allowedValues"]:
                parts = []
                if x.get("name") is not None:
                    parts.append(f"\"name\": \"{x['name']}\"")
                if x.get("value") is not None:
                    parts.append(f"\"value\": \"{x['value']}\"")
                result.append(f"- {', '.join(parts)}")
            return result
        return None

    def get_field_allowed(self, issue, fieldname, substruct=None) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(issue, str):
            issue = self.get_issue(issue)

        found = False
        casecmp = bool(self.get_default_str('case_sensitive', "true"))
        for rawfield in issue.raw['fields']:
            if not casecmp:
                if rawfield.lower() != fieldname.lower():
                    continue
                else:
                    fieldname = rawfield
                    found = True
            elif rawfield != fieldname:
                continue

        if found:
            return self._get_field_allowed(issue, fieldname)

        fields = self._fetch_custom_fields()
        for field in fields:
            if not casecmp:
                if fields[field].lower() != fieldname.lower():
                    continue
                else:
                    fieldname = field
                    found = True
            elif fields[field] != fieldname:
                continue

        if found:
            return self._get_field_allowed(issue, fieldname)
        return None

    def find_users_for_name(self, name) -> list:
        """
        Finds the users who match a given display name.
        """
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        return self.jira.search_users(user=name)

    def convert_to_jira_type(self, var_instance, value):
        """
        Converts the input from a JIRA type to a usable type based on
        some kinds of heuristics.

        Arguments:
        - var_instance: an instance of an existing field
        - value: The data to convert

        Returns:
        - The correct type tp put in a dict.
        """
        if isinstance(var_instance, jira.resources.User):
            # Assume the input is a name and look it up
            names = self.find_users_for_name(value)
            if len(names) > 1:
                raise ValueError(f"Ambiguous name {value} with {len(names)} matches.")
            return {"name": names[0].name}

        if isinstance(var_instance, jira.resources.Priority):
            return {"name": value}

        if isinstance(var_instance, list):
            return [{"name": value}]

        if isinstance(var_instance, str):
            return str(value)

        try:
            if 'name' in var_instance:
                return {"name": value}
        except:
            raise ValueError(f"Unable to handle {type(var_instance)}")

    def _proj_key(self, project):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        projects = [p for p in self.jira.projects()
                    if p.name == project or p.key == project]
        if len(projects) != 1:
            raise ValueError(f"Unable to determine a project by {project}.")
        return projects[0].key

    def get_project_default_types(self, project, issue_type):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        project = self._proj_key(project)
        if isinstance(issue_type, str):
            try:
                issue_type = self.jira.issue_type_by_name(issue_type)
            except jira.exceptions.JIRAError:
                raise ValueError(f"Couldn't determine issue type for \"{issue_type}\"")
        self._ratelimit()
        full_fields = self.jira.project_issue_fields(project, issue_type.id)
        return [f.name for f in full_fields]

    def set_field(self, issue, fieldname, val, forced=False):
        """Set the field for an issue to a particular value."""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(issue, str):
            issue = self.get_issue(issue)

        issue_dict = {}
        casecmp = bool(self.get_default_str('case_sensitive', "true"))
        for rawfield in issue.raw['fields']:
            if not casecmp:
                if rawfield.lower() != fieldname.lower():
                    continue
                else:
                    fieldname = rawfield
            elif rawfield != fieldname:
                continue
            f = eval(f"issue.fields.{fieldname}")
            if not isinstance(f, types.NoneType) and not forced:
                val = self.convert_to_jira_type(f, val)
            elif not forced:
                if fieldname == "assignee":
                    val = {"name": val}
            else:
                val = eval(val)
            issue_dict = {fieldname: val}
            break

        fields = self._fetch_custom_fields()
        for field in fields:
            if not casecmp:
                if fields[field].lower() != fieldname.lower():
                    continue
                else:
                    fieldname = field
            elif fields[field] != fieldname:
                continue

            if not forced:
                val = self.convert_to_field_type(field, val)
            else:
                val = eval(val)
            issue_dict = {field: val}

        self._ratelimit()
        issue.update(issue_dict)

    def object_convert(self, field_value):
        listed = False
        v = field_value
        if v.startswith('[') and v.endswith(']'):
            listed = True
            v = v[1:-1]

        for t in ["value", "name", "id"]:
            if v.lower().startswith(f'{{"{t}') or \
               v.lower().startswith(f'{{\'{t}'):
                v = eval(v)

        if listed:
            v = [v]

        return v

    def _convert_to_field_type(self, field_id, field_value):
        """Convert the field value to the appropriate type."""

        field_type = self._fetch_field_type_mapping().get(field_id)
        if field_type is None:
            raise ValueError(f"Field type for field with ID '{field_id}' not found.")

        if field_type == "string":
            return field_value
        elif field_type == "dict":
            if ':' not in field_value:
                return {"name": field_value}
            else:
                return eval(field_value)
        elif field_type == "user":
            n = self.find_users_for_name(field_value)
            if len(n) != 1:
                raise ValueError(f"Unable to convert \"{field_value}\" to unambiguous name - {len(n)} results.")
            return {'name': n[0].name}
        elif field_type == "number":
            return float(field_value)
        elif field_type == "date":
            return datetime.strptime(field_value, "%Y-%m-%d").date()
        elif field_type == "array":
            parser = field_value.replace(' ', '').replace('\t', '').replace('\r', '')
            return [self.object_convert(parser)]
        # Add more conversions for other field types as needed

    def convert_to_field_type(self, field_id, field_value):
        try:
            v = self._convert_to_field_type(field_id, field_value)
        except ValueError:
            v = self.object_convert(field_value)
        return v

    def _fetch_field_type_mapping(self):
        """Fetch field type mapping from Jira."""
        if hasattr(self, '_field_type_mapping'):
            # Get field type mapping from Jira if not cached
            return self._field_type_mapping

        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        custom_fields = self._jira_fields()
        field_type_mapping = {field['id']: field['schema']['type']
                              for field in custom_fields if field['custom']}
        field_type_mapping["assignee"] = "user"
        field_type_mapping["priority"] = "dict"

        self._field_type_mapping = field_type_mapping
        return self._field_type_mapping

    def _last_states_list(self) -> list:
        """Try to get all the final states"""

        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        statuses = self._get_statuses()
        final_status = []

        for status in statuses:
            if status.statusCategory.key == 'done':
                final_status.append(status)

        return final_status

    def last_states_names(self) -> list:

        final_statuses = [s.name for s in self._last_states_list()]
        return final_statuses

    def _get_statuses(self):

        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if hasattr(self, '_cached_statuses'):
            return self._cached_statuses

        self._cached_statuses = self.jira.statuses()
        return self._cached_statuses

    def get_status_detail(self, statusId):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(statusId, jira.resources.Status):
            statusId = statusId.id

        statuses = self._get_statuses()
        for status in statuses:
            if statusId == status.id or statusId == status.name:
                return status
        return None

    def issue_matches_conditions(self, issue, matching):
        for field, expected in matching.items():
            actual = self.get_field(issue, field)
            if isinstance(expected, list):
                if isinstance(actual, list):
                    if not any(val in actual for val in expected):
                        return False
                else:
                    if actual not in expected:
                        return False
            else:
                if actual != expected:
                    return False
        return True

    def filter_issue(self, issue, filtering):
        if 'match' in filtering:
            if not self.issue_matches_conditions(issue, filtering['match']):
                return False

        if 'or' in filtering:
            if not any(self.issue_matches_conditions(issue,
                                                     clause.get('match', {}))
                       for clause in filtering['or']):
                return False

        return True

    def report_filter_issues(self, list_name, issues):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if 'reporting' not in self.config['jira'] or \
           'filters' not in self.config['jira']['reporting'] or \
           list_name not in self.config['jira']['reporting']['filters']:
            raise RuntimeError(f"No reporting section for {list_name}")

        filter_config = self.config['jira']['reporting']['filters'][list_name]
        return [i for i in issues if self.filter_issue(i, filter_config)]

    def report_compute_score(self, issue):
        score = 0

        for field, spec in self.report_weights.items():
            field_weight = spec['field_weight']
            value_weights = spec['value_weights']
            value = self.get_field(issue, field)
            if value in value_weights:
                score += field_weight + value_weights[value]

        return score

    def report_sort_issue_list(self, issues):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if self.report_weights is None:
            self.report_weights = {}

            if 'reporting' in self.config['jira'] and \
               'ordering' in self.config['jira']['reporting']:
                for field, data in self.config['jira']['reporting']['ordering'].items():
                    self.report_weights[field] = {
                        'field_weight': data.get('weight', 1),
                        'value_weights': data.get('values', {})
                    }

        return sorted(issues, key=lambda x: -self.report_compute_score(x))

    def report_filters(self):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if 'reporting' in self.config['jira'] and \
           'filters' in self.config['jira']['reporting']:
            result = list(self.config['jira']['reporting']['filters'].keys())
        else:
            result = []

        return result

    def fetch_boards(self, limit=0) -> list:
        """Try to get all the boards configured in jira"""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        if limit > 0:
            return self.jira.boards(0, limit)

        return self.jira.boards(0, 0)

    def fetch_board_by_name(self, boardname):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        return self.jira.boards(name=boardname)

    def fetch_sprints_by_board(self, board) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(board, str):
            name = board
            board = self.fetch_board_by_name(name)
            found = None
            if len(board) != 1:
                # cycle through and see if there is a real result with this name
                for b in board:
                    if b.name == name:
                        found = b
            else:
                found = board[0]

            if not found:
                raise ValueError(f"Invalid results for {name} - ambiguous?")
            board = found

        try:
            self._ratelimit()

            start_at = 0
            max_results = 50

            while True:
                sprints = self.jira.sprints(board.raw['id'], startAt=start_at,
                                            maxResults=max_results)
                if not sprints:
                    break
                for sprint in sprints:
                    yield sprint
                if len(sprints) < max_results:
                    return None

                start_at += max_results

        except JIRAError:
            # not all boards support sprints, so ignore it
            sprints = []

        return sprints

    def _fetch_board_config_object(self, board):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(board, str):
            name = board
            board = self.fetch_board_by_name(name)
            found = None
            if len(board) != 1:
                # cycle through and see if there is a real result with this name
                for b in board:
                    if b.name == name:
                        found = b
            else:
                found = board[0]

            if not found:
                raise ValueError(f"Invalid results for {name} - ambiguous?")
            board = found

        # Got the board ID - let's get the REST details
        # Don't look at this too long .. it will make you sad.
        self._ratelimit()
        cfg = self.jira.find(f"../../agile/1.0/board/{board.raw['id']}/configuration")
        return cfg

    def fetch_issues_by_board(self, board, issue_offset, max_issues) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        # This is a silly way of doing things - we need to query for all the
        # epic types and board id details.  BUT, JQL doesn't let us query by
        # board ID, so we need to actually pull the board configuration,
        # without a proper pythonic API and decode it manually to get the
        # correct JQL.
        r = self._fetch_board_config_object(board)
        self._ratelimit()
        f = self.jira.filter(r.filter)
        # let's check if the query includes closed issues:
        query = f.jql

        if 'status' not in query:
            oldquery = query
            query = "status not in (" + \
                ",".join(['"' + s + '"' for s in self.last_states_names()]) + \
                ") AND "
            if " order " in oldquery.lower():
                ns = utils.ireplace("order", ") order", oldquery)
                query += "(" + ns

        issues_in_epics = self._query_issues(query, issue_offset, max_issues)

        return issues_in_epics

    def fetch_column_config_by_board(self, board) -> dict:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")
        r = self._fetch_board_config_object(board)

        cols = r.columnConfig.columns

        ret = {}
        for c in cols:
            ret[c.name] = [self.get_status_detail(status)
                           for status in c.statuses]

        return ret

    def fetch_jql_config_by_board(self, board):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")
        r = self._fetch_board_config_object(board)
        self._ratelimit()
        f = self.jira.filter(r.filter)

        return f.jql

    def fetch_quickfilters_by_board(self, board):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(board, str):
            name = board
            board = self.fetch_board_by_name(name)
            found = None
            if len(board) != 1:
                # cycle through and see if there is a real result with this name
                for b in board:
                    if b.name == name:
                        found = b
            else:
                found = board[0]

            if not found:
                raise ValueError(f"Invalid results for {name} - ambiguous?")
            board = found

        # Boards are a total hack, and this is also sad.
        # Rather than a direct link somewhere to quickfilters, we need to
        # use the greenhopper endpoint to find the quickfilter config
        self._ratelimit()
        cfg = self.jira.find(f"../../greenhopper/1.0/rapidviewconfig/editmodel.json?rapidViewId={board.raw['id']}")
        if 'quickFilterConfig' in cfg.raw:
            return cfg.quickFilterConfig
        return None

    def fetch_issues_by_board_qf(self, board, issue_offset, max_issues, filter) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(board, str):
            name = board
            board = self.fetch_board_by_name(name)
            found = None
            if len(board) != 1:
                # cycle through and see if there is a real result with this name
                for b in board:
                    if b.name == name:
                        found = b
            else:
                found = board[0]

            if not found:
                raise ValueError(f"Invalid results for {name} - ambiguous?")
            board = found

        fid = None
        filts = self.fetch_quickfilters_by_board(board)
        if not filts:
            return []

        for f in filts.quickFilters:
            if f.name == filter:
                fid = f.id

        if not fid:
            raise ValueError(f"Unknown query: {filter}")

        self._ratelimit()
        # Now query issues by the most absurd interface:
        resp = self.jira.find(f"../../greenhopper/1.0/xboard/work/allData.json?rapidViewId={board.raw['id']}&activeQuickFilters={fid}")

        if 'issuesData' in resp.raw:
            return resp.issuesData.issues

        return []

    def create_issue(self, issue_dict):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        result = self.jira.create_issue(issue_dict)
        self.last_issue = result
        return result

    def _find_users_by_key(self, key):
        user = User(self.jira._options, self.jira._session, _query_param='key')
        self._ratelimit()
        user.find(key)
        return [user]

    def _find_users_by_term(self, searchTerm):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        return self.jira.search_users(user=searchTerm)

    def _find_users(self, term):
        users = self._find_users_by_term(term)
        users = users if len(users) else self._find_users_by_key(term)
        return users

    def find_users_by_name(self, named):
        return self._find_users(named)

    def find_users_by_username(self, named):
        return self._find_users(named)

    def find_users_by_email(self, named):
        return self._find_users(named)

    def _groups(self):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        return self.jira.groups()

    def _components(self, project):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        return self.jira.project(project).components

    def fetch_attachment(self, attachmentid, target):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        attachment = self.jira.attachment(attachmentid)
        self._ratelimit()
        data = attachment.get()
        with open(target, 'wb') as f:
            f.write(data)

    def upload_attachment(self, issue, attachment_file, name):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        self._ratelimit()
        self.jira.add_attachment(issue.id, attachment_file, name)

    def add_issue_link(self, issue, target, title=None, link_type=None, isinward=False):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if not target.startswith("http://") and not target.startswith("https://"):
            tgtcheck = self.get_issue(target)
            self._ratelimit()
            link_types = self.jira.issue_link_types()
            if tgtcheck is None:
                raise ValueError(
                    f"Target {target} looks like an issue, but no issue matches.")
            if not link_type or not any(t.name == link_type for t in link_types):
                raise ValueError(
                    f"Invalid link type.  Please specify one of {','.join([t.name for t in link_types])}.")

            inwardissue = target if not isinward else issue
            outwardissue = issue if not isinward else target
            comment = None
            if title:
                comment = {"body": title}

            self._ratelimit()
            self.jira.create_issue_link(link_type, inwardissue, outwardissue, comment)
        else:
            if not title:
                title = target
            link = {"url": target, "title": title}
            self._ratelimit()
            self.jira.add_simple_link(issue, link)

    def eausm_vote_issue(self, issue, vote):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(issue, str):
            issue = self.get_issue(issue)

        if not issue:
            raise RuntimeError("Invalid issue")

        vote = int(vote)

        EAUSM_url = f"{self.jira.server_url}/rest/eausm/latest/planningPoker/vote"
        if 'eausm' not in self.config['jira'] or \
           bool(self.config['jira']['eausm']):
            payload = {"issueId": issue.id, "vote": vote}
            self._ratelimit()
            self.jira._session.put(EAUSM_url, data=json.dumps(payload))
        else:
            raise RuntimeError("Voting by this client is disabled - check your jira yml.")

    def jira_text_field_to_md(self, jira_text):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if not jira_text:
            return jira_text

        if 'default' not in self.config['jira'] or \
           'markdown' not in self.config['jira']['default'] or \
           not bool(self.config['jira']['default']['markdown']):
            return jira_text

        # Convert any COMMENT references before anything else
        # There are lots of patterns that can match, so we need to make this
        # early on in the parsing
        jira_comment_pattern = re.compile(r'\[(.*?)\|(https?://.*?/browse/([A-Z]+-\d+)\?focusedId=(\d+).*?)\]')
        text = jira_comment_pattern.sub(r'[\1](\3#\4)', jira_text)

        text = utils.jira_to_md(text)
        return text

    def md_text_to_jira_text_field(self, md_text):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if not md_text:
            return md_text

        if 'default' not in self.config['jira'] or \
           'markdown' not in self.config['jira']['default'] or \
           not bool(self.config['jira']['default']['markdown']):
            return md_text

        serverurl = self.jira.server_url
        if not serverurl.endswith('/'):
            serverurl = serverurl + '/'

        markdown_comment_pattern = re.compile(r'\[(.*?)\]\(([A-Z]+-\d+)#(\d+)\)')
        text = markdown_comment_pattern.sub(
            lambda m: f"[{m.group(1)}|{serverurl}browse/{m.group(2)}?focusedId={m.group(3)}&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-{m.group(3)}]",
            md_text
        )
        text = utils.md_to_jira(text)
        return text
