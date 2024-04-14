# -*- coding: utf-8 -*-
#
# jcli documentation build configuration file

import jcli

try:
    import sphinx_rtd_theme
    has_rtd_theme = True
except ImportError:
    has_rtd_theme = False

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
needs_sphinx = '1.5'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['sphinx_click.ext', 'reno.sphinxext']

# Add any paths that contain templates here, relative to this directory.
templates_path = []

# The master toctree document.
master_doc = 'contents'

# General information about the project.
project = u'jcli'
copyright = u'2024, Red Hat, Inc'
author = u'Aaron Conole'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '.'.join(jcli.__version__.split('.')[:-1])
# The full version, including alpha/beta/rc tags.
release = jcli.__version__

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# A list of warning types to suppress arbitrary warning messages.
suppress_warnings = ['image.nonlocal_uri']

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
if has_rtd_theme:
    html_theme = 'sphinx_rtd_theme'
