{
    'name': 'WhatsApp Integration',
    'version': '18.0.2.0.0',
    'category': 'Discuss',
    'summary': 'WhatsApp Business API integration for Odoo Community',
    'description': """
WhatsApp Integration for Odoo 18 Community Edition
===================================================

This module provides WhatsApp Business API integration allowing you to:
* Send and receive WhatsApp messages via a chat-style interface
* Use message templates
* Track message history
* Link conversations to partners

Requirements:
* Meta Business Account
* WhatsApp Business API access
* Valid SSL certificate for webhooks
    """,
    'author': 'Custom Development',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/whatsapp_send_wizard_views.xml',
        'views/whatsapp_account_views.xml',
        'views/whatsapp_conversation_views.xml',
        'views/whatsapp_message_views.xml',
        'views/whatsapp_template_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'whatsapp_integration/static/src/components/**/*.js',
            'whatsapp_integration/static/src/components/**/*.xml',
            'whatsapp_integration/static/src/components/**/*.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
