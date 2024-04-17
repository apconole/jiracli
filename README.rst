=======
jiracli - A tool for interacting with JIRA on the command line.
=======

What is jiracli
--------------

`jiracli` is a python based framework for interacting with JIRA via the
command line interface.  The use is intended for JIRA users who don't
enjoy using a web based interface to JIRA and would rather use their
familiar editors and interaction tools.

`jiracli` makes use of the click framework, and the Atlassian JIRA
python framework to provide functionality.


Installing
----------

Currently, `jiracli` is a development-only version, and doesn't have much
support for distribution.  In order to install it, clone and run *pip install*::

  $ git clone https://github.com/apconole/jiracli.git
  $ cd jiracli
  $ pip install -e .

This will put the main `jiracli` utility `jcli` into your path.

Using
-----

First, you'll need to populate a jira yaml file that the internal jira
connector class will use to connect to the jira server.  To do this,
you'll want to use the example found in the *examples/* directory.

You'll want to change the authentication information, and you probably
will want to set specific fields to be included with issue information
(depending on what custom fields your JIRA projects use such as
'Story Points', etc).  Once you've set up the basic stuff, you can list
your issues with::

  $ jcli login
  $ jcli myself

And that should display your username, which shows that the connector
is properly configured.

One other convenient change to make to your environment is to use
`auto-click-auto` to generate a shell completion.  If you've installed
the auto-click-auto package, and use bash - you can simply run::

  $ eval $(_JCLI_COMPLETE=bash_source jcli)

And your shell will have autocomplete for the `jcli` utility.

Additionally, there is the ability to run in interactive shell mode,
provided you've installed the `click-shell` package.  In that case,
you can run in interactive mode with::

  $ jcli shell-cmd
  jcli> help

This will give an interactive interface to the jcli suite of
commands.

Interfacing with issues
-----------------------

Querying Issues
---------------

The default display for issues looks something like::

  $ jcli issues list
  +---------+------------+------------+--------------------+--------+----------+
  | key     | project    | priority   | summary            | status | assignee |
  +---------+------------+------------+--------------------+--------+----------+
  | BUG-123 | PROJMAIN   | Normal     | A normal bug       | New    | a@b.com  |
  | BUG-1   | PROJMAIN   | Undefined  | This is some ot... | Plan   | a@b.com  |
  | FEAT-1  | PROJEXTRA  | High       | Add another foo... | To Do  | a@b.com  |
  +---------+------------+------------+--------------------+--------+----------+

This default view presents the table of JIRA issue tickets assigned to the
current user.  The query that it uses is very basic, and only looks at those
tickets assigned to the current user, in all projects, that are not in a
"final" state.

The view can be tuned with a specific jql by using the `--jql` option::

  $ jcli issues list --jql="\"Project\" = \"PROJEXTRA\" AND assignee=\"b@b.com\""
  +---------+------------+------------+--------------------+--------+----------+
  | key     | project    | priority   | summary            | status | assignee |
  +---------+------------+------------+--------------------+--------+----------+
  | FEAT-3  | PROJEXTRA  | Normal     | Add a list of t... | Start  | b@b.com  |
  +---------+------------+------------+--------------------+--------+----------+

Additionally, the different contains and match options can help to build a
JQL query (`--matching-eq`, `--matching-neq`, `--matching-contains`,
`--matching-not`, `--matching-in`) for finer tuned queries to list isues.

As an example, let's say we want to find all the issues for which the custom
field "Reponse Needed" had the users A or B set::

  $ jcli issues list --assignee=- \
    --matching-in "\"Response Needed\"" "(\"$(jcli myself)\", \"b@b.com\")"
  +---------+------------+------------+--------------------+--------+----------+
  | key     | project    | priority   | summary            | status | assignee |
  +---------+------------+------------+--------------------+--------+----------+
  | BUG-123 | PROJMAIN   | Normal     | A normal bug       | New    | a@b.com  |
  | BUG-124 | PROJMAIN   | High       | The system caug... | QE     | b@b.com  |
  +---------+------------+------------+--------------------+--------+----------+

This output can also be formatted as CSV and used in scripts such as::

  $ for issue in $(jcli issues list --assignee=- --output=csv \
    --matching-in "\"Response Needed\"" "(\"$(jcli myself)\", \"b@b.com\")" |\
    tail -n +2 | cut -d, -f1); do
      notify-send "Issue Needs Response" "$(echo Issue Id: $issue)"
    done

This will call notify-send for all issues on the platform where the field
for "Response Needed" includes the current user or 'b@b.com' user.

Display
-------

Interacting with issues usually involves adding comments, and transitioning
through states.  Occasionally, specific fields will need to be modified to
set up specific values.

Reading an issue is a simple `show` command::

  $ jcli issues show BUG-123
  +-----------------------------------------------------------------------------+
  | BUG-123    | PROJMAIN             | PROJMAIN                                |
  +-----------------------------------------------------------------------------+
  | priority: Normal               | status: New                                |
  +-----------------------------------------------------------------------------+
  | URL: https://tickets.b.com/browse/BUG-123                                   |
  +-----------------------------------------------------------------------------+
  | summary:                                                                    |
  | -------                                                                     |
  | A normal bug
  +-----------------------------------------------------------------------------+

  | Description:                                                                |
  |-----------------------------------------------------------------------------|
  | Description of problem:                                                     |
  | Just a normal bug that can happen when a user does foo-bar                  |
  > Comments:
  | Author: B Dev                                | 2023-09-14T07:28:41.000+0000 |
  |-----------------------------------------------------------------------------|
  | I wanted to try and solve this bug but there is an issue when the system ha |
  | s no activity - do we need to do something about this?                      |
  +-----------------------------------------------------------------------------+

This display includes comments, and will include any custom fields configured
in the Jira yaml preference file.

Another option would be to display the raw server side data of the issue::

  $ jcli issues sho

Commenting
----------

Adding a comment should be easy::

  $ jcli issues add-comment BUG-123

This will use the *EDITOR* environment variable to spawn an editor against a
temporary file which will be pushed to the issue as a comment.  Alternatively,
the **add-comment** command can accept a `--comment` option to fill a comment
from the command line directly.

Setting fields
--------------

Setting a specific field looks like::

  $ jcli issues set-field BUG-123 "Priority" "Normal"
  Updated BUG-123, set Priority High -> Normal

To move an issue to a different status, JIRA requires the use of a transition.
The valid transitions for an issue can be determined by::

  $ jcli issues states BUG-123
  ['New', 'Start', 'Post', 'QE', 'Done']

Setting the state can be done by::

  $ jcli issues set-status BUG-123 Post
  done.
