# -*- coding: utf-8 -*-

import logging
from openerp import models, api


_logger = logging.getLogger(__name__)
create_original = models.BaseModel.create

_logger.info("module name: %s".format(__name__))

@api.model
@api.returns('self', lambda value: value.id)
def create(self, values):
    """Creates a new record and log the record id and values

    :param self: model self
    :param values: record values
    :return: record id
    :rtype : str
    """

    _logger.info("in new create")
    record_id = create_original(self, values)
    record = self.browser(record_id)
    #_logger.info("Created record id: %s".format(record_id))
    #_logger.info("Created record id: %s".format(record))

    return record_id

models.BaseModel.create = create
