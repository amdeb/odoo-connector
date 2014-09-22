# -*- coding: utf-8 -*-

from functools import partial


class Backend(object):
    """ A backend represents a system to be integrated with,
    like Amazon, eBay, Magento, Prestashop, ...

    It owns 2 properties:

    .. attribute:: name

        Name of the service, for instance 'magento' or 'magento 1.7'

    .. attribute:: parent

        A parent backend of a backend. It is optional.

    The Backend functions are rather simple.

    * The Backend maintains a registry of all backends that
        can be searched using static class method
        :py:meth:`Backend.get_backend`.
    * A backend can have an optional `parent` backend.
    * A backend has two list of service classes: a normal list and
        a replaced list. All service classes in normal list are searched
        before those in the replaced list.
    * When a service class is not found in a backend,
        the backend's `parent` will be searched.
    * The service class can be replaced into the replaced list or
        can be removed from all lists.

    For exmaple, let's say we have theses backend versions::

                 <Magento>
                     |
              -----------------
              |               |
        <Magento 1.7>   <Magento 2.0>
              |
        <Magento with specific>

    And here is the way they are declared in Python::

        magento = Backend('magento')
        magento1700 = Backend('magento 1.7', magento)
        magento2000 = Backend('magento 2.0', magento)

        magento_specific = Backend('magento 1.7-specific', magento1700, )

    In the graph above, ``<Magento>`` can bu used to hold all the
    service classes shared between all its child versions.
    When search a service class, the current backend is searched. If
    the current backend doesn't have the service class, parent backend
    will be searched.

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

    Here, the called on :py:meth:`~get_service_class` of ``magento1700``
    would return::

        magento1700.get_service_class(Synchronizer, 'res.partner')
        # => Synchronizer1700
        magento1700.get_service_class(Mapper, 'res.partner')
        # => Mapper

    ..note:: :py:meth:the `~get_serivce_class` search most recently
            registered service class first. It stops searching when
            the first service_class matches searching conditions.

    The backend supports `replacing` operation: a replaced
    service class is searched after all normal service classes are
    search. There are two ways to replace a service class: call
    a backend's `~replace_serivce_class` or put as a parameter
    when register a service class.

        megento.replace_service_class(ImportMapper)

        @magento(replacing=ImportMapper)
        class AdvancedImportMapper(ImportMapper):
            _model_name = 'product.product'

    The backend' :py:meth:`remove_service_class` removes a registered
    service class.

    """

    _backend_registry = set()

    # used in unit test
    @staticmethod
    def _clear_backend_registry():
        Backend._backend_registry.clear()

    @staticmethod
    def get_backend(name, default=None):
        """ Return an instance for a ``name``.

        :param name: name of the service to return
        :type name: str
        :param default: a default returned if the specified name is not found
        :type default: Backend
        """

        search = (backend for backend in Backend._backend_registry
                  if backend.name == name)
        return next(search, default)

    def _validate_params(self, name, parent):
        if not isinstance(name, basestring):
            raise ValueError('A backend name (a string) is expected')
        if parent and not isinstance(parent, self.__class__):
            raise ValueError('A parent must be an instance of Backend')

    def _init_instance_attributes(self, name, parent):
        self.name = name
        self.parent = parent

        # a list of normal registered service classes
        self._class_entries = []
        # a list of replaced classes that are search after normal classes
        self._replaced_entries = []

    def __init__(self, name, parent=None):
        self._validate_params(name, parent)
        self._init_instance_attributes(name, parent)
        Backend._backend_registry.add(self)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return ((self.name == other.name)
                    and (self.parent == other.parent))
        return False

    def __repr__(self):
        template = "<{0}: {1} {2}>"
        return template.format(self.__class__, self.name, self.parent)

    def _is_matched(self, entry, base_class, model_name):
        is_installed = entry.is_module_installed()
        is_subclass = issubclass(entry, base_class)
        is_model_matched = entry.match(model_name)

        return is_installed and is_subclass and is_model_matched

    def _get_matched(self, entries, base_class, model_name):
        search = (
            entry for entry in entries
            if self._is_matched(entry, base_class, model_name)
        )
        return next(search, None)

    def _get_service_class(self, base_class, model_name):
        """ Find a matching subclass from both entries"""

        return (
            self._get_matched(self._class_entries, base_class, model_name)
            or self._get_matched(
                self._replaced_entries, base_class, model_name)
        )

    def get_service_class(self, base_class, model_name):
        """ Find a matching class from here and parent.

        :param base_class: class (and its subclass) to search in the registry
        :type base_class: :py:class:`connector.ConnectorUnit`
        :param model_name: the model name to search for
        :type: str
        """

        matched = self._get_service_class(base_class, model_name)
        if not matched and self.parent:
            matched = self.parent.get_service_class(
                base_class, model_name)
        return matched

    def replace_service_class(self, replacing):
        """ move a service class to replaced entries"""

        if not hasattr(replacing, '__contains__'):
            replacing = [replacing]

        for replaced in replacing:
            if replaced in self._class_entries:
                self._class_entries.remove(replaced)
            if replaced not in self._replaced_entries:
                self._replaced_entries.insert(0, replaced)

    def remove_service_class(self, service_class):
        """ remove the service class from both entries """

        if service_class in self._class_entries:
            self._class_entries.remove(service_class)
        if service_class in self._replaced_entries:
            self._replaced_entries.remove(service_class)

    def register_service_class(self, service_class, replacing=None):
        """ Register a class in the backend.

        First move all replacing service class into replaced entries.
        If the new service_class exists in any entries, remove it.
        Then add the service class to the front.

        :param service_class: the ConnectorUnit class class to register
        :type service_class: :py:class:`connector.ConnectorUnit`
        :param replacing: optional, the ConnectorUnit class to replace
        :type replacing: :py:class:`connector.ConnectorUnit`
        """

        if replacing:
            self.replace_service_class(replacing)

        self.remove_service_class(service_class)
        self._class_entries.insert(0, service_class)

    def __call__(self, service_class=None, replacing=None):
        """ Backend decorator used to register a service class

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
