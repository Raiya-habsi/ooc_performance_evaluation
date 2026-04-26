from odoo import _, api, fields, models

from .performance_utils import add_working_days


class PerformanceDevelopmentPlan(models.Model):
    _name = "performance.development.plan"
    _description = "Performance Development Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "employee_id"
    _order = "deadline, id desc"

    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    evaluation_id = fields.Many2one("performance.evaluation", required=True, tracking=True)
    cycle_id = fields.Many2one("performance.cycle", required=True, tracking=True)
    weakness_points = fields.Text()
    training_programs = fields.Text()
    professional_skills = fields.Text()
    leadership_skills = fields.Text()
    planned_activities = fields.Text()
    manager_id = fields.Many2one("hr.employee", required=True, tracking=True)
    hr_reviewer_id = fields.Many2one("hr.employee", tracking=True)
    deadline = fields.Date()
    progress = fields.Float()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("manager_prepared", "Manager Prepared"),
            ("hr_reviewed", "HR Reviewed"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("closed", "Closed"),
        ],
        default="draft",
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        days = self.env["res.config.settings"].get_performance_int("development_plan_working_days", 30)
        for record in records.filtered(lambda plan: not plan.deadline):
            record._set_default_deadline(days)
        return records

    def _set_default_deadline(self, days):
        for record in self:
            start_date = record.cycle_id.result_publish_date or fields.Date.context_today(record)
            record.deadline = add_working_days(start_date, days)
        return self

    def action_manager_prepare(self):
        self.write({"state": "manager_prepared"})

    def action_hr_review(self):
        self.write({"state": "hr_reviewed"})

    def action_start_progress(self):
        self.write({"state": "in_progress"})

    def action_complete(self):
        self.write({"state": "completed"})

    def action_close(self):
        self.write({"state": "closed"})
