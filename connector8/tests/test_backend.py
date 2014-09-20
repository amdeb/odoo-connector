# -*- coding: utf-8 -*-

import unittest2

import openerp.tests.common as common
from ..backend import Backend
from ..exception import ConnectorUnitError
from ..connector import Binder, ConnectorUnit
from ..unit.mapper import ExportMapper
from ..unit.backend_adapter import BackendAdapter
from ..session import ConnectorSession


class test_backend(unittest2.TestCase):
    """ Test Backend """

    def setUp(self):
        super(test_backend, self).setUp()
        self.name = 'calamitorium'

    def tearDown(self):
        super(test_backend, self).tearDown()
        Backend._clear_backend_registry()

    def test_new_backend(self):
        """ Create a backend"""
        backend = Backend(self.name)
        self.assertEqual(backend.name, self.name)
        self.assertIsNone(backend.version)

    def test_new_backend_version(self):
        """ Create a backend"""
        version = '1.14'
        backend = Backend(self.name, version=version)
        self.assertEqual(backend.name, self.name)
        self.assertEqual(backend.version, version)

    def test_parent_name(self):
        """ Bind the backend to a parent backend"""
        version = '1.14'
        backend = Backend(self.name)
        child_backend = Backend(parent=backend, version=version)
        self.assertEqual(child_backend.name, backend.name)

    def test_no_name_no_parent(self):
        """ Should raise an error because no service or parent is defined"""
        with self.assertRaises(ValueError):
            Backend(version='1.14')

    def test_get_backend(self):
        """ Find a backend """
        backend = Backend(self.name)
        registered = Backend.get_backend(self.name)
        self.assertEqual(backend, registered)

    def test_get_backend_version(self):
        """ Find a backend with a version """
        parent = Backend(self.name)
        backend = Backend(parent=parent, version='1.14')
        registered = Backend.get_backend(self.name, version='1.14')
        self.assertEqual(backend, registered)

    def test_get_backend_none(self):
        """ Find a backend with a default """
        Backend(self.name)
        self.assertIsNone(Backend.get_backend("NotExistingName"))

    def test_get_backend_default(self):
        """ Find a backend with a default """
        version = '1.14'
        backend = Backend(self.name, version)
        registered = Backend.get_backend(
            "NotExistingName", version='1.14', default=backend)
        self.assertEqual(backend, registered)

    def test_backend_str(self):
        backend = Backend(self.name)
        expected = 'Backend(\'%s\')' % self.name
        self.assertEqual(expected, str(backend))

    def test_backend_str_version(self):
        version = '1.14'
        backend = Backend(self.name, version)
        expected = 'Backend(\'%s\', \'%s\')' % (self.name, version)
        self.assertEqual(expected, str(backend))

    def test_backend_repr(self):
        backend = Backend(self.name)
        expected = '<Backend \'%s\'>' % self.name
        self.assertEqual(expected, repr(backend))

    def test_backend_repr_version(self):
        version = '1.14'
        backend = Backend(self.name, version)
        expected = '<Backend \'%s\', \'%s\'>' % (self.name, version)
        self.assertEqual(expected, repr(backend))


