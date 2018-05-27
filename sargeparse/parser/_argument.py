import os
import re
import logging

from sargeparse.parser.context_manager import CheckKwargs

LOG = logging.getLogger(__name__)


class Argument:
    _custom_parameters = ['default', 'global', 'envvar', 'config_path']

    def __init__(self, definition, **kwargs):
        definition = definition.copy()

        with CheckKwargs(kwargs) as d:
            subcommand = d.pop('subcommand')
            self._show_warnings = d.pop('show_warnings')
            self._prefix_chars = d.pop('prefix_chars')

        self.names = None
        self.dest = None
        self.add_argument_kwargs = definition

        self._process_add_argument_kwargs(for_subcommand=subcommand)

    def get_add_argument_kwargs_without_custom_parameters(self):
        """Return the add_argument() kwargs removing selected keys"""

        kwargs = self.add_argument_kwargs.copy()
        for key in self._custom_parameters:
            kwargs.pop(key, None)

        return kwargs

    def get_value_from_envvar(self, *, default=None):
        """Return value as read from the environment variable, and apply its type"""

        if 'envvar' not in self.add_argument_kwargs:
            return default

        envvar = self.add_argument_kwargs['envvar']
        if envvar not in os.environ:
            return default

        value = os.environ[envvar]
        return self.add_argument_kwargs.get('type', self._same)(value)

    def get_default_value(self, *, default=None):
        """Return default value from add_argument() kwargs"""

        if 'default' not in self.add_argument_kwargs:
            return default

        return self.add_argument_kwargs['default']

    def get_value_from_config(self, config, *, default=None):
        """Return value from dict, and apply its type"""

        if 'config_path' not in self.add_argument_kwargs:
            return default

        config_path = self.add_argument_kwargs['config_path']
        try:
            value = self._get_value_from_path(config, config_path)
        except KeyError:
            return default

        return self.add_argument_kwargs.get('type', self._same)(value)

    def pop_parameter(self, *args):
        """Return a specific parameter from the add_argument() kwargs while removing it"""
        return self.add_argument_kwargs.pop(*args)

    def is_positional(self):
        """Return whether or not an argument is 'positional', being 'optional' the alternative"""

        return self.names[0][0] not in self._prefix_chars

    def validate_schema(self, schema):
        """Return True if the argument satisfies the schema"""

        for k, v in schema.items():
            if k in self.add_argument_kwargs and self.add_argument_kwargs[k] == v:
                continue
            else:
                return False

        return True

    def _process_add_argument_kwargs(self, for_subcommand):
        self._process_common_add_argument_kwargs()

        if for_subcommand:
            self._process_add_argument_kwargs_for_subcommand()
        else:
            self._process_add_argument_kwargs_for_parser()

    def _process_common_add_argument_kwargs(self):
        self.names = self.add_argument_kwargs.pop('names', None)
        if not self.names:
            raise TypeError("Argument 'names' missing or invalid")

        self.dest = self._make_dest_from_argument_names(self.names)

        if not self.add_argument_kwargs.get('help') and self._show_warnings:
            msg = "Missing 'help' in %s. Please add something helpful, or set it to None to hide this warning"
            LOG.warning(msg, self.dest)
            self.add_argument_kwargs['help'] = "WARNING: MISSING HELP MESSAGE"

        if self.is_positional():
            # argparse will raise an exception if the argument is positional and 'dest' is set
            if 'dest' in self.add_argument_kwargs:
                msg = "Positional arguments cannot have a 'dest', remove it from the definition: '{}'".format(
                    self.add_argument_kwargs['dest']
                )
                raise TypeError(msg)

        else:  # argument is optional
            self.add_argument_kwargs.setdefault('dest', self.dest)

    def _process_add_argument_kwargs_for_parser(self):
        self.add_argument_kwargs.setdefault('global', False)

        if self.add_argument_kwargs['global'] and self.is_positional():
            raise TypeError("Positional arguments cannot be 'global': '{}'".format(self.names[0]))

    def _process_add_argument_kwargs_for_subcommand(self):
        if 'global' in self.add_argument_kwargs:
            raise TypeError("'global' arguments are not available in subcommands")

    def _make_dest_from_argument_names(self, names):
        """Get the 'dest' parameter based on the argument names"""

        dest = None

        for name in names:
            if name[0] in self._prefix_chars and not dest:
                dest = name[1:]

            if name[0] not in self._prefix_chars:
                dest = name
                break

            if name[0] in self._prefix_chars and name[0] == name[1]:
                dest = name[2:]
                break

        return dest.replace('-', '_')

    def _get_value_from_path(self, dictionary, path):
        """Return the value for path, where path represent a list of keys in nested dicts separated by '/'"""

        if isinstance(path, str):
            path = re.split(r'(?<!\\)/', path)
        elif not isinstance(path, list):
            path = [path]

        if path:
            key = path[0]
        else:
            raise RuntimeError("Invalid path config_path, it's probably better to use strings")

        if len(path) > 1:
            if key not in dictionary:
                raise KeyError("Path not found")

            return self._get_value_from_path(dictionary[key], path[1:])

        return dictionary[key]

    @staticmethod
    def _same(arg):
        """This is used as the default function for 'type' parameter"""
        return arg
