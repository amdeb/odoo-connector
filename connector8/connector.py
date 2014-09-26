# -*- coding: utf-8 -*-

from . import utility

# install the connector itself
utility.install_in_connector()


class MetaConnectorUnit(type):
    """ Metaclass for ConnectorUnit.

    Add a ``model_name`` property and a ``odoo_module_name``
    property to every ControlUnit class. Every ConnectorUnit subclass
    must have a ``_model_name`` defined. The ``odoo_module_name``
    property is used to find the module status (installed or not) of
    a ConnectorUnit subclass.
    """

    @property
    def model_name(cls):
        """
        The ``model_name`` is used to find the class and is mandatory for
        :py:class:`connector.ConnectorUnit` which are registered
        on a :py:class:`backend.Backend`.
        """
        if cls._model_name is None:
            raise NotImplementedError("no _model_name for %s" % cls)
        model_name = cls._model_name
        if not hasattr(model_name, '__iter__'):
            model_name = [model_name]
        return model_name

    def __init__(cls, name, bases, attrs):
        super(MetaConnectorUnit, cls).__init__(name, bases, attrs)
        cls.odoo_module_name = utility.get_odoo_module_name(cls)


class ConnectorUnit(object):
    """Abstract class for each piece of the connector:

    Examples:
        * :py:class:`connector.Binder`
        * :py:class:`connector.unit.mapper.Mapper`
        * :py:class:`connector.unit.synchronizer.Synchronizer`
        * :py:class:`connector.unit.backend_adapter.BackendAdapter`

    Or basically any class intended to be registered in a
    :py:class:`backend.Backend`.
    """

    __metaclass__ = MetaConnectorUnit

    _model_name = None  # to be defined in sub-classes

    def __init__(self, environment):
        """

        :param environment: current environment (backend, session, ...)
        :type environment: :py:class:`connector.Environment`
        """
        super(ConnectorUnit, self).__init__()
        self.environment = environment
        self.backend = self.environment.backend
        self.backend_record = self.environment.backend_record
        self.session = self.environment.session
        self.model = self.session.pool.get(environment.model_name)
        # so we can use openerp.tools.translate._, used to find the lang
        # that's because _() search for a localcontext attribute
        # but self.localcontext should not be used for other purposes
        self.localcontext = self.session.context

    @classmethod
    def match(cls, model):
        """ Returns True if the current class correspond to the
        searched model.

        :param model: model to match
        :type model: str or :py:class:`openerp.models.Model`
        """
        # filter out the ConnectorUnit from modules
        # not installed in the current DB
        if hasattr(model, '_name'):  # Model instance
            model_name = model._name
        else:
            model_name = model  # str

        return model_name in cls.model_name

    def get_connector_unit_for_model(self, connector_unit_class, model=None):
        """ Use the current :py:class:`connector.Environment` to
        search and return an instance of the
        :py:class:`connector.ConnectorUnit` for the current model.

        If a ``model`` is given, a new :py:class:`connector.Environment`
        is built for this model.

        :param connector_unit_class: ``ConnectorUnit`` to search
                                     (class or subclass)
        :type connector_unit_class: :py:class:`connector.ConnectorUnit`
        :param model: to give if the ``ConnectorUnit`` is for another
                      model than the current one
        :type model: str
        :return: a subclass of ``ConnectorUnit`` class.
        """

        if model is None:
            env = self.environment
        else:
            env = Environment(self.backend_record,
                              self.session,
                              model)
        return env.get_connector_unit(connector_unit_class)

    def get_binder_for_model(self, model=None):
        """ Returns an new instance of the correct ``Binder`` for
        a model """
        return self.get_connector_unit_for_model(Binder, model)


class Environment(object):
    """ Environment used by different units for synchronization.

    .. attribute:: backend_record

        Browsable record of the backend. The backend is inherited
        from the model ``connector.backend`` and have at least a
        ``type`` and a ``version``.

    .. attribute:: session

        Current session we are working in. It contains the Odoo
        cr, uid and context.

    .. attribute:: model_name

        Name of the Odoo model to work with.
    """

    def __init__(self, backend_record, session, model_name):
        """

        :param backend_record: browse record of the backend
        :type backend_record: :py:class:`openerp.osv.orm.browse_record`
        :param session: current session (cr, uid, context)
        :type session: :py:class:`connector8.session.ConnectorSession`
        :param model_name: name of the model
        :type model_name: str
        """
        self.backend_record = backend_record
        self.backend = backend_record.get_backend()
        self.session = session
        self.model_name = model_name
        self.model = self.session.pool.get(model_name)
        self.pool = self.session.pool

    def set_lang(self, code):
        """ Change the working language in the environment.

        It changes the ``lang`` key in the session's context.
        """
        self.session.context['lang'] = code

    def get_connector_unit(self, base_class):
        """ Searches and returns an instance of the
        :py:class:`connector.ConnectorUnit` for the current model

        The returned instance is built with ``self`` for its environment.

        :param base_class: ``ConnectorUnit`` to search (class or subclass)
        :type base_class: :py:class:`connector8.connector.ConnectorUnit`
        """

        connector_unit_class = self.backend.get_service_class(
            base_class, self.model_name)
        return connector_unit_class(self)


class Binder(ConnectorUnit):
    """ For one record of a model, capable to find an external or
    internal id, or create the binding (link) between them

    The Binder should be implemented in the connectors.
    """

    _model_name = None  # define in sub-classes

    def to_odoo(self, external_id, unwrap=False):
        """ Give the Odoo ID for an external ID

        :param external_id: external ID for which we want
                            the Odoo ID
        :param unwrap: if True, returns the openerp_id
                       else return the id of the binding
        :return: a record ID, depending on the value of unwrap,
                 or None if the external_id is not mapped
        :rtype: int
        """
        raise NotImplementedError

    def to_backend(self, binding_id, wrap=False):
        """ Give the external ID for an Odoo binding ID
        (ID in a model magento.*)

        :param binding_id: Odoo binding ID for which we want the backend id
        :param wrap: if False, binding_id is the ID of the binding,
                     if True, binding_id is the ID of the normal record, the
                     method will search the corresponding binding and returns
                     the backend id of the binding
        :return: external ID of the record
        """
        raise NotImplementedError

    def bind(self, external_id, binding_id):
        """ Create the link between an external ID and an Odoo ID

        :param external_id: external id to bind
        :param binding_id: Odoo ID to bind
        :type binding_id: int
        """
        raise NotImplementedError

    def unwrap_binding(self, binding_id, browse=False):
        """ For a binding record, gives the normal record.

        Example: when called with a ``magento.product.product`` id,
        it will return the corresponding ``product.product`` id.

        :param browse: when True, returns a browse_record instance
                       rather than an ID
        """
        raise NotImplementedError

    def unwrap_model(self):
        """ For a binding model, gives the normal model.

        Example: when called on a binder for ``magento.product.product``,
        it will return ``product.product``.
        """
        raise NotImplementedError
