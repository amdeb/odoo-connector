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

    The Backend structure is rather simple.

    * The Backend maintains a registry of all backends that
        can be searched using static class method
        :py:meth:`Backend.get_backend`
    * A ``Backend`` instance holds a registry of
        service classes that are sub class of the
        :py:class:`connector.ConnectorUnit` class
    * It returns an installed service class
        for a specified base class and a model name
    * When a service class is not found in a backend,
        the backend's `parent` will be searched if the backend
        has a parent defined. The search goes up to the backend parent
        chain until a service class is found or no parent is available.


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
    When serach a service class, the current backend is searched. If
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

        magento1700.get_service_class(Synchronizer, session, 'res.partner')
        # => Synchronizer1700
        magento1700.get_service_class(Mapper, session, 'res.partner')
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
        """ Return an instance of :py:class:`backend.Backend`
        for a ``name``. If not found, return default or
        None if no default specified

        :param name: name of the service to return
        :type name: str
        :param default: a default returned if the specified name is not found
        :type default: Backend
        """

        for backend in Backend._backend_registry:
            if backend.name == name:
                return backend
        else:
            return default

    def __init__(self, name, parent=None):
        if not isinstance(name, basestring):
            raise ValueError('A backend name (a string) is expected')

        self.name = name
        self.parent = parent

        # a list of normal registered service classes
        self._class_entries = []
        # a list of replaced classes that are search after normal classes
        self._replaced_entries = []

        Backend._backend_registry.add(self)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return ((self.name == other.name)
                    and (self.parent == other.parent))

    def __repr__(self):
        template = "<{0}: {1} {2}>"
        return template.format(self.__class__, self.name, self.parent)

    def _get_matched(self, entries, base_class, session, model_name):

        for entry in entries:
            is_installed = session.is_module_installed(
                entry.odoo_module_name
            )
            is_subclass = issubclass(entry, base_class)
            is_model_matched = entry.match(model_name)

            if is_installed and is_subclass and is_model_matched:
                return entry

    def get_service_class(self, base_class, session, model_name):
        """ Find a matching subclass of ``base_class`` from the registered
        service classes.If not found, try replaced service classes

        :param base_class: class (and its subclass) to search in the registry
        :type base_class: :py:class:`connector.ConnectorUnit`
        :param session: current session
        :type session: :py:class:`session.ConnectorSession`
        :param model_name: the model name to search for
        :type: str
        """

        matched = self._get_matched(
            self._class_entries, base_class, session, model_name)
        if not matched:
            matched = self._get_matched(
                self._replaced_entries, base_class, session, model_name)
        return matched

    def replace_service_class(self, replacing):
        """ remove a service class from class entries and
        add it to replaced entries
        """

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
