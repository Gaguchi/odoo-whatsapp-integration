import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class WhatsAppMessage(models.Model):
    _name = 'whatsapp.message'
    _description = 'WhatsApp Message'
    _order = 'timestamp desc, id desc'
    _rec_name = 'display_name'

    account_id = fields.Many2one('whatsapp.account', string='WhatsApp Account',
                                  required=True, ondelete='cascade')
    
    conversation_id = fields.Many2one('whatsapp.conversation', string='Conversation',
                                       ondelete='cascade', index=True)
    
    direction = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ], string='Direction', required=True, default='outgoing')
    
    phone_number = fields.Char(string='Phone Number', required=True, index=True,
                               help='Phone number with country code (no + prefix)')
    
    message_type = fields.Selection([
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('location', 'Location'),
        ('contacts', 'Contacts'),
        ('sticker', 'Sticker'),
        ('template', 'Template'),
        ('interactive', 'Interactive'),
        ('reaction', 'Reaction'),
    ], string='Message Type', default='text', required=True)
    
    content = fields.Text(string='Content', help='Message body or description')
    media_url = fields.Char(string='Media URL', help='URL for media messages')
    media_mime_type = fields.Char(string='Media MIME Type')
    
    whatsapp_message_id = fields.Char(string='WhatsApp Message ID', index=True,
                                       help='Message ID from WhatsApp API')
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ], string='Status', default='pending')
    
    error_message = fields.Text(string='Error Message')
    
    # Link to Odoo partner
    partner_id = fields.Many2one('res.partner', string='Contact',
                                  compute='_compute_partner_id', store=True)
    
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, index=True)
    
    display_name = fields.Char(string='Display Name', compute='_compute_display_name')
    
    @api.depends('phone_number', 'content', 'message_type')
    def _compute_display_name(self):
        for record in self:
            preview = (record.content or '')[:30]
            if len(record.content or '') > 30:
                preview += '...'
            record.display_name = f"{record.phone_number}: {preview}"

    @api.depends('phone_number')
    def _compute_partner_id(self):
        """Try to match phone number to a partner."""
        for record in self:
            phone = record.phone_number or ''
            if not phone:
                record.partner_id = False
                continue
            phone_short = phone[-10:] if len(phone) > 10 else phone
            partner = self.env['res.partner'].search([
                '|', '|',
                ('phone', 'ilike', phone),
                ('mobile', 'ilike', phone),
                ('phone', 'ilike', phone_short),
            ], limit=1)
            record.partner_id = partner

    def action_open_partner(self):
        """Open the linked partner form."""
        self.ensure_one()
        if self.partner_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
                'view_mode': 'form',
            }
        return False

    def action_reply(self):
        """Open a wizard to reply to this message."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'whatsapp.message.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_account_id': self.account_id.id,
                'default_phone_number': self.phone_number,
            }
        }

    @api.model
    def process_webhook_message(self, account, message_data, contact_data):
        """
        Process an incoming message from webhook.
        
        :param account: whatsapp.account record
        :param message_data: Message dict from webhook payload
        :param contact_data: Contact dict from webhook payload
        """
        message_type = message_data.get('type', 'text')
        content = ''
        media_url = None
        
        if message_type == 'text':
            content = message_data.get('text', {}).get('body', '')
        elif message_type == 'image':
            content = message_data.get('image', {}).get('caption', '[Image]')
            media_url = message_data.get('image', {}).get('id')
        elif message_type == 'document':
            content = message_data.get('document', {}).get('filename', '[Document]')
            media_url = message_data.get('document', {}).get('id')
        elif message_type == 'audio':
            content = '[Audio Message]'
            media_url = message_data.get('audio', {}).get('id')
        elif message_type == 'video':
            content = message_data.get('video', {}).get('caption', '[Video]')
            media_url = message_data.get('video', {}).get('id')
        elif message_type == 'location':
            loc = message_data.get('location', {})
            content = f"📍 {loc.get('name', '')} ({loc.get('latitude')}, {loc.get('longitude')})"
        elif message_type == 'reaction':
            content = f"Reaction: {message_data.get('reaction', {}).get('emoji', '')}"
        else:
            content = f'[{message_type.title()} message]'
        
        phone = contact_data.get('wa_id', message_data.get('from', ''))
        
        # Get or create conversation for this phone number
        conversation = self.env['whatsapp.conversation'].get_or_create(
            account.id, phone
        )
        
        return self.create({
            'account_id': account.id,
            'conversation_id': conversation.id,
            'direction': 'incoming',
            'phone_number': phone,
            'message_type': message_type,
            'content': content,
            'media_url': media_url,
            'whatsapp_message_id': message_data.get('id'),
            'status': 'delivered',
            'timestamp': fields.Datetime.now(),
        })

    @api.model
    def process_status_update(self, account, status_data):
        """
        Update message status from webhook.
        
        :param account: whatsapp.account record
        :param status_data: Status dict from webhook payload
        """
        message_id = status_data.get('id')
        status = status_data.get('status')
        
        if not message_id or not status:
            return False
        
        message = self.search([
            ('whatsapp_message_id', '=', message_id),
            ('account_id', '=', account.id),
        ], limit=1)
        
        if message:
            status_map = {
                'sent': 'sent',
                'delivered': 'delivered',
                'read': 'read',
                'failed': 'failed',
            }
            new_status = status_map.get(status)
            if new_status:
                message.status = new_status
                if status == 'failed':
                    errors = status_data.get('errors', [])
                    if errors:
                        message.error_message = errors[0].get('message', 'Unknown error')
        
        return message
