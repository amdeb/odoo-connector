# -*- coding: utf-8 -*-

import mock

import openerp.tests.common as common
from ..event import (
    on_record_create,
    on_record_write,
    on_record_unlink
)


class test_producers(common.TransactionCase):
    """ Test producers """

    def setUp(self):
        super(test_producers, self).setUp()

        class Recipient(object):
            pass

        self.recipient = Recipient()
        # need the old pool to call old unlink method
        self.pool_model = self.registry('res.partner')
        self.model = self.env['res.partner']
        self.partner_unlink = self.model.create({'name': 'unlink_test'})
        self.partner_write = self.model.create({'name': 'write_test'})

    def test_on_record_create(self):
        """
        Create a record and check if the event is called
        """
        @on_record_create(model_names='res.partner')
        def event(session, model_name, record):
            self.recipient.record_id = record.id
            self.recipient.name = record.name

        record = self.model.create({'name': 'Kif Kroker'})
        self.assertEqual(self.recipient.record_id, record.id)
        self.assertEqual(self.recipient.name, record.name)
        on_record_create.unsubscribe(event)

    def test_on_record_write(self):
        """
        Write on a record and check if the event is called
        """
        @on_record_write(model_names='res.partner')
        def event(session, model_name, record_id, values=None):
            self.recipient.record_id = record_id
            self.recipient.values = values

        values = {
            'name': 'Lrrr',
            'city': 'Omicron Persei 8',
        }
        self.partner_write.write(values)

        self.assertEqual(self.recipient.record_id, self.partner_write.id)
        self.assertEqual(self.partner_write.name, values['name'])
        self.assertDictEqual(self.recipient.values, values)
        on_record_write.unsubscribe(event)

    def test_on_record_unlink(self):
        """
        Unlink a record and check if the event is called
        """
        @on_record_unlink(model_names='res.partner')
        def event(session, model_name, record_id):
                self.recipient.record_id = record_id

        unlink_id = self.partner_unlink.id
        # has to use the old style because of 8.0 bug
        self.pool_model.unlink(self.cr, self.uid, [unlink_id])
        self.assertEqual(self.recipient.record_id, unlink_id)
        on_record_unlink.unsubscribe(event)

    def test_on_record_write_no_consumer(self):
        """
        If no consumer is registered on the event for the model,
        the event should not be fired at all
        """
        # clear all the registered events
        on_record_write._consumers = {None: set()}
        with mock.patch.object(on_record_write, 'fire'):
            self.partner_write.write({'name': 'Kif Kroker'})
            self.assertEqual(on_record_write.fire.called, False)
