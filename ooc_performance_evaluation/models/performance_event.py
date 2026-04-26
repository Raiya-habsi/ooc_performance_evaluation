from odoo import fields, models


class PerformanceEventParticipation(models.Model):
    _name = "performance.event.participation"
    _description = "Performance Event Participation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "event_name"
    _order = "event_date desc, id desc"

    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    cycle_id = fields.Many2one("performance.cycle", required=True, tracking=True)
    event_name = fields.Char(required=True)
    event_date = fields.Date(required=True)
    event_type = fields.Char()
    participation_role = fields.Char()
    quality_rating = fields.Float()
    manager_quality_comment = fields.Text()
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
    created_by_hr = fields.Boolean(default=False)
