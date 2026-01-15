import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WhatsAppWebhook(http.Controller):
    """
    WhatsApp Webhook Controller
    
    Handles webhook verification and incoming message notifications
    from the WhatsApp Cloud API.
    """

    @http.route('/whatsapp/webhook', type='http', auth='public', methods=['GET'], csrf=False)
    def verify_webhook(self, **kwargs):
        """
        Handle webhook verification from Meta.
        
        Meta sends a GET request with:
        - hub.mode: should be 'subscribe'
        - hub.verify_token: your custom verify token
        - hub.challenge: random string to return if valid
        """
        mode = kwargs.get('hub.mode')
        token = kwargs.get('hub.verify_token')
        challenge = kwargs.get('hub.challenge')
        
        _logger.info(f"WhatsApp webhook verification: mode={mode}, token={token}")
        
        if mode == 'subscribe' and token:
            # Find account with matching verify token
            account = request.env['whatsapp.account'].sudo().search([
                ('verify_token', '=', token),
                ('active', '=', True)
            ], limit=1)
            
            if account:
                _logger.info(f"Webhook verified for account: {account.name}")
                return challenge
            else:
                _logger.warning(f"Webhook verification failed: token not found")
                return 'Forbidden', 403
        
        return 'Bad Request', 400

    @http.route('/whatsapp/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def receive_webhook(self, **kwargs):
        """
        Handle incoming webhook notifications from WhatsApp.
        
        Processes:
        - Incoming messages
        - Message status updates (sent, delivered, read)
        """
        try:
            data = request.get_json_data()
            _logger.info(f"WhatsApp webhook received: {json.dumps(data, indent=2)}")
            
            # Normalize data structure to handle both standard and flattened payloads
            entries = data.get('entry', [])
            
            # If no 'entry' key, check if it looks like a flattened 'changes' object
            if not entries and 'field' in data and 'value' in data:
                 entries = [{'changes': [data]}]
            
            # Process each entry
            for entry in entries:
                changes = entry.get('changes', [])
                for change in changes:
                    if change.get('field') != 'messages':
                        continue
                    
                    value = change.get('value', {})
                    metadata = value.get('metadata', {})
                    phone_number_id = metadata.get('phone_number_id')
                    
                    if not phone_number_id:
                        continue
                    
                    # Find the corresponding account
                    account = request.env['whatsapp.account'].sudo().search([
                        ('phone_number_id', '=', phone_number_id),
                        ('active', '=', True)
                    ], limit=1)
                    
                    if not account:
                        _logger.warning(f"No account found for phone_number_id: {phone_number_id}")
                        continue
                    
                    # Process messages
                    messages = value.get('messages', [])
                    contacts = value.get('contacts', [])
                    
                    for message in messages:
                        contact = next((c for c in contacts if c.get('wa_id') == message.get('from')), {})
                        msg_record = request.env['whatsapp.message'].sudo().process_webhook_message(
                            account, message, contact
                        )
                        # Send bus notification for new message
                        if msg_record:
                            self._notify_new_message(account.id, msg_record)
                    
                    # Process status updates
                    statuses = value.get('statuses', [])
                    for status in statuses:
                        msg_record = request.env['whatsapp.message'].sudo().process_status_update(
                            account, status
                        )
                        # Send bus notification for status update
                        if msg_record:
                            self._notify_status_update(account.id, msg_record)
            
            return 'OK'
            
        except Exception as e:
            _logger.error(f"WhatsApp webhook error: {str(e)}", exc_info=True)
            return 'Error', 500

    @http.route('/whatsapp/webhook/status', type='json', auth='user', methods=['POST'])
    def webhook_status(self, **kwargs):
        """
        Check webhook configuration status (for Odoo users).
        """
        try:
            accounts = request.env['whatsapp.account'].search([('active', '=', True)])
            return {
                'status': 'ok',
                'accounts': [{
                    'id': acc.id,
                    'name': acc.name,
                    'state': acc.state,
                    'phone_number_id': acc.phone_number_id,
                } for acc in accounts]
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def _notify_new_message(self, account_id, message):
        """Send bus notification for new incoming message."""
        try:
            channel = f'whatsapp_channel_{account_id}'
            notification = {
                'type': 'new_message',
                'account_id': account_id,
                'conversation_id': message.conversation_id.id if message.conversation_id else None,
                'message': {
                    'id': message.id,
                    'direction': message.direction,
                    'content': message.content,
                    'message_type': message.message_type,
                    'timestamp': message.timestamp.isoformat() if message.timestamp else None,
                    'status': message.status,
                    'phone_number': message.phone_number,
                }
            }
            request.env['bus.bus'].sudo()._sendone(channel, 'whatsapp.message', notification)
            _logger.info(f"Bus notification sent for new message on channel: {channel}")
        except Exception as e:
            _logger.error(f"Failed to send bus notification: {e}")

    def _notify_status_update(self, account_id, message):
        """Send bus notification for message status update."""
        try:
            channel = f'whatsapp_channel_{account_id}'
            notification = {
                'type': 'status_update',
                'account_id': account_id,
                'message_id': message.id,
                'whatsapp_message_id': message.whatsapp_message_id,
                'status': message.status,
                'error_message': message.error_message,
            }
            request.env['bus.bus'].sudo()._sendone(channel, 'whatsapp.status', notification)
        except Exception as e:
            _logger.error(f"Failed to send status bus notification: {e}")