class test_backend_register(common.TransactionCase):
    """ Test registration of classes on the Backend"""

    def setUp(self):
        super(test_backend_register, self).setUp()
        self.service = 'calamitorium'
        self.version = '1.14'
        self.parent = Backend(self.service)
        self.backend = Backend(parent=self.parent, version=self.version)
        self.session = ConnectorSession(self.cr, self.uid)

    def tearDown(self):
        super(test_backend_register, self).tearDown()
        Backend._clear_backend_registry()
        del self.parent._class_entries[:]
        del self.backend._class_entries[:]

    def test_register_get_registered(self):
        class BenderBinder(Binder):
            _model_name = 'res.users'

        self.backend.register_service_class(BenderBinder)
        ref = self.backend.get_service_class(
            BenderBinder, self.session, 'res.users'
        )

        self.assertEqual(ref, BenderBinder)

    def test_register_get_base(self):
        class BenderBinder(Binder):
            _model_name = 'res.users'

        self.backend.register_service_class(BenderBinder)
        ref = self.backend.get_service_class(
            Binder, self.session, 'res.users'
        )

        self.assertEqual(ref, BenderBinder)

    def test_backend_decorator(self):
        @self.backend
        class ZoidbergMapper(ExportMapper):
            _model_name = 'res.users'

        ref = self.backend.get_service_class(
            ExportMapper, self.session, 'res.users'
        )
        self.assertEqual(ref, ZoidbergMapper)

    def test_get_registered_from_parent(self):
        """ It should get the parent's class when no class is defined"""
        @self.parent
        class FryBinder(Binder):
            _model_name = 'res.users'

        ref = self.backend.get_service_class(
            Binder, self.session, 'res.users'
        )
        self.assertEqual(ref, FryBinder)

    def test_no_register_error(self):
        """ Error when asking for a class and none is found"""
        with self.assertRaises(ConnectorUnitError):
            self.backend.get_service_class(
                BackendAdapter, self.session, 'res.users'
            )

    def test_get_class_installed_module(self):
        """ Only class from an installed module should be returned """
        class LambdaUnit(ConnectorUnit):
            _model_name = 'res.users'

        @self.backend
        class LambdaYesUnit(LambdaUnit):
            _model_name = 'res.users'

        class LambdaNoUnit(LambdaUnit):
            _model_name = 'res.users'

        # trick the origin of the class, let it think
        # that it comes from the OpenERP module 'not installed module'
        LambdaNoUnit._openerp_module_ = 'not installed module'
        self.backend(LambdaNoUnit)

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, 'res.users'
        )
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_replacing_module(self):
        """ Returns the replacing ConnectorUnit"""

        class LambdaUnit(ConnectorUnit):
            _model_name = 'res.users'

        @self.backend
        class LambdaNoUnit(LambdaUnit):
            _model_name = 'res.users'

        @self.backend(replacing=LambdaNoUnit)
        class LambdaYesUnit(LambdaUnit):
            _model_name = 'res.users'

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, 'res.users')
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_replacing_uninstalled_module(self):
        """ Does not return the replacing ConnectorUnit of an
        uninstalled module """

        class LambdaUnit(ConnectorUnit):
            _model_name = 'res.users'

        @self.backend
        class LambdaYesUnit(LambdaUnit):
            _model_name = 'res.users'

        class LambdaNoUnit(LambdaUnit):
            _model_name = 'res.users'

        # trick the origin of the class, let it think
        # that it comes from the OpenERP module 'not installed module'
        LambdaNoUnit._openerp_module_ = 'not installed module'
        self.backend(LambdaNoUnit, replacing=LambdaYesUnit)

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, 'res.users')
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_replacing_diamond(self):
        """ Replace several classes in a diamond fashion """
        class LambdaUnit(ConnectorUnit):
            _model_name = 'res.users'

        @self.backend
        class LambdaNoUnit(LambdaUnit):
            _model_name = 'res.users'

        @self.backend
        class LambdaNo2Unit(LambdaUnit):
            _model_name = 'res.users'

        @self.backend(replacing=(LambdaNoUnit, LambdaNo2Unit))
        class LambdaYesUnit(LambdaUnit):
            _model_name = 'res.users'

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, 'res.users')
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_replacing_self(self):
        """ A class should not be able to replace itself """
        class LambdaUnit(ConnectorUnit):
            _model_name = 'res.users'

        @self.backend
        class LambdaRecurseUnit(LambdaUnit):
            _model_name = 'res.users'

        self.backend.register_service_class(
            LambdaRecurseUnit, replacing=LambdaRecurseUnit
        )

        self.assertEqual(0, len(self.backend._class_entries.replaced_by))
