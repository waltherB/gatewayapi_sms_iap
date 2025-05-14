# -*- coding: utf-8 -*-
import requests
import json
import logging
from odoo import _ # Import _ for translations
from odoo.exceptions import UserError, ValidationError

DEFAULT_GATEWAYAPI_BASE_URL = "https://gatewayapi.eu"
_logger = logging.getLogger(__name__)

GSM7_BASIC_CHARS = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENDED_CHARS = "^{}\\[~]|€"
ALL_GSM7_CHARS = GSM7_BASIC_CHARS + GSM7_EXTENDED_CHARS

def message_requires_ucs2(message_text):
    if not message_text:
        return False
    try:
        message_text.encode('ascii')
        for char in message_text:
            if char not in ALL_GSM7_CHARS:
                _logger.debug(f"Character '{char}' (ord: {ord(char)}) requires UCS-2 as it's not in simplified GSM-7 set.")
                return True
        return False
    except UnicodeEncodeError:
        _logger.debug(f"Message contains non-ASCII characters (e.g., emojis), requires UCS-2.")
        return True

class GatewayApiClient:
    def __init__(self, api_token, base_url=None):
        if not api_token:
            raise ValidationError(_("GatewayAPI API Token is required."))
        self.api_token = api_token
        self.base_url = base_url or DEFAULT_GATEWAYAPI_BASE_URL
        self.session = requests.Session()
        self.session.auth = (self.api_token, '')

    def _request(self, method, endpoint, payload=None, params=None):
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        _logger.debug("GatewayAPI Request: Method=%s, URL=%s, Headers=%s, Payload=%s, Params=%s",
                      method, url, headers, json.dumps(payload) if payload else "None", params)
        try:
            response = self.session.request(method, url, json=payload, params=params, headers=headers, timeout=20)
            _logger.debug("GatewayAPI Response: Status=%s, URL=%s, Response Body=%s",
                          response.status_code, response.url, response.text)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg_detail = e.response.text
            try:
                error_json = e.response.json()
                if isinstance(error_json, dict):
                    if 'message' in error_json: error_msg_detail = error_json['message']
                    elif 'detail' in error_json: error_msg_detail = error_json['detail']
                    elif 'variables' in error_json and isinstance(error_json['variables'], list) and error_json['variables']:
                        first_var_error = next((var.get('message') for var in error_json['variables'] if 'message' in var), None)
                        if first_var_error: error_msg_detail = first_var_error
                elif isinstance(error_json, list) and error_json:
                     first_error = error_json[0]
                     if isinstance(first_error, dict) and 'message' in first_error: error_msg_detail = first_error['message']
                     else: error_msg_detail = str(first_error)
            except (json.JSONDecodeError, TypeError): pass
            error_msg = _("GatewayAPI HTTP Error: %(status_code)s - %(detail)s") % {'status_code': e.response.status_code, 'detail': error_msg_detail}
            _logger.error(error_msg)
            raise UserError(error_msg)
        except requests.exceptions.Timeout:
            _logger.error("GatewayAPI Request Timeout: %s %s", method, url)
            raise UserError(_("GatewayAPI Connection Timeout. Please try again later."))
        except requests.exceptions.RequestException as e:
            _logger.error("GatewayAPI Connection Error: %s", e)
            raise UserError(_("GatewayAPI Connection Error: %s") % e)

    def get_balance(self):
        return self._request('GET', 'rest/me')

    def send_sms(self, sender, recipients, message_body):
        if not isinstance(recipients, list):
            recipients = [recipients]

        payload = {
            "sender": sender,
            "message": message_body,
            "recipients": [{"msisdn": str(number)} for number in recipients]
        }

        if message_requires_ucs2(message_body):
            payload["encoding"] = "UCS2"
            payload["class"] = "standard"
            _logger.info("Message for %s requires UCS-2 encoding. Sending with class: %s.",
                         [r['msisdn'] for r in payload['recipients']], payload["class"])
        else:
            payload["encoding"] = "GSM7"
            payload["class"] = "standard"
            _logger.info("Message for %s uses GSM-7 encoding. Sending with class: %s.",
                         [r['msisdn'] for r in payload['recipients']], payload["class"])

        return self._request('POST', 'rest/mtsms', payload=payload)
