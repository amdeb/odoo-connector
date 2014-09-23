import inspect
import threading

from openerp.models import MetaModel, AbstractModel
from openerp.modules.registry import RegistryManager

from openerp.modules.registry import RegistryManager

INSTALLED_MODEL_NAME_POSTFIX = ".installed"


def get_odoo_module_name(cls_func_path):
    """ Get module name for a class, a function or a module path

    Extract the first part of an Odoo module name excluding
    openerp.addon.

    Taken from Odoo server: ``openerp.models``
    The Odoo module name can be in the ``openerp.addons`` namespace
    or not. For instance module ``sale`` can be imported as
    ``openerp.addons.sale`` (the good way) or ``sale`` (for backward
    compatibility).
    """

    module_path = (cls_func_path
                   if isinstance(cls_func_path, basestring)
                   else cls_func_path.__module__)

    module_parts = module_path.split('.')
    if len(module_parts) > 2 and module_parts[:2] == ['openerp', 'addons']:
        module_name = module_parts[2]
    else:
        module_name = module_parts[0]
    return module_name


def get_installed_module_name(odoo_module_name):
    return odoo_module_name + INSTALLED_MODEL_NAME_POSTFIX


def is_module_installed(cls_func):
    """ find if the odoo module of a class or func is installed """

    odoo_module_name = getattr(cls_func, 'odoo_module_name', None)
    if not odoo_module_name:
        odoo_module_name = get_odoo_module_name(cls_func)

    installed_model_name = get_installed_module_name(odoo_module_name)
    odoo_pool = RegistryManager.get(
        threading.current_thread().dbname)
    return bool(odoo_pool.get(installed_model_name))


def install_in_connector():
    """ Installs an Odoo module in the ``Connector`` framework.

    It has to be called once per Odoo module to be found by connector.

    Under the cover, it creates a an abstract model whose _name
    is ``{name_of_the_odoo_module_to_install}.installed``.

    The connector uses this abastract model to know when the Odoo module
    is installed or not and whether it should use the ConnectorUnit
    classes of this module or not and whether it should fire the
    consumers of events or not.
    """

    # Get the module of the caller
    caller_module_name = inspect.currentframe().f_back.f_globals["__name__"]

    odoo_module_name = get_odoo_module_name(caller_module_name)
    # Build a new AbstractModel with the name of the module and the suffix
    name = get_installed_module_name(odoo_module_name)
    class_name = name.replace('.', '_')
    # we need to call __new__ and __init__ in 2 phases because
    # __init__ needs to have the right __module__ and _module attributes
    model = MetaModel.__new__(MetaModel, class_name,
                              (AbstractModel,), {'_name': name})
    # Update the module of the model, it should be the caller's one
    model._module = odoo_module_name
    model.__module__ = caller_module_name
    MetaModel.__init__(model, class_name,
                       (AbstractModel,), {'_name': name})