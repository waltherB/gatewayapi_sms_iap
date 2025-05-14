# Odoo 17 - GatewayAPI SMS Connector (via IAP Alternative Provider)

## Overview

This module integrates [GatewayAPI.eu](https://gatewayapi.eu) as an SMS provider for your Odoo 17 instance. It utilizes the **IAP Alternative Provider** framework developed by the Odoo Community Association (OCA), allowing you to send SMS messages (notifications, marketing, alerts) directly from Odoo using GatewayAPI as the backend gateway.

The module is designed to be robust, user-friendly, and provides essential features like automatic UCS-2 encoding for emojis, API token security, balance checking, and low credit notifications.

## Key Features

*   **GatewayAPI Integration**: Send SMS via your GatewayAPI account.
*   **IAP Alternative Provider Framework**: Built upon the stable [OCA `iap_alternative_provider` module](https://github.com/OCA/server-tools/tree/17.0/iap_alternative_provider).
*   **Easy Configuration**: Set up your GatewayAPI credentials (API Token, Sender Name, Base URL) within Odoo.
    *   Default Base URL: `https://gatewayapi.eu` (configurable).
    *   Secure API Token handling with a show/hide toggle.
*   **Automatic UCS-2 Encoding**: Messages containing emojis or other non-GSM7 characters are automatically detected and sent using UCS-2 encoding to ensure correct display.
*   **Connection Testing**: Verify your API credentials and check your current GatewayAPI credit balance directly from the configuration screen.
*   **Automated Balance Checks**:
    *   Enable periodic checks of your GatewayAPI credit balance.
    *   Configure the check interval (minutes, hours, days, etc.).
*   **Low Credit Notifications**:
    *   Set a minimum credit threshold.
    *   Receive notifications in Odoo (via selected channels or directly to users) when your balance falls below this limit.
*   **Detailed Logging**: Comprehensive logging for SMS sending attempts, API responses, and balance checks to aid in troubleshooting.
*   **Multi-Language Support**: Initial translations provided for English and Danish.

## Prerequisites

1.  **Odoo Version**: 17.0
2.  **OCA `iap_alternative_provider` Module**: This module is a **critical dependency**. You must download and install it from the OCA `server-tools` repository for Odoo 17:
    *   Repository: [https://github.com/OCA/server-tools](https://github.com/OCA/server-tools)
    *   Direct link to module (ensure you get the version for Odoo 17.0): [server-tools/tree/17.0/iap_alternative_provider](https://github.com/OCA/server-tools/tree/17.0/iap_alternative_provider)
    *   Place the `iap_alternative_provider` module in your Odoo addons path and install it *before* installing this GatewayAPI connector.
3.  **Python `requests` library**: This is a standard Python library, usually already available. If not, install it: `pip install requests`
4.  **GatewayAPI Account**: You need an active account with [GatewayAPI.eu](https://gatewayapi.eu) and your API token.

## Installation

1.  Ensure all prerequisites, especially the OCA `iap_alternative_provider` module, are installed and working in your Odoo 17 environment.
2.  Download this module (`gatewayapi_sms_iap`).
3.  Place the `gatewayapi_sms_iap` folder into your Odoo custom addons path.
4.  Restart the Odoo server.
5.  Go to **Apps** in Odoo, click **Update Apps List**.
6.  Search for "GatewayAPI SMS Connector (IAP Alternative)" and click **Install**.

## Configuration

1.  **Configure the Alternative Provider:**
    *   Navigate to **Settings » Technical » Alternative Providers**.
    *   Click **Create**.
    *   **Name**: Give your configuration a descriptive name (e.g., "GatewayAPI Production").
    *   **Provider**: Select **GatewayAPI** from the dropdown list.
    *   Fill in the GatewayAPI specific fields:
        *   **GatewayAPI Account Label**: A friendly label for this setup.
        *   **GatewayAPI Base URL**: Defaults to `https://gatewayapi.eu`. Change only if you have a custom endpoint.
        *   **Default Sender Name**: Your desired SMS sender ID (e.g., your company name or a verified number, adhering to GatewayAPI and local regulations).
        *   **API Token**: Your API Token obtained from your GatewayAPI dashboard. Use the eye icon to toggle visibility.
    *   **Available for services**: Select **sms** from the list. This tells Odoo that this provider can handle SMS services.
    *   Click the **Check Credentials** button to test the connection and retrieve your current balance.
    *   (Optional) Configure the **Automated Balance Check & Notifications** section:
        *   Tick **Enable GatewayAPI Balance Check**.
        *   Set your desired **Minimum Credit Limit**.
        *   Configure the **Check Interval** and **Interval Unit**.
        *   Select a **Notification Channel** and/or **Notify Users Directly** for low credit alerts.
    *   **Save** the Alternative Provider record.

2.  **Link to IAP Account:**
    *   Navigate to **Settings » Technical » IAP Accounts**.
    *   Click **Create** (or edit an existing IAP account if you have one for SMS).
    *   **Service Name**: Select or type `sms`.
    *   **Alternative Provider**: Select the GatewayAPI provider record you configured in the previous step.
    *   (Optional) If you use multi-company, you can assign this IAP account to a specific **Company**. If left blank, it's global.
    *   **Save** the IAP Account.

Your Odoo system is now configured to use GatewayAPI for sending SMS messages.

## Usage

Once configured, Odoo will automatically use this GatewayAPI setup when sending SMS messages through its standard mechanisms:

*   Sending SMS from Contact forms.
*   SMS marketing campaigns.
*   Automated SMS from workflows (e.g., in CRM or Sales).
*   Using the "Send SMS" composer available in various Odoo views.
*   Programmatic sending from other custom modules by calling the standard Odoo SMS API (e.g., `self.env['sms.api']._send_sms(...)`).

The module will automatically detect if messages contain emojis or special characters and use UCS-2 encoding. Otherwise, it will use GSM-7.

## Logging

The module provides detailed logging for:
*   API requests and responses to GatewayAPI.
*   SMS sending status (success/failure).
*   Error mapping for common GatewayAPI issues.
*   Balance check operations.

Check your Odoo server logs for messages prefixed with `GatewayAPI` or related to the `iap.alternative.provider` model for troubleshooting.

## Translations

This module includes initial translations for:
*   English (Source)
*   Danish (da)
*   British English (en_GB)

To add or improve translations:
1.  Ensure all user-facing strings in Python code are wrapped with `_()`.
2.  Use Odoo's tools to extract translatable terms into the `.pot` file:
    ```bash
    # Navigate to your custom addons directory
    # Example:
    python /path/to/odoo/odoo-bin agettext -d gatewayapi_sms_iap -p .
    # Or using the i18n_tool.py:
    # python /path/to/odoo/tools/i18n_tool.py --path=./gatewayapi_sms_iap --output_pot=gatewayapi_sms_iap/i18n/gatewayapi_sms_iap.pot
    ```
3.  Copy the generated `i18n/gatewayapi_sms_iap.pot` to a new `i18n/<lang_code>.po` file (e.g., `i18n/fr.po` for French).
4.  Translate the `msgstr` entries in the new `.po` file.
5.  Restart Odoo and update the language translations in Odoo settings.

## Support and Contribution

*   **Author**: [Your Name / Company]
*   **Website**: [https://www.yourwebsite.com]
*   **Support**: For issues or questions, please contact [your-support-email@example.com] or open an issue if this project is hosted on a public repository.

Contributions to improve the module are welcome!

## License

LGPL-3
