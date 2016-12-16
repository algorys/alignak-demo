#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
alignak_backend_client command line interface::

    Usage:
        {command} [-h]
        {command} [--version]
        {command} [-v] [-c]
                  [-b=url] [-u=username] [-p=password]
                  [-T=template] [-t=type] <action> <item>

    Options:
        -h, --help                  Show this screen.
        -V, --version               Show application version.
        -v, --verbose               Run in verbose mode (more info to display)
        -c, --check                 Check only (dry run), do not change the backend.
        -b, --backend url           Specify backend URL [default: http://127.0.0.1:5000]
        -u, --username=username     Backend login username [default: admin]
        -p, --password=password     Backend login password [default: admin]
        -t, --type=host             Type of the provided item
        -T, --template=template     Template to use for the new item

    Use cases:
        Display help message:
            {command} (-h | --help)

        Display current version:
            {command} -V
            {command} --version

        Add an item in the backend:
            {command} [-b=backend] [-u=username] [-p=password] item

        Add an item in the backend based on a template (default is host):
            {command} [-b=backend] [-u=username] [-p=password] -T template item

        Add an item in the backend based on a template:
            {command} [-b=backend] [-u=username] [-p=password] -T template -t host item

        Exit code:
            0 if required operation succeeded
            1 if backend access is denied (check provided username/password)
            2 if element creation failed (missing template,...)

            64 if command line parameters are not used correctly
"""
from __future__ import print_function

import os
import json
import tempfile
import logging

from docopt import docopt, DocoptExit

from alignak_backend_client.client import Backend, BackendException

# Configure logger
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)8s - %(message)s')
# Name the logger to get the backend client logs
logger = logging.getLogger('alignak_backend_client.client')

__version__ = "0.1"

class BackendUpdate(object):
    """
    Class to connect the Alignak backend
    """

    def __init__(self):
        self.logged_in = False

        # Get command line parameters
        args = None
        try:
            args = docopt(__doc__, version=__version__)
        except DocoptExit as exp:
            print("Command line parsing error:\n%s." % (exp))
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 64")
            exit(64)

        logger.debug("Test")
        # Verbose
        self.verbose = False
        if '--verbose' in args and args['--verbose']:
            logger.setLevel('DEBUG')
            self.verbose = True

        # Dry-run mode?
        self.dry_run = args['--check']
        logger.info("Dry-run mode (check only): %s", self.dry_run)

        # Backend URL
        self.backend = None
        self.backend_url = args['--backend']
        logger.info("Backend URL: %s", self.backend_url)

        # Backend authentication
        self.username = args['--username']
        self.password = args['--password']
        logger.info("Backend login with credentials: %s/%s", self.username, self.password)

        # Get the item type
        self.item_type = args['--type']
        logger.info("Item type: %s", self.item_type)

        # Get the action to execute
        self.action = args['<action>']
        logger.info("Action to execute: %s", self.action)
        if self.action not in ['add', 'get', 'delete']:
            print("Action '%s' is not authorized." % (self.action))
            exit(64)

        # Get the new item to create
        self.item = args['<item>']
        logger.info("Host to get created: %s", self.item)

        # Get the template to use
        self.template = args['--template']
        logger.info("Using the template: %s", self.template)

        # Not yet any data
        self.data = None

    def initialize(self):
        """
        Login on backend with username and password

        :return: None
        """
        try:
            logger.info("Authenticating...")
            # Backend authentication with token generation
            # headers = {'Content-Type': 'application/json'}
            # payload = {'username': self.username, 'password': self.password, 'action': 'generate'}
            self.backend = Backend(self.backend_url)
            self.backend.login(self.username, self.password)
        except BackendException as e:
            print("Backend exception: %s" % str(e))

        if self.backend.token is None:
            print("Access denied!")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 1")
            exit(1)

        logger.info("Authenticated.")

        # Default realm
        self.realm_all = ''
        self.default_realm = ''
        realms = self.backend.get_all('realm')
        for r in realms['_items']:
            if r['name'] == 'All' and r['_level'] == 0:
                self.realm_all = r['_id']
                logger.info("Found realm 'All': %s", self.realm_all)

        # Default timeperiods
        self.tp_always = None
        self.tp_never = None
        timeperiods = self.backend.get_all('timeperiod')
        for tp in timeperiods['_items']:
            if tp['name'] == '24x7':
                self.tp_always = tp['_id']
                logger.info("Found TP '24x7': %s", self.tp_always)
            if tp['name'].lower() == 'none' or tp['name'].lower() == 'none':
                self.tp_never = tp['_id']
                logger.info("Found TP 'Never': %s", self.tp_never)

        if self.verbose:
            hosts = self.backend.get_all('host')
            self.hosts_names = sorted([host['name'] for host in hosts['_items']])
            logger.info("Existing hosts: %s", ','.join(self.hosts_names))

            params = {'where': json.dumps({'_is_template': True})}
            templates = self.backend.get_all('host', params=params)
            self.host_templates_names = sorted([template['name'] for template in templates['_items']])
            logger.info("Existing host templates: %s", ','.join(self.hosts_names))

            params = {'where': json.dumps({'_is_template': True})}
            templates = self.backend.get_all('host', params=params)
            self.service_templates_names = sorted([template['name'] for template in templates['_items']])
            logger.info("Existing service templates: %s", ','.join(self.service_templates_names ))

    def get_resource(self, resource_name, name):
        try:
            logger.info("Trying to get %s: '%s'", resource_name, name)

            params = {'where': json.dumps({'name': name})}
            response = self.backend.get(resource_name, params=params)
            if len(response['_items']) > 0:
                response = response['_items'][0]

                logger.info("-> found %s '%s': %s", resource_name, name, response['_id'])

                # Exists in the backend, we got the element
                if not self.dry_run:
                    logger.info(" -> dumping %s: %s", resource_name, name)
                    dump = json.dumps(response, indent=4,
                                      separators=(',', ': '), sort_keys=True)
                    print(dump)
                    try:
                        temp_d = tempfile.gettempdir()
                        path = os.path.join(temp_d, 'alignak-object-dump-%s-%s' %
                                            (resource_name, name))
                        dfile = open(path, "wb")
                        dfile.write(dump)
                        dfile.close()
                    except (OSError, IndexError) as exp:
                        logger.exception("Error when writing the dump file %s : %s", path, str(exp))

                    logger.warning("-> dumped %s: %s", resource_name, name)
                else:
                    logger.info("Dry-run mode: should have dumped an %s '%s'",
                                resource_name, name)

                return True
            else:
                logger.warning("-> %s %s template '%s' not found", resource_name, self.template)
                return False

        except BackendException as e:
            print("Get error for  '%s' : %s" % (resource_name, name))
            logger.exception(e)
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 5")
            return False

        return True

    def delete_resource(self, resource_name, name):
        try:
            logger.info("Trying to get %s: '%s'", resource_name, name)

            params = {'where': json.dumps({'name': name})}
            response = self.backend.get(resource_name, params=params)
            if len(response['_items']) > 0:
                response = response['_items'][0]

                logger.info("-> found %s '%s': %s", resource_name, name, response['_id'])

                # Exists in the backend, we must delete the element...
                if not self.dry_run:
                    headers = {
                        'Content-Type': 'application/json',
                        'If-Match': response['_etag']
                    }
                    logger.info(" -> deleting %s: %s", resource_name, name)
                    self.backend.delete(resource_name + '/' + response['_id'], headers)
                    logger.warning("-> deleted %s: %s", resource_name, name)
                else:
                    response = {'_id': '_fake', '_etag': '_fake'}
                    logger.info("Dry-run mode: should have deleted an %s '%s'",
                                resource_name, name)

                return True
            else:
                logger.warning("-> %s %s template '%s' not found", resource_name, self.template)
                return False

        except BackendException as e:
            print("Deletion error for  '%s' : %s" % (resource_name, name))
            logger.exception(e)
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 5")
            return False

        return True

    def create_update_resource(self, resource_name, name):
        self.update_backend_data = True

        if self.data is None:
            data = {}

        try:
            logger.info("Trying to get %s: '%s'", resource_name, name)

            params = {'where': json.dumps({'name': name})}
            response = self.backend.get(resource_name, params=params)
            if len(response['_items']) > 0:
                response = response['_items'][0]

                logger.info("-> found %s '%s': %s", resource_name, name, response['_id'])

                # Exists in the backend, we should update if required...
                if not self.dry_run:
                    headers = {
                        'Content-Type': 'application/json',
                        'If-Match': response['_etag']
                    }
                    # self.backend.patch(
                    #     resource_name + '/' + response['_id'], item,
                    #     headers=headers, inception=True
                    # )
                    logger.warning("-> %s should be updated and not created: %s",
                                   resource_name, name)
                    return False
            else:
                logger.info("-> %s '%s' not existing, it can be created.", resource_name, name)

                host_template = None
                if self.template is not None:
                    logger.info("Trying to find the %s template: %s", resource_name, self.template)

                    params = {'where': json.dumps({'name': self.template, '_is_template': True})}
                    response = self.backend.get(resource_name, params=params)
                    if len(response['_items']) > 0:
                        host_template = response['_items'][0]

                        logger.info("-> %s template '%s': %s",
                                    resource_name, self.template, host_template['_id'])
                    else:
                        print("-> %s template '%s' not found" % (resource_name, self.template))
                        return False

                # Host data and template information if templating is required
                host_data = {
                    'name': name,
                    '_realm': self.realm_all
                }
                if host_template is not None:
                    host_data.update({'_templates': [host_template['_id']],
                                      '_templates_with_services': True})

                if not self.dry_run:
                    logger.info("Trying to create the %s: %s, with: %s",
                                resource_name, name, host_data)
                    response = self.backend.post(resource_name, host_data, headers=None)
                else:
                    response = {'_id': '_fake', '_etag': '_fake'}
                    logger.info("Dry-run mode: should have created an %s '%s' with %s",
                                resource_name, name, host_data)
                logger.info("Created: '%s': %s, with %s",
                            resource_name, response['_id'], host_data)
        except BackendException as e:
            print("Creation error for  '%s' : %s" % (resource_name, name))
            logger.exception(e)
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 5")
            return False

        return True


def main():
    """
    Main function
    """
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
          "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("backend_import, version: %s" % __version__)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
          "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

    bc = BackendUpdate()
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
          "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    bc.initialize()
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
          "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

    exit_code = 0
    if bc.item and bc.action == 'get':
        item_dump = bc.get_resource(bc.item_type, bc.item)
        if item_dump:
            print("Dumped %s '%s'" % (bc.item_type, bc.item))
        else:
            exit_code = 2
            print("%s '%s' dump failed" % (bc.item_type, bc.item))
            if not bc.verbose:
                print("Set verbose mode to have more information (-v)")

    if bc.item and bc.action == 'add':
        item_creation = bc.create_update_resource(bc.item_type, bc.item)
        if item_creation:
            print("Created %s '%s'" % (bc.item_type, bc.item))
        else:
            exit_code = 2
            print("%s '%s' creation failed" % (bc.item_type, bc.item))
            if not bc.verbose:
                print("Set verbose mode to have more information (-v)")

    if bc.item and bc.action == 'delete':
        item_deletion = bc.delete_resource(bc.item_type, bc.item)
        if item_deletion:
            print("Deleted %s '%s'" % (bc.item_type, bc.item))
        else:
            exit_code = 2
            print("%s '%s' deletion failed" % (bc.item_type, bc.item))
            if not bc.verbose:
                print("Set verbose mode to have more information (-v)")

    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
          "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    main()