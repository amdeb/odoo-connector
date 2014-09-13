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

        # use env, not registry, to use new api
        self.model = self.env['res.partner']
        self.partner = self.model.create({'name': 'new'})

    def test_on_record_create(self):
        """
        Create a record and check if the event is called
        """
        @on_record_create(model_names='res.partner')
        def event(session, model_name, record_set):
            self.recipient.name = record_set[0].name

        values = {'name': 'Kif Kroker'}
        self.model.create(values)
        self.assertEqual(self.recipient.name, values['name'])
        on_record_create.unsubscribe(event)

    def test_on_record_write(self):
        """
        Write on a record and check if the event is called
        """
        @on_record_write(model_names='res.partner')
        def event(session, model_name, record_id, values=None):
            self.recipient.record_id = record_id
            self.recipient.values = values

        # update ids in current model
        partner = self.model[0]
        values = {'name': 'Lrrr', 'city': 'Omicron Persei 8'}
        self.model.write(values)
        self.assertEqual(self.recipient.record_id, partner.id)
        self.assertDictEqual(self.recipient.values, values)
        on_record_write.unsubscribe(event)

    def test_on_record_unlink(self):
        """
        Unlink a record and check if the event is called
        """
        @on_record_unlink(model_names='res.partner')
        def event(session, model_name, record_id):
            if model_name == 'res.partner':
                self.recipient.record_id = record_id

        unlinked_id = self.partner.id
        self.model.unlink(unlinked_id)
        self.assertEqual(self.recipient.record_id, unlinked_id)
        on_record_write.unsubscribe(event)

    def test_on_record_write_no_consumer(self):
        """
        If no consumer is registered on the event for the model,
        the event should not be fired at all
        """
        # clear all the registered events
        on_record_write._consumers = {None: set()}

        with mock.patch.object(on_record_write, 'fire'):
            self.model.write({'name': 'Kif Kroker'})
            self.assertEqual(on_record_write.fire.called, False)
