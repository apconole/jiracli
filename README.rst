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
