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
Producers of events.

Fire the common events:

-  ``on_record_create`` when a record is created
-  ``on_record_write`` when something is written on a record
-  ``on_record_unlink``  when a record is deleted

"""

import logging

from openerp import models, api

from .event import (on_record_create,
                    on_record_write,
                    on_record_unlink)


_logger = logging.getLogger(__name__)

create_original = models.BaseModel.create
write_original = models.BaseModel.write
unlink_original = models.BaseModel.unlink


@api.model
@api.returns('self', lambda value: value.id)
def create(self, values):
    """ Create a new record with the values

    :param values: the values of the new record
    :return: the newly created record
    """
    record = create_original(self, values)
    on_record_create.fire(self._name, record)
    return record

models.BaseModel.create = create


@api.multi
def write(self, values):
    write_original(self, values)

    if on_record_write.has_consumer_for(self._name):
        for record_id in self._ids:
            on_record_write.fire(self._name, record_id, values)

    return True

models.BaseModel.write = write


def unlink(self, cr, uid, ids, context=None):
    unlink_original(self, cr, uid, ids, context=context)

    if not hasattr(ids, '__contains__'):
        ids = [ids]

    if on_record_unlink.has_consumer_for(self._name):
        for record_id in ids:
            on_record_unlink.fire(self._name, record_id)

    return True

models.BaseModel.unlink = unlink
