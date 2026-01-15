import json
import logging
import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v22.0"


class WhatsAppAccount(models.Model):
    _name = 'whatsapp.account'
    _description = 'WhatsApp Business Account'
    _rec_name = 'name'

    name = fields.Char(string='Account Name', required=True)
    phone_number_id = fields.Char(string='Phone Number ID', required=True,
                                   help='Your WhatsApp Phone Number ID from Meta Developer Console')
    access_token = fields.Char(string='Access Token', required=True,
                                help='Permanent Access Token from Meta Developer Console')
    waba_id = fields.Char(string='WhatsApp Business Account ID',
                          help='Your WABA ID from Meta Developer Console')
    app_id = fields.Char(string='App ID',
                         help='Your Meta App ID')
    app_secret = fields.Char(string='App Secret',
                             help='Your Meta App Secret')
    verify_token = fields.Char(string='Webhook Verify Token', required=True,
                               help='Custom token for webhook verification (you define this)')
    
    state = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connected', 'Connected'),
    ], string='Status', default='disconnected', readonly=True)
    
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)
    
    message_ids = fields.One2many('whatsapp.message', 'account_id', string='Messages')
    template_ids = fields.One2many('whatsapp.template', 'account_id', string='Templates')
    
    _sql_constraints = [
        ('phone_number_id_unique', 'unique(phone_number_id)',
         'This Phone Number ID is already registered!')
    ]

    def _get_headers(self):
        """Get API headers with authorization."""
        self.ensure_one()
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }

    def action_test_connection(self):
        """Test the WhatsApp API connection."""
        self.ensure_one()
        url = f"{WHATSAPP_API_URL}/{self.phone_number_id}"
        
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            data = response.json()
            
            self.state = 'connected'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Successful',
                    'message': f"Connected to WhatsApp: {data.get('display_phone_number', 'Unknown')}",
                    'type': 'success',
                    'sticky': False,
                }
            }
        except requests.exceptions.RequestException as e:
            self.state = 'disconnected'
            raise UserError(f"Connection failed: {str(e)}")

    def send_text_message(self, to, message_text, conversation_id=None):
        """
        Send a text message via WhatsApp.
        
        :param to: Recipient phone number (with country code, no +)
        :param message_text: Text content to send
        :param conversation_id: Optional conversation ID to link
        :return: whatsapp.message record
        """
        self.ensure_one()
        url = f"{WHATSAPP_API_URL}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message_text
            }
        }
        
        try:
            response = requests.post(url, headers=self._get_headers(), 
                                     json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            message_id = data.get('messages', [{}])[0].get('id')
            
            # Log the outgoing message
            message = self.env['whatsapp.message'].create({
                'account_id': self.id,
                'conversation_id': conversation_id,
                'direction': 'outgoing',
                'phone_number': to,
                'message_type': 'text',
                'content': message_text,
                'whatsapp_message_id': message_id,
                'status': 'sent',
            })
            
            return message
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"WhatsApp send failed: {str(e)}")
            
            # Log failed message
            message = self.env['whatsapp.message'].create({
                'account_id': self.id,
                'conversation_id': conversation_id,
                'direction': 'outgoing',
                'phone_number': to,
                'message_type': 'text',
                'content': message_text,
                'status': 'failed',
                'error_message': str(e),
            })
            return message

    def send_template_message(self, to, template_name, language_code='en', components=None, conversation_id=None):
        """
        Send a template message via WhatsApp.
        
        :param to: Recipient phone number
        :param template_name: WhatsApp approved template name
        :param language_code: Template language code
        :param components: Template components (header, body, button params)
        :param conversation_id: Optional conversation ID to link
        :return: whatsapp.message record
        """
        self.ensure_one()
        url = f"{WHATSAPP_API_URL}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }
        
        if components:
            payload["template"]["components"] = components
        
        try:
            response = requests.post(url, headers=self._get_headers(),
                                     json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            message_id = data.get('messages', [{}])[0].get('id')
            
            message = self.env['whatsapp.message'].create({
                'account_id': self.id,
                'conversation_id': conversation_id,
                'direction': 'outgoing',
                'phone_number': to,
                'message_type': 'template',
                'content': f"Template: {template_name}",
                'whatsapp_message_id': message_id,
                'status': 'sent',
            })
            
            return message
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"WhatsApp template send failed: {str(e)}")
            
            message = self.env['whatsapp.message'].create({
                'account_id': self.id,
                'conversation_id': conversation_id,
                'direction': 'outgoing',
                'phone_number': to,
                'message_type': 'template',
                'content': f"Template: {template_name}",
                'status': 'failed',
                'error_message': str(e),
            })
            return message

    def action_sync_templates(self):
        """Sync message templates from WhatsApp Business API."""
        self.ensure_one()
        
        if not self.waba_id:
            raise UserError("WABA ID is required to sync templates")
        
        url = f"{WHATSAPP_API_URL}/{self.waba_id}/message_templates"
        
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            data = response.json()
            
            templates = data.get('data', [])
            synced_count = 0
            
            for template in templates:
                existing = self.env['whatsapp.template'].search([
                    ('account_id', '=', self.id),
                    ('template_name', '=', template.get('name'))
                ], limit=1)
                
                vals = {
                    'name': template.get('name', '').replace('_', ' ').title(),
                    'template_name': template.get('name'),
                    'language': template.get('language', 'en'),
                    'category': template.get('category', 'utility').lower(),
                    'status': template.get('status', 'PENDING').lower(),
                    'account_id': self.id,
                }
                
                # Extract content from components
                components = template.get('components', [])
                for comp in components:
                    if comp.get('type') == 'BODY':
                        vals['content'] = comp.get('text', '')
                        break
                
                if existing:
                    existing.write(vals)
                else:
                    self.env['whatsapp.template'].create(vals)
                synced_count += 1
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Templates Synced',
                    'message': f"Synced {synced_count} templates from WhatsApp",
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except requests.exceptions.RequestException as e:
            raise UserError(f"Failed to sync templates: {str(e)}")
