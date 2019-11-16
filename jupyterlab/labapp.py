# coding: utf-8
"""A tornado based Jupyter lab server."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import json
import os
import os.path as osp
from os.path import join as pjoin
import sys
import warnings

from jupyter_core.application import JupyterApp, base_aliases
# TODO ECH Flags are failing with nbclassic, but succeed with jupyter_sever
# from jupyter_server.serverapp import aliases, flags
from nbclassic.notebookapp import aliases, flags
from jupyter_server.utils import url_path_join as ujoin
from traitlets import Bool, Instance, Unicode

from ._version import __version__
from .debuglog import DebugLogFileMixin
from .extension import load_config, load_jupyter_server_extension
from .commands import (
    build, clean, get_app_dir, get_app_version, get_user_settings_dir,
    get_workspaces_dir, AppOptions,
)
from .coreconfig import CoreConfig

from jupyter_server.extension.application import ExtensionApp

build_aliases = dict(base_aliases)
build_aliases['app-dir'] = 'LabBuildApp.app_dir'
build_aliases['name'] = 'LabBuildApp.name'
build_aliases['version'] = 'LabBuildApp.version'
build_aliases['dev-build'] = 'LabBuildApp.dev_build'
build_aliases['minimize'] = 'LabBuildApp.minimize'
build_aliases['debug-log-path'] = 'DebugLogFileMixin.debug_log_path'

build_flags = dict(flags)

version = __version__
app_version = get_app_version()
if version != app_version:
    version = '%s (dev), %s (app)' % (__version__, app_version)


class LabBuildApp(JupyterApp, DebugLogFileMixin):
    version = version
    description = """
    Build the JupyterLab application

    The application is built in the JupyterLab app directory in `/staging`.
    When the build is complete it is put in the JupyterLab app `/static`
    directory, where it is used to serve the application.
    """
    aliases = build_aliases
    flags = build_flags

    # Not configurable!
    core_config = Instance(CoreConfig, allow_none=True)

    app_dir = Unicode('', config=True,
        help="The app directory to build in")

    name = Unicode('JupyterLab', config=True,
        help="The name of the built application")

    version = Unicode('', config=True,
        help="The version of the built application")

    dev_build = Bool(None, allow_none=True, config=True,
        help="Whether to build in dev mode. Defaults to True (dev mode) if there are any locally linked extensions, else defaults to False (prod mode).")

    minimize = Bool(True, config=True,
        help="Whether to use a minifier during the Webpack build (defaults to True). Only affects production builds.")

    pre_clean = Bool(False, config=True,
        help="Whether to clean before building (defaults to False)")

    def start(self):
        parts = ['build']
        parts.append('none' if self.dev_build is None else
                     'dev' if self.dev_build else
                     'prod')
        if self.minimize:
            parts.append('minimize')
        command = ':'.join(parts)

        app_dir = self.app_dir or get_app_dir()
        app_options = AppOptions(
            app_dir=app_dir, logger=self.log, core_config=self.core_config
        )
        self.log.info('JupyterLab %s', version)
        with self.debug_logging():
            if self.pre_clean:
                self.log.info('Cleaning %s' % app_dir)
                clean(app_options=app_options)
            self.log.info('Building in %s', app_dir)
            build(name=self.name, version=self.version,
                  command=command, app_options=app_options)


clean_aliases = dict(base_aliases)
clean_aliases['app-dir'] = 'LabCleanApp.app_dir'


class LabCleanApp(JupyterApp):
    version = version
    description = """
    Clean the JupyterLab application

    This will clean the app directory by removing the `staging` and `static`
    directories.
    """
    aliases = clean_aliases

    # Not configurable!
    core_config = Instance(CoreConfig, allow_none=True)

    app_dir = Unicode('', config=True, help='The app directory to clean')

    def start(self):
        clean(app_options=AppOptions(
            app_dir=self.app_dir, logger=self.log,
            core_config=self.core_config))


class LabPathApp(JupyterApp):
    version = version
    description = """
    Print the configured paths for the JupyterLab application

    The application path can be configured using the JUPYTERLAB_DIR
        environment variable.
    The user settings path can be configured using the JUPYTERLAB_SETTINGS_DIR
        environment variable or it will fall back to
        `/lab/user-settings` in the default Jupyter configuration directory.
    The workspaces path can be configured using the JUPYTERLAB_WORKSPACES_DIR
        environment variable or it will fall back to
        '/lab/workspaces' in the default Jupyter configuration directory.
    """

    def start(self):
        print('Application directory:   %s' % get_app_dir())
        print('User Settings directory: %s' % get_user_settings_dir())
        print('Workspaces directory: %s' % get_workspaces_dir())


class LabWorkspaceExportApp(JupyterApp):
    version = version
    description = """
    Export a JupyterLab workspace

    If no arguments are passed in, this command will export the default
        workspace.
    If a workspace name is passed in, this command will export that workspace.
    If no workspace is found, this command will export an empty workspace.
    """
    def start(self):
        app = LabApp(config=self.config)
        base_url = app.base_url
        config = load_config(app)
        directory = config.workspaces_dir
        app_url = config.app_url

        if len(self.extra_args) > 1:
            print('Too many arguments were provided for workspace export.')
            self.exit(1)

        raw = (app_url if not self.extra_args
               else ujoin(config.workspaces_url, self.extra_args[0]))
        slug = slugify(raw, base_url)
        workspace_path = pjoin(directory, slug + WORKSPACE_EXTENSION)

        if osp.exists(workspace_path):
            with open(workspace_path) as fid:
                try:  # to load the workspace file.
                    print(fid.read())
                except Exception as e:
                    print(json.dumps(dict(data=dict(), metadata=dict(id=raw))))
        else:
            print(json.dumps(dict(data=dict(), metadata=dict(id=raw))))


class LabWorkspaceImportApp(JupyterApp):
    version = version
    description = """
    Import a JupyterLab workspace

    This command will import a workspace from a JSON file. The format of the
        file must be the same as what the export functionality emits.
    """
    workspace_name = Unicode(
        None,
        config=True,
        allow_none=True,
        help="""
        Workspace name. If given, the workspace ID in the imported
        file will be replaced with a new ID pointing to this
        workspace name.
        """
    )

    aliases = {
        'name': 'LabWorkspaceImportApp.workspace_name'
    }

    def start(self):
        app = LabApp(config=self.config)
        base_url = app.base_url
        config = load_config(app)
        directory = config.workspaces_dir
        app_url = config.app_url
        workspaces_url = config.workspaces_url

        if len(self.extra_args) != 1:
            print('One argument is required for workspace import.')
            self.exit(1)

        workspace = dict()
        with self._smart_open() as fid:
            try:  # to load, parse, and validate the workspace file.
                workspace = self._validate(fid, base_url, app_url, workspaces_url)
            except Exception as e:
                print('%s is not a valid workspace:\n%s' % (fid.name, e))
                self.exit(1)

        if not osp.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                print('Workspaces directory could not be created:\n%s' % e)
                self.exit(1)

        slug = slugify(workspace['metadata']['id'], base_url)
        workspace_path = pjoin(directory, slug + WORKSPACE_EXTENSION)

        # Write the workspace data to a file.
        with open(workspace_path, 'w') as fid:
            fid.write(json.dumps(workspace))

        print('Saved workspace: %s' % workspace_path)

    def _smart_open(self):
        file_name = self.extra_args[0]

        if file_name == '-':
            return sys.stdin
        else:
            file_path = osp.abspath(file_name)

            if not osp.exists(file_path):
                print('%s does not exist.' % file_name)
                self.exit(1)

            return open(file_path)

    def _validate(self, data, base_url, app_url, workspaces_url):
        workspace = json.load(data)

        if 'data' not in workspace:
            raise Exception('The `data` field is missing.')

        # If workspace_name is set in config, inject the
        # name into the workspace metadata.
        if self.workspace_name is not None:
            if self.workspace_name == "":
                workspace_id = ujoin(base_url, app_url)
            else:
                workspace_id = ujoin(base_url, workspaces_url, self.workspace_name)
            workspace['metadata'] = {'id': workspace_id}
        # else check that the workspace_id is valid.
        else:
            if 'id' not in workspace['metadata']:
                raise Exception('The `id` field is missing in `metadata`.')
            else:
                id = workspace['metadata']['id']
                if id != ujoin(base_url, app_url) and not id.startswith(ujoin(base_url, workspaces_url)):
                    error = '%s does not match app_url or start with workspaces_url.'
                    raise Exception(error % id)

        return workspace


class LabWorkspaceApp(JupyterApp):
    version = version
    description = """
    Import or export a JupyterLab workspace

    There are two sub-commands for export or import of workspaces. This app
        should not otherwise do any work.
    """
    subcommands = dict()
    subcommands['export'] = (
        LabWorkspaceExportApp,
        LabWorkspaceExportApp.description.splitlines()[0]
    )
    subcommands['import'] = (
        LabWorkspaceImportApp,
        LabWorkspaceImportApp.description.splitlines()[0]
    )

    def start(self):
        super().start()
        print('Either `export` or `import` must be specified.')
        self.exit(1)



class LabApp(ExtensionApp):
    version = version

    description = """
    JupyterLab - An extensible computational environment for Jupyter.

    This launches a Tornado based HTML Server that serves up an
    HTML5/Javascript JupyterLab client.

    JupyterLab has three different modes of running:

    * Core mode (`--core-mode`): in this mode JupyterLab will run using the JavaScript
      assets contained in the installed `jupyterlab` Python package. In core mode, no
      extensions are enabled. This is the default in a stable JupyterLab release if you
      have no extensions installed.
    * Dev mode (`--dev-mode`): uses the unpublished local JavaScript packages in the
      `dev_mode` folder.  In this case JupyterLab will show a red stripe at the top of
      the page.  It can only be used if JupyterLab is installed as `pip install -e .`.
    * App mode: JupyterLab allows multiple JupyterLab "applications" to be
      created by the user with different combinations of extensions. The `--app-dir` can
      be used to set a directory for different applications. The default application
      path can be found using `jupyter lab path`.
    """

    examples = """
        jupyter lab                       # start JupyterLab
        jupyter lab --dev-mode            # start JupyterLab in development mode, with no extensions
        jupyter lab --core-mode           # start JupyterLab in core mode, with no extensions
        jupyter lab --app-dir=~/myjupyterlabapp # start JupyterLab with a particular set of extensions
        jupyter lab --certfile=mycert.pem # use SSL/TLS certificate
    """

    aliases['app-dir'] = 'LabApp.app_dir'
    aliases.update({
        'watch': 'LabApp.watch',
    })


    flags['core-mode'] = (
        {'LabApp': {'core_mode': True}},
        "Start the app in core mode."
    )
    flags['dev-mode'] = (
        {'LabApp': {'dev_mode': True}},
        "Start the app in dev mode for running from source."
    )
    flags['watch'] = (
        {'LabApp': {'watch': True}},
        "Start the app in watch mode."
    )


    subcommands = dict(
        build=(LabBuildApp, LabBuildApp.description.splitlines()[0]),
        clean=(LabCleanApp, LabCleanApp.description.splitlines()[0]),
        path=(LabPathApp, LabPathApp.description.splitlines()[0]),
        paths=(LabPathApp, LabPathApp.description.splitlines()[0]),
        workspace=(LabWorkspaceApp, LabWorkspaceApp.description.splitlines()[0]),
        workspaces=(LabWorkspaceApp, LabWorkspaceApp.description.splitlines()[0])
    )

    default_url = Unicode('/lab', config=True,
        help="The default URL to redirect to from `/`")

    override_static_url = Unicode('', config=True, help=('The override url for static lab assets, typically a CDN.'))

    override_theme_url = Unicode('', config=True, help=('The override url for static lab theme assets, typically a CDN.'))

    app_dir = Unicode(get_app_dir(), config=True,
        help="The app directory to launch JupyterLab from.")

    user_settings_dir = Unicode(get_user_settings_dir(), config=True,
        help="The directory for user settings.")

    workspaces_dir = Unicode(get_workspaces_dir(), config=True,
        help="The directory for workspaces")

    core_mode = Bool(False, config=True,
        help="""Whether to start the app in core mode. In this mode, JupyterLab
        will run using the JavaScript assets that are within the installed
        JupyterLab Python package. In core mode, third party extensions are disabled.
        The `--dev-mode` flag is an alias to this to be used when the Python package
        itself is installed in development mode (`pip install -e .`).
        """)

    dev_mode = Bool(False, config=True,
        help="""Whether to start the app in dev mode. Uses the unpublished local
        JavaScript packages in the `dev_mode` folder.  In this case JupyterLab will
        show a red stripe at the top of the page.  It can only be used if JupyterLab
        is installed as `pip install -e .`.
        """)

    watch = Bool(False, config=True,
        help="Whether to serve the app in watch mode")

    # The name of the extension
    extension_name = "jupyterlab"

    # The url that your extension will serve its homepage.
    default_url = '/lab'

    # Should your extension expose other server extensions when launched directly?
    load_other_extensions = True

    # Local path to static files directory.
    static_paths = []

    # Local path to templates directory.
    template_paths = []

    def initialize_settings(self):
        notebookapp_config = self.settings.get('config').get('NotebookApp', None)
        if notebookapp_config:
            confs = list(notebookapp_config.keys())
            self.log.warn("=========================================================================================")
            self.log.warn("You are using NotebookApp settings that be deprecated at the next major notebook release.")
            self.log.warn("Please migrate following settings from NotebookApp to ServerApp: {}".format(confs))
            self.log.warn("Read more on https://...")
            self.log.warn("=========================================================================================")
            warnings.warn(
                "NotebookApp configuration is deprecated. Migrate them to ServerApp",
                DeprecationWarning, stacklevel=2,
            )

    def initialize_handlers(self):
        """Load any extensions specified by config.

        Import the module, then call the load_jupyter_server_extension function,
        if one exists.

        If the JupyterLab server extension is not enabled, it will
        be manually loaded with a warning.

        The extension API is experimental, and may change in future releases.
        """
        c = load_config(self)
        self.static_paths = [c.static_dir]
        self.template_paths = [c.templates_dir]
        if not self.serverapp.jpserver_extensions.get('jupyterlab', False):
            msg = 'JupyterLab server extension not enabled, manually loading...'
            self.log.warning(msg)
            load_jupyter_server_extension(self)

#-----------------------------------------------------------------------------
# Main entry point
#-----------------------------------------------------------------------------

main = launch_new_instance = LabApp.launch_instance

if __name__ == '__main__':
    main()
