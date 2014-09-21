# -*- coding: utf-8 -*-

import unittest2
import openerp.tests.common as common

from ..backend import Backend
from ..connector import ConnectorUnit
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
        """ Create a backend with version"""
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
        """ Find a backend with a wrong name"""
        Backend(self.name)
        self.assertIsNone(Backend.get_backend("NotExistingName"))

    def test_get_backend_default(self):
        """ Find a backend with a default """
        version = '1.14'
        backend = Backend(self.name, version)
        registered = Backend.get_backend(
            "NotExistingName", version='1.14', default=backend)
        self.assertEqual(backend, registered)

    def test_backend_repr(self):
        backend = Backend(self.name)
        expected = "Backend<'{0}'>" .format(self.name)
        self.assertEqual(expected, repr(backend))

    def test_backend_repr_version(self):
        template_version = "<Backend('{0}', '{1}'>"
        version = '1.14'
        backend = Backend(self.name, version)
        expected = template_version.format(self.name, version)
        self.assertEqual(expected, repr(backend))


class test_backend_service_registry(common.TransactionCase):
    """ Test registration of classes on the Backend"""

    def setUp(self):
        super(test_backend_service_registry, self).setUp()
        self.service_name = 'calamitorium'
        self.version = '1.14'
        self.model_name = 'res.users'
        self.parent = Backend(self.service_name)
        self.backend = Backend(parent=self.parent, version=self.version)
        self.session = ConnectorSession(self.cr, self.uid)

    def tearDown(self):
        super(test_backend_service_registry, self).tearDown()
        Backend._clear_backend_registry()

    def test_register_service_class(self):
        """get the registered service class"""
        class BenderBinder(ConnectorUnit):
            _model_name = self.model_name

        self.backend.register_service_class(BenderBinder)
        ref = self.backend.get_service_class(
            BenderBinder, self.session, self.model_name
        )

        self.assertEqual(ref, BenderBinder)

    def test_backend_decorator(self):
        """register a service using decorator"""
        @self.backend
        class ZoidbergMapper(ConnectorUnit):
            _model_name = self.model_name

        ref = self.backend.get_service_class(
            ZoidbergMapper, self.session, self.model_name
        )
        self.assertEqual(ref, ZoidbergMapper)

    def test_no_register_none(self):
        """ Return None for unregistered service"""
        class FryBinder(ConnectorUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            FryBinder, self.session, self.model_name
        )
        self.assertIsNone(matching_cls)

    def test_get_class_match_subclass(self):
        """ search subclass when both base and sub registered """
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaYesUnit, self.session, self.model_name
        )
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_match_baseclass(self):
        """ search base class when both base and sub registered """
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, self.model_name
        )
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_installed_module(self):
        """ Only class from an installed module should be returned """
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        class LambdaNoUnit(LambdaUnit):
            _model_name = self.model_name

        # trick the origin of the class, let it think
        # that it comes from the Odoo module 'not installed module'
        LambdaNoUnit.odoo_module_name = 'not installed module'
        self.backend(LambdaNoUnit)

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, self.model_name
        )
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_replacing_module(self):
        """ Returns the replacing ConnectorUnit"""

        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaNoUnit(LambdaUnit):
            _model_name = self.model_name

        @self.backend(replacing=LambdaNoUnit)
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, self.model_name)
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_replacing_uninstalled_module(self):
        """ Does not return the replacing ConnectorUnit of an
        uninstalled module """

        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        class LambdaNoUnit(LambdaUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        # trick the origin of the class, let it think
        # that it comes from the Odoo module 'not installed module'
        LambdaNoUnit.odoo_module_name = 'not installed module'
        self.backend(LambdaNoUnit, replacing=LambdaYesUnit)

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, self.model_name)
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_replacing_two(self):
        """ Replace several classes"""
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaNoUnit(LambdaUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaNo2Unit(LambdaUnit):
            _model_name = self.model_name

        @self.backend(replacing=(LambdaNoUnit, LambdaNo2Unit))
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, self.model_name)
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_class_replacing_self(self):
        """ Replacing oneself adds one as the last registered"""

        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaRecursiveUnit(LambdaUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaUnitA(LambdaUnit):
            _model_name = self.model_name

        @self.backend(replacing=LambdaRecursiveUnit)
        class LambdaRecursiveUnit(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, self.model_name)
        self.assertEqual(matching_cls, LambdaRecursiveUnit)

    def test_get_class_not_existing_model(self):
        """Not found should return None for unmatched model name"""

        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, 'no.res.users')
        self.assertIsNone(matching_cls)

    def test_get_class_service_not_registered(self):
        """Not found should return None for unmatched service"""

        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        class LambdaUnitA(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaUnitA, self.session, self.model_name)
        self.assertIsNone(matching_cls)

    def test_get_class_multiple_match(self):
        """Multiple matches should return the last-added"""
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaUnitA(LambdaUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaUnitZ(LambdaUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaUnitB(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.session, self.model_name)
        self.assertEqual(matching_cls, LambdaUnitB)

