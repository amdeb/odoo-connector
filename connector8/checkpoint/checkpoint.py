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

"""
The checkpoint is a model containing records to be reviewed by the end
users.  The connectors register records to verify so the user can check
them and flag them as reviewed.

A concrete use case is the import of new products from Magento. Once
they are imported, the user have to configure things like the supplier,
so they appears in this list.
"""

from openerp import models, fields
from openerp.tools.translate import _


class connector_checkpoint(models.Model):
    _name = 'connector.checkpoint'
    _description = 'Connector Checkpoint'

    _inherit = ['mail.thread', 'ir.needaction_mixin']

    def _get_models(self):
        """ All models are allowed as reference, anyway the
        fields.reference are readonly. """
        model_obj = self.env['ir.model'].browse()
        models = model_obj.read(fields=['model', 'name'])
        return [(m['model'], m['name']) for m in models]

    def _get_ref(self):
        res = {}
        for check in self.browse():
            res[check.id] = check.model_id.model + ',' + str(check.record_id)
        return res

    def _get_record_name(self):
        res = {}
        for check in self.browse():
            model_obj = self.env[check.model_id.model].browse(check.record_id)
            res[check.id] = model_obj.name_get()[0][1]
        return res

    def _search_record(self, args):
        ids = set()

        sql = "SELECT DISTINCT model_id FROM connector_checkpoint"
        rows = self.env.cr.execute(sql).fecthall()
        model_ids = [row[0] for row in rows]

        model_obj = self.evn['ir.model'].browse(model_ids)
        models = model_obj.read(fields=['model'])

        for criteria in args:
            __, operator, value = criteria
            for model in models:
                model_id = model['id']
                model_name = model['model']
                model_obj = self.pool.get(model_name)
                results = model_obj.name_search(name=value,
                                                operator=operator)
                res_ids = [res[0] for res in results]
                check_ids = self.search(self.env.cr, self.env.uid,
                                        args=[('model_id', '=', model_id),
                                         ('record_id', 'in', res_ids)],
                                        context=self.context)
                ids.update(check_ids)
        if not ids:
            return [('id', '=', '0')]
        return [('id', 'in', tuple(ids))]

    record = fields.Reference(
        compute='_get_ref',
        type='reference',
        string='Record',
        selection=_get_models,
        help="The record to review.",
        size=128,
        readonly=True)

    name = fields.Char(
        compute='_get_record_name',
        fnct_search=_search_record,
        type='char',
        string='Record Name',
        help="Name of the record to review",
        readonly=True)

    record_id = fields.Integer(
        string='Record ID',
        required=True,
        readonly=True)

    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Model',
        required=True,
        readonly=True)

    backend_id = fields.Reference(
        string='Imported from',
        selection=_get_models,
        size=128,
        readonly=True,
        required=True,
        help="The record has been imported from this backend",
        select=1)

    state = fields.Selection(
        selection=[('need_review', 'Need Review'),
                   ('reviewed', 'Reviewed')],
        string='Status',
        required=True,
        readonly=True)

    _defaults = {
        'state': 'need_review',
    }

    def reviewed(self, cr, uid, ids, context=None):
        return self.write({'state': 'reviewed'})

    def _subscribe_users(self, ids):
        """ Subscribe all users having the 'Connector Manager' group """
        group_ref = self.env['ir.model.data'].get_object_reference(
            self.evn.cr, self.env.uid, 'connector', 'group_connector_manager')
        if not group_ref:
            return
        group_id = group_ref[1]

        user_ids = self.env.pool.get('res.users').search(
            self.env.cr, self.env.uid,
            [('groups_id', '=', group_id)],
            context=self.env.context
        )

        self.message_subscribe_users(
            self.env.cr, self.env.uid, ids,
            user_ids=user_ids,
            context=self.env.context
        )

    def create(self, vals):
        obj_id = super(connector_checkpoint, self).create(vals)
        self._subscribe_users([obj_id])
        cp = self.browse(obj_id)
        msg = _('A %s needs a review.') % cp.model_id.name
        self.message_post(
            self.env.cr, self.env.uid,
            obj_id, body=msg,
            subtype='mail.mt_comment',
            context=self.env.context
        )

        return obj_id

    def create_from_name(self, cr, uid, model_name, record_id,
                         backend_model_name, backend_id, context=None):
        model_obj = self.pool.get('ir.model')
        model_ids = model_obj.search(cr, uid,
                                     [('model', '=', model_name)],
                                     context=context)
        assert model_ids, "The model %s does not exist" % model_name
        backend = backend_model_name + ',' + str(backend_id)
        return self.create({'model_id': model_ids[0],
                            'record_id': record_id,
                            'backend_id': backend}
        )

    def _needaction_domain_get(self, cr, uid, context=None):
        """ Returns the domain to filter records that require an action
            :return: domain or False is no action
        """
        return [('state', '=', 'need_review')]


def add_checkpoint(session, model_name, record_id,
                   backend_model_name, backend_id):
    cr, uid, context = session.cr, session.uid, session.context
    checkpoint_obj = session.pool['connector.checkpoint']
    return checkpoint_obj.create_from_name(
        cr, uid,
        model_name, record_id,
        backend_model_name, backend_id,
        context=context
    )


class connector_checkpoint_review(models.TransientModel):
    _name = 'connector.checkpoint.review'
    _description = 'Checkpoints Review'

    def _get_checkpoint_ids(self):
        context = self.env.context
        if context is None:
            context = {}
        res = False
        if (context.get('active_model') == 'connector.checkpoint' and
                context.get('active_ids')):
            res = context['active_ids']
        return res

    checkpoint_ids = fields.Many2many(
        comodel_name='connector.checkpoint',
        relation='connector_checkpoint_review_rel',
        column1='review_id',
        column2='checkpoint_id',
        string='Checkpoints',
        domain="[('state', '=', 'need_review')]")

    _defaults = {
        'checkpoint_ids': _get_checkpoint_ids,
    }

    def review(self):
        form = self.browse()
        checkpoint_ids = [checkpoint.id for checkpoint in form.checkpoint_ids]
        checkpoint_obj = self.env['connector.checkpoint']
        checkpoint_obj.reviewed()
        return {'type': 'ir.actions.act_window_close'}
