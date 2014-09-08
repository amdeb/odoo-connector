# -*- coding: utf-8 -*-

import logging
from openerp import models, api


_logger = logging.getLogger(__name__)
create_original = models.BaseModel.create

_logger.info("module name: {0}".format(__name__))

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
    _logger.debug("in new create debug message")
    record = self.browse(create_original(self, values))
    _logger.info("Created record values: {0}".format(record))

    return record

models.BaseModel.create = create
