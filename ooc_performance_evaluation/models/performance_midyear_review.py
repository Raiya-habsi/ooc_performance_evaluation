from odoo import fields, models


class PerformanceMidyearReview(models.Model):
    _name = "performance.midyear.review"
    _description = "Performance Mid-Year Review"
    _rec_name = "employee_id"
    _order = "review_date desc, id desc"

    employee_id = fields.Many2one("hr.employee", required=True)
    cycle_id = fields.Many2one("performance.cycle", required=True)
    manager_id = fields.Many2one("hr.employee", required=True)
    review_date = fields.Date(required=True, default=fields.Date.context_today)
    progress_summary = fields.Text()
    challenges = fields.Text()
    support_required = fields.Text()
    priority_changes = fields.Text()
    employee_comments = fields.Text()
    manager_comments = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("done", "Done")],
        default="draft",
    )
