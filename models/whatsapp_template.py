from odoo import api, fields, models


class WhatsAppTemplate(models.Model):
    _name = 'whatsapp.template'
    _description = 'WhatsApp Message Template'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Display Name', required=True)
    template_name = fields.Char(string='Template Name', required=True,
                                 help='Exact template name as registered in WhatsApp')
    
    account_id = fields.Many2one('whatsapp.account', string='WhatsApp Account',
                                  required=True, ondelete='cascade')
    
    language = fields.Char(string='Language Code', default='en',
                           help='Language code e.g., en, en_US, es')
    
    category = fields.Selection([
        ('marketing', 'Marketing'),
        ('utility', 'Utility'),
        ('authentication', 'Authentication'),
    ], string='Category', default='utility')
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending')
    
    content = fields.Text(string='Content Preview',
                          help='Template body text (may include {{1}}, {{2}} placeholders)')
    
    header_type = fields.Selection([
        ('none', 'None'),
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
    ], string='Header Type', default='none')
    
    header_text = fields.Char(string='Header Text')
    
    footer_text = fields.Char(string='Footer Text')
    
    has_buttons = fields.Boolean(string='Has Buttons')
    
    active = fields.Boolean(default=True)
    
    _sql_constraints = [
        ('template_account_unique', 'unique(template_name, account_id)',
         'Template name must be unique per account!')
    ]

    def action_send_test(self):
        """Open wizard to send test template message."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'whatsapp.message.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_account_id': self.account_id.id,
                'default_template_id': self.id,
                'default_message_type': 'template',
            }
        }
