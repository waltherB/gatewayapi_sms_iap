# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

try:
    from odoo.addons.gatewayapi_sms_iap.services.gatewayapi_client import GatewayApiClient, DEFAULT_GATEWAYAPI_BASE_URL, message_requires_ucs2
except ImportError:
    _logger_init = logging.getLogger(__name__)
    _logger_init.error("Failed to import GatewayApiClient or message_requires_ucs2 from services.")
    GatewayApiClient = None
    message_requires_ucs2 = None # Should not happen if services/gatewayapi_client.py is correct
    DEFAULT_GATEWAYAPI_BASE_URL = "https://gatewayapi.eu" # Fallback


_logger = logging.getLogger(__name__)

class IapAlternativeProvider(models.Model):
    _inherit = 'iap.alternative.provider'

    provider = fields.Selection(
        selection_add=[('gatewayapi', 'GatewayAPI')],
        ondelete={'gatewayapi': 'cascade'}
    )

    gatewayapi_account_name = fields.Char(string=_("GatewayAPI Account Label"))
    gatewayapi_base_url = fields.Char(
        string=_("GatewayAPI Base URL"),
        default=lambda self: DEFAULT_GATEWAYAPI_BASE_URL
    )
    gatewayapi_sender_name = fields.Char(
        string=_("Default Sender Name"),
        help=_("Default sender for SMS. Alphanumeric: 1-11 chars. Numeric: 3-15 digits. Check GatewayAPI docs.")
    )
    gatewayapi_api_token = fields.Char(string=_("GatewayAPI API Token (Hidden)"), copy=False)
    gatewayapi_show_token = fields.Boolean(string=_("Show API Token"), default=False)

    gatewayapi_check_balance_enabled = fields.Boolean(string=_("Enable GatewayAPI Balance Check"), default=False)
    gatewayapi_min_credit_limit = fields.Float(string=_("Minimum Credit Limit"), default=10.0)
    gatewayapi_check_interval_qty = fields.Integer(string=_("Check Interval"), default=1)
    gatewayapi_check_interval_unit = fields.Selection([
        ('minutes', _('Minutes')), ('hours', _('Hours')), ('days', _('Days')),
        ('weeks', _('Weeks')), ('months', _('Months'))], string=_("Interval Unit"), default='days')
    gatewayapi_next_balance_check = fields.Datetime(string=_("Next Balance Check"), readonly=True, copy=False)
    gatewayapi_last_balance_check_result = fields.Text(string=_("Last Balance Check Info"), readonly=True, copy=False)

    gatewayapi_notify_channel_id = fields.Many2one(
        'mail.channel', string=_("Notification Channel"),
        help=_("Select an existing channel (e.g., #sms-alerts). To create a new one, go to the Discuss app, create the channel, then select it here.")
    )
    gatewayapi_notify_user_ids = fields.Many2many(
        'res.users', 'iap_alt_provider_gatewayapi_notify_user_rel',
        'provider_id', 'user_id', string=_("Notify Users Directly"))

    def action_toggle_gatewayapi_token_visibility(self):
        self.ensure_one()
        self.gatewayapi_show_token = not self.gatewayapi_show_token
        # The client-side reload will handle the view update for the token fields
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.onchange('provider')
    def _onchange_provider_gatewayapi_defaults(self):
        if self.provider == 'gatewayapi':
            sms_service = self.env.ref('iap.iap_service_sms', raise_if_not_found=False)
            if sms_service and sms_service not in self.service_ids:
                self.service_ids = [(6, 0, [sms_service.id])]
            if not self.gatewayapi_base_url: # Should be set by default lambda
                self.gatewayapi_base_url = DEFAULT_GATEWAYAPI_BASE_URL

    @api.onchange('gatewayapi_check_balance_enabled', 'gatewayapi_check_interval_qty', 'gatewayapi_check_interval_unit')
    def _onchange_schedule_next_gatewayapi_balance_check(self):
        if self.provider == 'gatewayapi' and self.gatewayapi_check_balance_enabled and \
           self.gatewayapi_check_interval_qty > 0 and self.gatewayapi_check_interval_unit:
            self._schedule_next_gatewayapi_balance_check(force_now=True)
        elif self.provider == 'gatewayapi': # if check disabled or params invalid for gatewayapi
            self.gatewayapi_next_balance_check = False

    def _get_gatewayapi_client(self):
        self.ensure_one()
        if self.provider != 'gatewayapi':
            _logger.warning("_get_gatewayapi_client called on non-GatewayAPI provider: %s", self.name)
            raise UserError(_("Internal Error: Attempted to get GatewayAPI client for wrong provider type."))
        if not self.gatewayapi_api_token:
            _logger.error("GatewayAPI API Token is missing for provider: %s", self.name)
            raise UserError(_("GatewayAPI API Token is not set for provider '%s'.") % self.name)
        if not GatewayApiClient: # Check if the class itself was imported
            _logger.critical("GatewayAPI client class (GatewayApiClient) is not loaded/imported.")
            raise UserError(_("Critical Error: GatewayAPI client library is not available."))
        return GatewayApiClient(self.gatewayapi_api_token, self.gatewayapi_base_url)

    def _map_gatewayapi_error_to_odoo_state(self, e, number=""):
        error_text = str(e.args[0] if e.args else e) # Get the message from UserError
        _logger.warning("Mapping GatewayAPI error for number %s: %s", number, error_text)

        if "balance" in error_text.lower() or "credit" in error_text.lower() or "insufficient funds" in error_text.lower():
            return 'insufficient_credit', error_text
        if "msisdn" in error_text.lower() or "recipient" in error_text.lower() or "invalid number" in error_text.lower() or "number format" in error_text.lower() or "Invalid MSISDN" in error_text:
            return 'wrong_number_format', error_text
        if "authentication failed" in error_text.lower() or "unauthorized" in error_text.lower() or "token" in error_text.lower():
            return 'server_error', _("Authentication error with GatewayAPI: %s") % error_text
        if "sender" in error_text.lower() and ("invalid" in error_text.lower() or "not allowed" in error_text.lower()):
            return 'server_error', _("Invalid or disallowed sender name: %s") % error_text
        # Default fallback
        return 'server_error', error_text

    def _sms_send(self, iap_account, messages, SudoUser=False):
        self.ensure_one()
        if self.provider != 'gatewayapi':
            return super()._sms_send(iap_account, messages, SudoUser=SudoUser)

        _logger.info("Sending %s SMS via GatewayAPI provider '%s' (IAP Account: '%s')",
                     len(messages), self.name, iap_account.name)

        if not self.gatewayapi_sender_name:
            _logger.error("GatewayAPI Default Sender Name missing for provider '%s'", self.name)
            return [{'res_id': msg['res_id'], 'state': 'server_error', 'error_text': _("GatewayAPI Default Sender Name is not configured.")} for msg in messages]

        try:
            client = self._get_gatewayapi_client()
        except UserError as e: # Errors from _get_gatewayapi_client
            _logger.error("Failed to initialize GatewayAPI client for provider '%s': %s", self.name, e)
            return [{'res_id': msg['res_id'], 'state': 'server_error', 'error_text': str(e.args[0] if e.args else e)} for msg in messages]

        results = []
        for message_data in messages:
            number = message_data['number']
            content = message_data['content']
            res_id = message_data['res_id']
            log_prefix = f"SMS to {number} (res_id: {res_id}, provider: {self.name}):"

            try:
                api_response = client.send_sms(
                    sender=self.gatewayapi_sender_name,
                    recipients=[number],
                    message_body=content
                )
                if api_response and isinstance(api_response.get('ids'), list) and api_response['ids']:
                    message_id_3rd_party = str(api_response['ids'][0])
                    results.append({
                        'res_id': res_id,
                        'state': 'success',
                        'message_id_3rd_party': message_id_3rd_party
                    })
                    _logger.info("%s Successfully sent. GatewayAPI ID: %s", log_prefix, message_id_3rd_party)
                else:
                    error_text = _("Unknown or malformed success response from GatewayAPI: %s") % api_response
                    results.append({'res_id': res_id, 'state': 'server_error', 'error_text': error_text})
                    _logger.warning("%s Failed. %s", log_prefix, error_text)
            except UserError as e: # Errors from client.send_sms
                state, error_text_mapped = self._map_gatewayapi_error_to_odoo_state(e, number)
                results.append({'res_id': res_id, 'state': state, 'error_text': error_text_mapped})
                _logger.error("%s Failed. Mapped State: %s, Error: %s", log_prefix, state, error_text_mapped)
            except Exception as e: # Other unexpected errors
                error_text_generic = _("Unexpected error sending SMS: %s") % str(e)
                results.append({'res_id': res_id, 'state': 'server_error', 'error_text': error_text_generic})
                _logger.error("%s Failed with unexpected error. Error: %s", log_prefix, str(e), exc_info=True)
        return results

    def check_credentials(self): # This method is called by the button in iap_alternative_provider
        self.ensure_one()
        if self.provider != 'gatewayapi':
            _logger.warning("check_credentials called on non-GatewayAPI provider: %s", self.name)
            return False # Should not happen if button is correctly made invisible

        _logger.info("Testing GatewayAPI credentials for provider: %s", self.name)
        try:
            client = self._get_gatewayapi_client()
            balance_info = client.get_balance()
            credits = balance_info.get('credits')
            currency = balance_info.get('currency')

            if credits is not None and currency:
                message = _("Connection Successful!\nYour GatewayAPI Balance: %(credits)s %(currency)s") % {'credits': credits, 'currency': currency}
                self.gatewayapi_last_balance_check_result = _("OK (%(datetime)s): %(credits)s %(currency)s") % {
                    'datetime': fields.Datetime.now(), 'credits': credits, 'currency': currency
                }
                self.env.user.notify_success(message=message, title=_("GatewayAPI Test"))
                _logger.info("GatewayAPI credential check for provider '%s' SUCCEEDED. Balance: %s %s", self.name, credits, currency)
                return True # As expected by iap_alternative_provider's button action
            else:
                error_msg = _("Connection Test: Received unexpected balance data from GatewayAPI: %s") % balance_info
                self.gatewayapi_last_balance_check_result = _("Error (%(datetime)s): %(error_msg)s") % {
                    'datetime': fields.Datetime.now(), 'error_msg': error_msg
                }
                _logger.warning("GatewayAPI credential check for provider '%s' FAILED: %s", self.name, error_msg)
                raise UserError(error_msg) # Show error to user
        except UserError as e: # Catches errors from _get_gatewayapi_client or client.get_balance
            self.gatewayapi_last_balance_check_result = _("Failed (%(datetime)s): %(error)s") % {
                'datetime': fields.Datetime.now(), 'error': str(e.args[0] if e.args else e)
            }
            _logger.error("GatewayAPI credential check for provider '%s' FAILED: %s", self.name, e)
            raise # Re-raise to show in UI
        except Exception as e: # Other unexpected errors
            error_msg_generic = _("GatewayAPI Connection Test Failed unexpectedly: %s") % str(e)
            self.gatewayapi_last_balance_check_result = _("Failed (%(datetime)s): %(error)s") % {
                'datetime': fields.Datetime.now(), 'error': error_msg_generic
            }
            _logger.error("GatewayAPI credential check for provider '%s' FAILED unexpectedly: %s", self.name, e, exc_info=True)
            raise UserError(error_msg_generic)

    def _schedule_next_gatewayapi_balance_check(self, force_now=False):
        self.ensure_one()
        if not (self.provider == 'gatewayapi' and self.gatewayapi_check_balance_enabled and \
                self.gatewayapi_check_interval_qty > 0 and self.gatewayapi_check_interval_unit):
            if self.provider == 'gatewayapi': # Only clear if it was for gatewayapi
                 self.gatewayapi_next_balance_check = False
            return

        next_check_base = fields.Datetime.now() # Always schedule from now if this function is called
        self.gatewayapi_next_balance_check = next_check_base + timedelta(
            **{self.gatewayapi_check_interval_unit: self.gatewayapi_check_interval_qty}
        )
        _logger.info("GatewayAPI provider '%s': Next balance check scheduled for %s", self.name, self.gatewayapi_next_balance_check)

    @api.model
    def _cron_check_gatewayapi_balances(self):
        providers_to_check = self.search([
            ('provider', '=', 'gatewayapi'),
            ('gatewayapi_check_balance_enabled', '=', True),
            ('gatewayapi_next_balance_check', '<=', fields.Datetime.now())
        ])
        _logger.info("CRON: Checking GatewayAPI balances for %s provider(s).", len(providers_to_check))

        for provider_record in providers_to_check:
            log_prefix_cron = f"CRON Balance Check (Provider: {provider_record.name}):"
            try:
                client = provider_record._get_gatewayapi_client()
                balance_info = client.get_balance()
                credits = balance_info.get('credits')
                currency = balance_info.get('currency')

                if credits is not None and currency:
                    provider_record.gatewayapi_last_balance_check_result = _("OK (%(datetime)s): %(credits)s %(currency)s") % {
                        'datetime': fields.Datetime.now(), 'credits': credits, 'currency': currency
                    }
                    _logger.info("%s Success. Balance: %s %s", log_prefix_cron, credits, currency)
                    if credits <= provider_record.gatewayapi_min_credit_limit:
                        _logger.warning("%s LOW BALANCE DETECTED. Current: %s %s, Limit: %s",
                                        log_prefix_cron, credits, currency, provider_record.gatewayapi_min_credit_limit)
                        provider_record._send_gatewayapi_low_credit_notification(credits, currency)
                else:
                    error_msg_balance = _("Unexpected balance response: %s") % balance_info
                    provider_record.gatewayapi_last_balance_check_result = _("Error (%(datetime)s): %(error_msg)s") % {
                        'datetime': fields.Datetime.now(), 'error_msg': error_msg_balance
                    }
                    _logger.error("%s %s", log_prefix_cron, error_msg_balance)
            except Exception as e: # Catch any exception during the check for a single provider
                error_msg_exception = _("Error during balance check: %s") % str(e)
                provider_record.gatewayapi_last_balance_check_result = _("Failed (%(datetime)s): %(error)s") % {
                     'datetime': fields.Datetime.now(), 'error': error_msg_exception
                }
                _logger.error("%s %s", log_prefix_cron, error_msg_exception, exc_info=True)
            finally:
                # Always reschedule, even on error, to try again later.
                provider_record._schedule_next_gatewayapi_balance_check(force_now=True)
        return True

    def _send_gatewayapi_low_credit_notification(self, current_credits, currency):
        self.ensure_one()
        log_prefix_notify = f"Low Credit Notify (Provider: {self.name}):"
        subject = _("Low GatewayAPI Credit Alert for Provider: %s") % (self.gatewayapi_account_name or self.name)
        body_html = _(
            "<p>The GatewayAPI provider '<strong>%(provider_name)s</strong>' (used for SMS) has a low credit balance.</p>"
            "<p>Current Balance: <strong>%(credits)s %(currency)s</strong></p>"
            "<p>Configured Limit: <strong>%(limit)s %(currency)s</strong></p>"
            "<p>Please top up your GatewayAPI account to ensure continued SMS service.</p>"
            "<p><small>This notification is for the IAP Alternative Provider configuration: %(config_name)s.</small></p>"
        ) % {
            'provider_name': self.gatewayapi_account_name or self.name,
            'credits': current_credits, 'currency': currency,
            'limit': self.gatewayapi_min_credit_limit,
            'config_name': self.name
        }
        # Determine author for notifications (system user if from cron, otherwise current user)
        author_id = self.env.user.partner_id.id if self.env.user and self.env.user.exists() else self.env.ref('base.partner_root').id

        if self.gatewayapi_notify_channel_id:
            try:
                self.gatewayapi_notify_channel_id.with_context(mail_create_nosubscribe=True).message_post(
                    body=body_html, subject=subject, message_type='notification',
                    subtype_xmlid='mail.mt_comment', author_id=author_id
                )
                _logger.info("%s Sent notification to channel %s.", log_prefix_notify, self.gatewayapi_notify_channel_id.name)
            except Exception as e:
                _logger.error("%s Failed to send notification to channel %s: %s",
                              log_prefix_notify, self.gatewayapi_notify_channel_id.name, e, exc_info=True)

        if self.gatewayapi_notify_user_ids:
            partner_ids_to_notify = self.gatewayapi_notify_user_ids.mapped('partner_id').ids
            if partner_ids_to_notify:
                # Post a message on the provider record, which will notify followers (the users)
                self.message_post(
                    body=body_html, subject=subject, partner_ids=partner_ids_to_notify, # Notifying partners directly
                    message_type='notification', # This creates mail.message records
                    subtype_xmlid='mail.mt_note', # A general note type, appears in inbox
                    author_id=author_id,
                )
                _logger.info("%s Sent direct notifications to users: %s.", log_prefix_notify, self.gatewayapi_notify_user_ids.mapped('name'))

    @api.constrains('gatewayapi_check_interval_qty', 'gatewayapi_check_interval_unit', 'gatewayapi_check_balance_enabled', 'provider')
    def _check_gatewayapi_interval(self):
        for record in self:
            if record.provider == 'gatewayapi':
                if record.gatewayapi_check_balance_enabled and record.gatewayapi_check_interval_qty <= 0:
                    raise ValidationError(_("GatewayAPI Balance Check Interval must be positive if enabled."))
                if record.gatewayapi_check_balance_enabled and not record.gatewayapi_check_interval_unit:
                    raise ValidationError(_("GatewayAPI Balance Check Interval Unit must be set if enabled."))

    @api.constrains('provider', 'gatewayapi_sender_name')
    def _check_gatewayapi_sender_name(self):
        for record in self:
            if record.provider == 'gatewayapi' and record.gatewayapi_sender_name:
                sender = record.gatewayapi_sender_name
                if sender.isnumeric():
                    if not (3 <= len(sender) <= 15):
                         raise ValidationError(_("Numeric GatewayAPI Sender Name must be between 3 and 15 digits (e.g., 451234567)."))
                # Allow spaces in alphanumeric, but GatewayAPI might strip them or have own rules
                elif not (sender.replace(" ", "").isalnum() and 1 <= len(sender.replace(" ", "")) <= 11):
                     raise ValidationError(_("Alphanumeric GatewayAPI Sender Name must be 1-11 alphanumeric characters (excluding spaces)."))
