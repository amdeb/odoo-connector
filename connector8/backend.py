# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Guewen Baconnier
#    Copyright 2013 Camptocamp SA
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from functools import partial
from collections import namedtuple
from .exception import ConnectorUnitError


class Backend(object):
    """ A backend represents a system to interact with,
    like Magento, Prestashop, Redmine, ...

    It owns 3 properties:

    .. attribute:: name

        Name of the service, for instance 'magento'

    .. attribute:: version

        The version of the service. For instance: '1.7'

    .. attribute:: parent

        A parent backend. When no
        :py:class:`connector.ConnectorUnit`
        is found for a backend, it will search it in the `parent`.

    The Backends structure is a key part of the framework,
    but is rather simple.

    * A ``Backend`` instance holds a registry of
      :py:class:`connector.ConnectorUnit` classes
    * It can return an appropriate
      :py:class:`connector.ConnectorUnit` to use for a task
    * If no :py:class:`connector.ConnectorUnit`
      is registered for a task, it will ask it to its direct parent
      (and so on)

    The Backends support 2 different extension mechanisms. One is more
    horizontal - across the versions - and the other would be more vertical
    as it allows to modify the behavior for 1 version of backend.

    For the sake of the example, let's say we have theses backend versions::

                 <Magento>
                     |
              -----------------
              |               |
        <Magento 1.7>   <Magento 2.0>
              |
        <Magento with specific>

    And here is the way they are declared in Python::

        magento = Backend('magento')
        magento1700 = Backend(parent=magento, version='1.7')
        magento2000 = Backend(parent=magento, version='2.0')

        magento_specific = Backend(parent=magento1700, version='1.7-specific')

    In the graph above, ``<Magento>`` will hold all the classes shared between
    all the versions.  Each Magento version (``<Magento 1.7>``, ``<Magento
    2.0>``) will use the classes defined on ``<Magento>``, excepted if they
    registered their own ones instead. That's the same for ``<Magento with
    specific>`` but this one contains customizations which are specific to an
    instance (typically you want specific mappings for one instance).

    Here is how you would register classes on ``<Magento>`` and another on
    ``<Magento 1.7>``::

        @magento
        class Synchronizer(ConnectorUnit):
            _model_name = 'res.partner'

        @magento
        class Mapper(ConnectorUnit):
            _model_name = 'res.partner'

        @magento1700
        class Synchronizer1700(Synchronizer):
            _model_name = 'res.partner'

    Here, the called on :py:meth:`~get_class` of ``magento1700``
    would return::

        magento1700.get_class(Synchronizer, session, 'res.partner')
        # => Synchronizer1700
        magento1700.get_class(Mapper, session, 'res.partner')
        # => Mapper

    This is the vertical extension mechanism, it says that each child version
    is able to extend or replace the behavior of its parent.

    .. note:: when using the framework, you won't need to call
              :py:meth:`~get_class`, usually, you will call
              :py:meth:`connector.Environment.get_connector_unit`.

    The vertical extension is the one you will probably use the most, because
    most of the things you will change concern your custom adaptations or
    different behaviors between the versions of the backend.

    However, some time, we need to change the behavior of a connector, by
    installing an addon. For example, say that we already have an
    ``ImportMapper`` for the products in the Magento Connector. We create a
    generic addon to handle the catalog in a more advanced manner. We
    redefine an ``AdvancedImportMapper``, which should be used when
    the addon is installed. This is the horizontal extension mechanism.

    Replace a :py:class:`connector.ConnectorUnit` by another one
    in a backend::

        @magento(replacing=ImportMapper)
        class AdvancedImportMapper(ImportMapper):
            _model_name = 'product.product'
    """

    _backend_registry = set()

    # used in unit test
    @staticmethod
    def _clear_backend_registry():
        Backend._backend_registry.clear()

    @staticmethod
    def get_backend(name, version=None, default=None):
        """ Return an instance of :py:class:`backend.Backend`
        for a ``name`` and a ``version``. If not found,
        return default or None if no default specified

        :param name: name of the service to return
        :type name: str
        :param version: version of the service to return
        :type version: str
        """

        for backend in Backend._backend_registry:
            if backend.match(name, version):
                return backend
        else:
            return default

    # Represents an entry for a service class in a backend
    # the first element is a service class while the
    # second is a list of other service classes that replace
    # this service class
    _ConnectorUnitEntry = namedtuple(
        '_ConnectorUnitEntry',  ['service_class', 'replaced_by']
    )

    def __init__(self, name=None, version=None, parent=None):
        if name is None and parent is None:
            raise ValueError('A name or a parent is expected')

        self.name = name if name is not None else parent.name
        self.version = version
        self.parent = parent

        #  a list of registered service classes
        # that are instances of _ConnectorUnitEntry
        self._class_entries = []

        Backend._backend_registry.add(self)

    def match(self, name, version):
        """Used to find the backend for a service and a version"""
        return (self.name == name and
                self.version == version)

    def __str__(self):
        if self.version:
            return 'Backend(\'%s\', \'%s\')' % (self.name, self.version)
        return 'Backend(\'%s\')' % self.name

    def __repr__(self):
        if self.version:
            return '<Backend \'%s\', \'%s\'>' % (self.name, self.version)
        return '<Backend \'%s\'>' % self.name

    def _add_candidate(self, candidates, entry,
                       base_class, session, model_name):
        service_class = entry.service_class
        is_installed = session.is_module_installed(
            service_class.odoo_module_name
        )
        is_subclass = issubclass(service_class, base_class)
        is_model_matched = service_class.match(model_name)

        if is_installed and is_subclass and is_model_matched:
            candidates.add(entry.service_class)

    def _get_classes(self, base_class, session, model_name):
        def follow_replacing(entries):
            candidates = set()
            for entry in entries:
                replacings = None
                if entry.replaced_by:
                    replacings = follow_replacing(entry.replaced_by)
                    if replacings:
                        candidates.update(replacings)
                # If all the classes supposed to replace the current class
                # have been discarded, the current class is a candidate.
                # It happens when the entries in 'replaced_by' are
                # in modules not installed.
                if not replacings:
                    self._add_candidate(
                        candidates, entry, base_class, session, model_name)
            return candidates

        matching_classes = follow_replacing(self._class_entries)
        if not matching_classes and self.parent:
            matching_classes = self.parent._get_classes(
                base_class, session, model_name
            )

        return matching_classes

    def get_service_class(self, base_class, session, model_name):
        """ Find a matching subclass of ``base_class`` from the registered
        classes.

        :param base_class: class (and its subclass) to search in the registry
        :type base_class: :py:class:`connector.ConnectorUnit`
        :param session: current session
        :type session: :py:class:`session.ConnectorSession`
        :param model_name: the model name to search for
        :type: str
        """

        matching_classes = self._get_classes(
            base_class, session, model_name)

        if len(matching_classes) == 1:
            return matching_classes.pop()

        if not matching_classes:
            return None

        # too many matches
        error_template = '{0} service classes found for class type {1} ' \
            'for session: {2} and model name {3}. ' \
            'Matched classes including 1st: {4}.  2nd: {5}'
        error_message = error_template.format(
            len(matching_classes),
            base_class,
            session,
            model_name,
            matching_classes.pop(),
            matching_classes.pop()
        )
        raise ConnectorUnitError(error_message)

    def _register_replace(self, replacing, entry):
        """ add entry to the replaced_by part of replacing class(es) """

        if not hasattr(replacing, '__iter__'):
            replacing = [replacing]

        for replacing_class in replacing:
            for replaced_entry in self._class_entries:
                if replaced_entry.service_class is replacing_class:
                    replaced_entry.replaced_by.append(entry)
                    break

    def register_service_class(self, service_class, replacing=None):
        """ Register a class in the backend.

        :param service_class: the ConnectorUnit class class to register
        :type service_class: :py:class:`connector.ConnectorUnit`
        :param replacing: optional, the ConnectorUnit class to replace
        :type replacing: :py:class:`connector.ConnectorUnit`
        """

        entry = Backend._ConnectorUnitEntry(
            service_class=service_class,
            replaced_by=[]
        )

        # register only if it is new
        for registered in self._class_entries:
            if service_class is registered.service_class:
                return

        # add replacing first thus never replace itself
        if replacing:
            self._register_replace(replacing, entry)

        self._class_entries.append(entry)

    def __call__(self, service_class=None, replacing=None):
        """ Backend decorator used to register a backend ConnectorUnit class

        For a backend ``magento`` declared like this::

            magento = Backend('magento')

        A :py:class:`connector8.connector.ConnectorUnit`
        (like a binder, a synchronizer, a mapper, ...) can be
        registered as follows::

            @magento
            class MagentoBinder(Binder):
                _model_name = 'a.model'
                # other stuff

        Thus, by doing::

            magento.get_service_class(Binder, 'a.model')

        We get the correct class ``MagentoBinder``.

        Any ``ConnectorUnit`` can be replaced by another one::

            @magento(replacing=MagentoBinder)
            class MagentoBinder2(Binder):
                _model_name = 'a.model'
                # other stuff

        This is useful when working on an Odoo module which should
        alter the original behavior of a connector for an existing backend.

        :param service_class: the ConnectorUnit class class to register
        :type service_class: :py:class:`connector.ConnectorUnit`
        :param replacing: optional, a ConnectorUnit class or several
        classes (in an iterable container)to replace
        :type replacing: :py:class:`connector.ConnectorUnit`
        """

        if service_class is None:
            return partial(self, replacing=replacing)

        self.register_service_class(service_class, replacing=replacing)
        return service_class
