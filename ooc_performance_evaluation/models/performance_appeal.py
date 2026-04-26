from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .performance_utils import add_working_days


class PerformanceAppeal(models.Model):
    _name = "performance.appeal"
    _description = "Performance Appeal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "employee_id"
    _order = "id desc"

    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    evaluation_id = fields.Many2one("performance.evaluation", required=True, tracking=True)
    cycle_id = fields.Many2one("performance.cycle", related="evaluation_id.cycle_id", store=True)
    appeal_reason = fields.Char(required=True)
    appeal_description = fields.Text(required=True)
    requested_change = fields.Text()
    employee_attachment_ids = fields.Many2many("ir.attachment", string="Employee Attachments")
    manager_response = fields.Text()
    manager_recommendation = fields.Text()
    hr_decision = fields.Text()
    committee_notes = fields.Text()
    final_decision = fields.Text()
    submission_date = fields.Date(readonly=True)
    decision_date = fields.Date(readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("hr_review", "HR Review"),
            ("waiting_manager_response", "Waiting Manager Response"),
            ("committee_review", "Committee Review"),
            ("decision_issued", "Decision Issued"),
            ("closed", "Closed"),
            ("rejected_late", "Rejected Late"),
        ],
        default="draft",
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("evaluation_id") and not vals.get("employee_id"):
                vals["employee_id"] = self.env["performance.evaluation"].browse(vals["evaluation_id"]).employee_id.id
        return super().create(vals_list)

    def _get_appeal_deadline(self):
        self.ensure_one()
        cycle = self.evaluation_id.cycle_id
        if cycle.appeal_deadline:
            return cycle.appeal_deadline
        publish_date = cycle.result_publish_date or fields.Date.context_today(self)
        days = self.env["res.config.settings"].get_performance_int("appeal_working_days", 10)
        return add_working_days(publish_date, days)

    def action_submit(self):
        for appeal in self:
            deadline = appeal._get_appeal_deadline()
            today = fields.Date.context_today(appeal)
            if deadline and today > deadline:
                appeal.state = "rejected_late"
                continue
            appeal.write({"state": "submitted", "submission_date": today})
            appeal.evaluation_id.state = "appealed"

    def action_start_hr_review(self):
        self.write({"state": "hr_review"})

    def action_request_manager_response(self):
        self.write({"state": "waiting_manager_response"})

    def action_start_committee_review(self):
        self.write({"state": "committee_review"})

    def action_issue_decision(self):
        for appeal in self:
            if not appeal.final_decision:
                raise ValidationError(_("Final decision text is required before issuing a decision."))
            appeal.write({"state": "decision_issued", "decision_date": fields.Date.context_today(appeal)})
            appeal.evaluation_id._compute_all_scores()

    def action_close(self):
        self.write({"state": "closed"})
