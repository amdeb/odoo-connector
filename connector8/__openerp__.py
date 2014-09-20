# -*- coding: utf-8 -*-

{'name': 'Connector8',
 'version': '0.1',
 'author': 'Openerp Connector Core Editors and Amdeb',
 'license': 'AGPL-3',
 'category': 'Generic Modules',
 'description': """
This is a port of OCA connector to Odoo 8.0
""",
 'depends': ['mail'
             ],
 'data': ['security/connector_security.xml',
          'security/ir.model.access.csv',
          'queue/model_view.xml',
          'queue/queue_data.xml',
          'checkpoint/checkpoint_view.xml',
          'res_partner_view.xml',
          ],
 'installable': True,
 'application': True,
 }
