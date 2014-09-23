# -*- coding: utf-8 -*-

import unittest2
import openerp.tests.common as common

from ..backend import Backend
from ..connector import ConnectorUnit


class TestBackend(unittest2.TestCase):
    """ Test Backend """

    def setUp(self):
        super(TestBackend, self).setUp()
        self.name = 'calamitorium'

    def tearDown(self):
        super(TestBackend, self).tearDown()
        Backend._clear_backend_registry()

    def test_new_backend(self):
        """ Create a backend"""
        backend = Backend(self.name)
        self.assertEqual(backend.name, self.name)

    def test_new_backend_invalid_name(self):
        """ Should raise an error because name should be a string"""
        with self.assertRaises(ValueError):
            Backend(33)

    def test_new_backend_invalid_backend(self):
        """ Should raise an error because parent should be an instance
        of Backend"""
        with self.assertRaises(ValueError):
            Backend(self.name, object)

    def test_backend_parent_eq(self):
        """ Create a backend"""
        parent = Backend(self.name)
        child_name = self.name + ' 1.7'
        child_one = Backend(child_name, parent)
        child_two = Backend(child_name, parent)
        self.assertEqual(child_one, child_two)

    def test_backend_parent_not_eq(self):
        """ Create a backend"""
        parent = Backend(self.name)
        child_name = self.name + ' 1.7'
        child_one = Backend(child_name, parent)
        child_two = Backend(child_name)
        self.assertNotEqual(child_one, child_two)

    def test_get_backend(self):
        """ Find a backend """
        backend = Backend(self.name)
        registered = Backend.get_backend(self.name)
        self.assertEqual(backend, registered)

    def test_get_backend_none(self):
        """ Find a backend with a wrong name"""
        Backend(self.name)
        self.assertIsNone(Backend.get_backend("NotExistingName"))

    def test_get_backend_default(self):
        """ Find a backend with a default """
        backend = Backend(self.name)
        registered = Backend.get_backend(
            "NotExistingName", backend)
        self.assertEqual(backend, registered)

    def test_backend_repr(self):
        backend = Backend(self.name)
        expected = "{0}({1}, {2})".format(
            type(backend).__name__, self.name, None)
        self.assertEqual(expected, repr(backend))


class TestBackendServiceRegistry(common.TransactionCase):
    """ Test registration of classes on the Backend"""

    def setUp(self):
        super(TestBackendServiceRegistry, self).setUp()
        self.service_name = 'calamitorium'
        self.name_version = self.service_name + '1.14'
        self.model_name = 'res.users'
        self.parent = Backend(self.service_name)
        self.backend = Backend(self.name_version, self.parent)

    def tearDown(self):
        super(TestBackendServiceRegistry, self).tearDown()
        Backend._clear_backend_registry()

    def test_register_service_class(self):
        """get the registered service class"""
        class BenderBinder(ConnectorUnit):
            _model_name = self.model_name

        self.backend.register_service_class(BenderBinder)
        ref = self.backend.get_service_class(
            BenderBinder, self.model_name
        )

        self.assertEqual(ref, BenderBinder)

    def test_backend_decorator(self):
        """register a service using decorator"""
        @self.backend
        class ZoidbergMapper(ConnectorUnit):
            _model_name = self.model_name

        ref = self.backend.get_service_class(
            ZoidbergMapper, self.model_name
        )
        self.assertEqual(ref, ZoidbergMapper)

    def test_get_service_class_unregistered_none(self):
        """ Return None for unregistered service"""
        class FryBinder(ConnectorUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            FryBinder, self.model_name
        )
        self.assertIsNone(matching_cls)

    def test_get_service_class_from_parent(self):
        """ search a class that only exists in a backend's parent """
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.parent
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaYesUnit, self.model_name
        )
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_service_class_for_subclass(self):
        """ search subclass when both base and sub registered """
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaYesUnit, self.model_name
        )
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_service_class_for_base_class(self):
        """ search base class when both base and sub registered """
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaYesUnit(LambdaUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.model_name
        )
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_service_class_not_installed_module(self):
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
            LambdaUnit, self.model_name
        )
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_service_class_replacing_module(self):
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
            LambdaUnit, self.model_name)
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_service_class_replacing_uninstalled_module(self):
        """ Does not return the replacing ConnectorUnit of an
        uninstalled module """

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
        self.backend(LambdaNoUnit, replacing=LambdaYesUnit)

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.model_name)
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_service_class_replacing_two(self):
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
            LambdaUnit, self.model_name)
        self.assertEqual(matching_cls, LambdaYesUnit)

    def test_get_service_class_replacing_self(self):
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
            LambdaUnit, self.model_name)
        self.assertEqual(matching_cls, LambdaRecursiveUnit)

    def test_get_service_class_not_existing_model(self):
        """Not found should return None for unmatched model name"""

        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        matching_cls = self.backend.get_service_class(
            LambdaUnit, 'no.res.users')
        self.assertIsNone(matching_cls)

    def test_get_service_class_multiple_match(self):
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
            LambdaUnit, self.model_name)
        self.assertEqual(matching_cls, LambdaUnitB)

    def test_replace_service_class(self):
        """ should return normal class """
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaUnitA(LambdaUnit):
            _model_name = self.model_name

        @self.backend
        class LambdaUnitB(LambdaUnit):
            _model_name = self.model_name

        self.backend.replace_service_class(LambdaUnitB)

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.model_name)
        self.assertEqual(matching_cls, LambdaUnitA)

    def test_replace_service_class_searched(self):
        """ replaced service class is still searched """
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        self.backend.replace_service_class(LambdaUnit)

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.model_name)
        self.assertEqual(matching_cls, LambdaUnit)

    def test_remove_service_class(self):
        """ replaced service class is still searched """
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        self.backend.remove_service_class(LambdaUnit)

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.model_name)
        self.assertIsNone(matching_cls)

    def test_remove_service_class_with_replaced(self):
        """ replaced service class can be removed """
        @self.backend
        class LambdaUnit(ConnectorUnit):
            _model_name = self.model_name

        @self.backend(replacing=LambdaUnit)
        class LambdaUnitB(LambdaUnit):
            _model_name = self.model_name

        self.backend.remove_service_class(LambdaUnit)
        self.backend.remove_service_class(LambdaUnitB)

        matching_cls = self.backend.get_service_class(
            LambdaUnit, self.model_name)
        self.assertIsNone(matching_cls)
