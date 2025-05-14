# -*- coding: utf-8 -*-
{
    'name': "GatewayAPI SMS Connector (IAP Alternative)",
    'summary': """
        Send SMS using GatewayAPI.eu via Odoo's IAP Alternative Provider framework.
        Supports automatic UCS-2 for emojis, balance checks, and low credit alerts.
    """,
    'description': """
        This module provides seamless integration with GatewayAPI.eu, allowing you to use it
        as your SMS gateway within Odoo. It leverages the 'IAP Alternative Provider'
        framework (OCA) for robust and flexible SMS sending capabilities.

        Key Features:
        - Configure GatewayAPI credentials securely.
        - Send SMS messages directly from Odoo (e.g., from contacts, CRM, custom flows).
        - Automatic UCS-2 encoding: Emojis and special characters are handled correctly.
        - Default GatewayAPI URL: gatewayapi.eu (user-configurable).
        - Test Connection: Verify your API token and see current GatewayAPI credit balance.
        - Automated Balance Checks: Configure scheduled checks for your GatewayAPI credits.
        - Low Credit Notifications: Receive alerts in Odoo (via channels or direct messages)
          when credits fall below your defined threshold.
        - Show/Hide API Token: For enhanced security in the configuration form.
        - Detailed Logging: For easier troubleshooting and monitoring of SMS activities.
        - Multi-Language Support: Initial translations for English and Danish.
    """,
    'author': "Your Name / Company", # Replace with your actual name/company
    'website': "https://www.yourwebsite.com", # Replace with your actual website
    'category': 'Marketing/SMS Marketing', # Or 'Technical Settings/Integrations'
    'version': '17.0.1.3.0',
    'license': 'LGPL-3',

    'depends': [
        'iap',
        'iap_alternative_provider',
        'mail',
        'sms',
    ],

    'data': [
        'views/iap_alternative_provider_views.xml',
        'data/ir_cron_data.xml',
    ],

    'images': [
        'static/description/banner.png',
    ],

    'external_dependencies': {
        'python': ['requests'],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
    'price': 0.00, # Set your price
    'currency': 'EUR', # Set your currency

    'live_test_url': 'https://your-demo-link.com', # Optional
    'support': 'your-support-email@example.com', # Optional
}
