from odoo import api, fields, models
from odoo.exceptions import UserError


class WhatsAppMessageSendWizard(models.TransientModel):
    _name = 'whatsapp.message.send.wizard'
    _description = 'Send WhatsApp Message Wizard'

    account_id = fields.Many2one('whatsapp.account', string='WhatsApp Account',
                                  required=True, 
                                  domain=[('state', '=', 'connected')])
    
    phone_number = fields.Char(string='Phone Number', required=True,
                               help='Phone number with country code (no + prefix)')
    
    message_type = fields.Selection([
        ('text', 'Text Message'),
        ('template', 'Template Message'),
    ], string='Message Type', default='text', required=True)
    
    message_text = fields.Text(string='Message')
    
    template_id = fields.Many2one('whatsapp.template', string='Template',
                                   domain="[('account_id', '=', account_id), ('status', '=', 'approved')]")

    @api.onchange('account_id')
    def _onchange_account_id(self):
        if self.template_id and self.template_id.account_id != self.account_id:
            self.template_id = False

    def action_send(self):
        """Send the WhatsApp message."""
        self.ensure_one()
        
        if not self.account_id:
            raise UserError("Please select a WhatsApp account")
        
        if not self.phone_number:
            raise UserError("Please enter a phone number")
        
        # Clean phone number
        phone = self.phone_number.replace('+', '').replace(' ', '').replace('-', '')
        
        if self.message_type == 'text':
            if not self.message_text:
                raise UserError("Please enter a message")
            result = self.account_id.send_text_message(phone, self.message_text)
        else:
            if not self.template_id:
                raise UserError("Please select a template")
            result = self.account_id.send_template_message(
                phone, 
                self.template_id.template_name,
                self.template_id.language
            )
        
        if result and result.status == 'sent':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Message Sent',
                    'message': f"Message sent successfully to {phone}",
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            error_msg = result.error_message if result else "Unknown error"
            raise UserError(f"Failed to send message: {error_msg}")
