import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class WhatsAppConversation(models.Model):
    _name = 'whatsapp.conversation'
    _description = 'WhatsApp Conversation'
    _order = 'last_message_date desc'
    _rec_name = 'display_name'

    account_id = fields.Many2one('whatsapp.account', string='WhatsApp Account',
                                  required=True, ondelete='cascade')
    
    phone_number = fields.Char(string='Phone Number', required=True, index=True,
                               help='Phone number with country code (no + prefix)')
    
    partner_id = fields.Many2one('res.partner', string='Contact',
                                  compute='_compute_partner_id', store=True)
    
    message_ids = fields.One2many('whatsapp.message', 'conversation_id', 
                                   string='Messages')
    
    last_message_date = fields.Datetime(string='Last Message', 
                                         compute='_compute_last_message',
                                         store=True)
    
    last_message_preview = fields.Char(string='Last Message Preview',
                                        compute='_compute_last_message',
                                        store=True)
    
    unread_count = fields.Integer(string='Unread Messages',
                                   compute='_compute_unread_count',
                                   store=True)
    
    display_name = fields.Char(string='Display Name', 
                                compute='_compute_display_name')
    
    _sql_constraints = [
        ('unique_phone_account', 'unique(phone_number, account_id)',
         'A conversation with this phone number already exists for this account.')
    ]

    @api.depends('partner_id', 'phone_number')
    def _compute_display_name(self):
        for record in self:
            if record.partner_id:
                record.display_name = record.partner_id.name
            else:
                record.display_name = record.phone_number

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

    @api.depends('message_ids.timestamp', 'message_ids.content')
    def _compute_last_message(self):
        for record in self:
            last_msg = self.env['whatsapp.message'].search([
                ('conversation_id', '=', record.id)
            ], order='timestamp desc', limit=1)
            if last_msg:
                record.last_message_date = last_msg.timestamp
                preview = (last_msg.content or '')[:50]
                if len(last_msg.content or '') > 50:
                    preview += '...'
                record.last_message_preview = preview
            else:
                record.last_message_date = False
                record.last_message_preview = ''

    @api.depends('message_ids.status', 'message_ids.direction')
    def _compute_unread_count(self):
        for record in self:
            record.unread_count = self.env['whatsapp.message'].search_count([
                ('conversation_id', '=', record.id),
                ('direction', '=', 'incoming'),
                ('status', '!=', 'read'),
            ])

    @api.model
    def get_or_create(self, account_id, phone_number):
        """Get existing conversation or create a new one."""
        conversation = self.search([
            ('account_id', '=', account_id),
            ('phone_number', '=', phone_number),
        ], limit=1)
        
        if not conversation:
            conversation = self.create({
                'account_id': account_id,
                'phone_number': phone_number,
            })
        
        return conversation.id

    def action_open_chat(self):
        """Open the chat interface for this conversation."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'whatsapp_chat',
            'context': {
                'active_conversation_id': self.id,
            }
        }

    def get_messages(self, limit=50, offset=0):
        """Get messages for this conversation, ordered oldest first for chat display."""
        self.ensure_one()
        messages = self.env['whatsapp.message'].search([
            ('conversation_id', '=', self.id)
        ], order='timestamp asc', limit=limit, offset=offset)
        
        return [{
            'id': msg.id,
            'direction': msg.direction,
            'content': msg.content,
            'message_type': msg.message_type,
            'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
            'status': msg.status,
            'media_url': msg.media_url,
        } for msg in messages]

    def send_message(self, content, message_type='text'):
        """Send a message in this conversation."""
        self.ensure_one()
        
        # Send via WhatsApp API (which creates the record)
        # We pass conversation_id so it's linked immediately
        message = self.account_id.send_text_message(
            self.phone_number, 
            content, 
            conversation_id=self.id
        )
        
        return {
            'id': message.id,
            'direction': message.direction,
            'content': message.content,
            'message_type': message.message_type,
            'timestamp': message.timestamp.isoformat() if message.timestamp else None,
            'status': message.status,
            'error_message': message.error_message,
        }
