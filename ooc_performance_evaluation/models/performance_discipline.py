from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PerformanceDisciplineScore(models.Model):
    _name = "performance.discipline.score"
    _description = "Performance Discipline Score"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "employee_id"
    _order = "cycle_id desc, employee_id"

    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    cycle_id = fields.Many2one("performance.cycle", required=True, tracking=True)
    late_count = fields.Integer()
    early_leave_count = fields.Integer()
    absence_count = fields.Integer()
    approved_leave_count = fields.Integer()
    official_mission_count = fields.Integer()
    penalty_points = fields.Float(compute="_compute_score", store=True)
    score = fields.Float(compute="_compute_score", store=True)
    hr_override_score = fields.Float(tracking=True)
    override_reason = fields.Text()
    override_attachment_ids = fields.Many2many("ir.attachment", string="Override Attachments")
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("locked", "Locked")],
        default="draft",
        tracking=True,
    )

    _sql_constraints = [
        (
            "discipline_employee_cycle_unique",
            "unique(employee_id, cycle_id)",
            "An employee can only have one discipline score per cycle.",
        )
    ]

    @api.depends("late_count", "early_leave_count", "absence_count")
    def _compute_score(self):
        for record in self:
            record.penalty_points = record.late_count + record.early_leave_count + (record.absence_count * 5)
            record.score = max(0.0, 100.0 - record.penalty_points)

    def _get_date_range(self):
        self.ensure_one()
        start = self.cycle_id.start_date
        end = self.cycle_id.final_evaluation_end or self.cycle_id.result_publish_date or fields.Date.context_today(self)
        return start, end

    def action_refresh_from_sources(self):
        leave_model = self.env["hr.leave"]
        attendance_model = self.env["hr.attendance"]
        for record in self:
            start_date, end_date = record._get_date_range()
            if not start_date:
                raise UserError(_("The cycle must have a start date to compute discipline scores."))
            attendances = attendance_model.search(
                [
                    ("employee_id", "=", record.employee_id.id),
                    ("check_in", ">=", fields.Datetime.to_datetime(start_date)),
                    ("check_in", "<", fields.Datetime.to_datetime(end_date + timedelta(days=1))),
                ]
            )
            approved_leaves = leave_model.search(
                [
                    ("employee_id", "=", record.employee_id.id),
                    ("state", "=", "validate"),
                    ("date_from", "<=", fields.Datetime.to_datetime(end_date + timedelta(days=1))),
                    ("date_to", ">=", fields.Datetime.to_datetime(start_date)),
                ]
            )
            work_days = 0
            cursor = start_date
            while cursor <= end_date:
                if cursor.weekday() < 5:
                    work_days += 1
                cursor += timedelta(days=1)
            attendance_dates = {fields.Datetime.context_timestamp(record, att.check_in).date() for att in attendances if att.check_in}
            late_count = sum(
                1
                for att in attendances
                if att.check_in and fields.Datetime.context_timestamp(record, att.check_in).time().hour >= 9
            )
            early_leave_count = sum(
                1
                for att in attendances
                if att.check_out and fields.Datetime.context_timestamp(record, att.check_out).time().hour < 17
            )
            approved_leave_count = 0
            official_mission_count = 0
            leave_dates = set()
            mission_dates = set()
            for leave in approved_leaves:
                leave_start = fields.Datetime.context_timestamp(record, leave.date_from).date()
                leave_end = fields.Datetime.context_timestamp(record, leave.date_to).date()
                current = leave_start
                is_mission = "mission" in (leave.holiday_status_id.name or "").lower()
                while current <= leave_end:
                    if current.weekday() < 5:
                        if is_mission:
                            mission_dates.add(current)
                        else:
                            leave_dates.add(current)
                    current += timedelta(days=1)
            approved_leave_count = len(leave_dates)
            official_mission_count = len(mission_dates)
            absence_count = max(0, work_days - len(attendance_dates | leave_dates | mission_dates))
            record.write(
                {
                    "late_count": late_count,
                    "early_leave_count": early_leave_count,
                    "absence_count": absence_count,
                    "approved_leave_count": approved_leave_count,
                    "official_mission_count": official_mission_count,
                }
            )

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_lock(self):
        self.write({"state": "locked"})

    @api.constrains("hr_override_score", "override_reason")
    def _check_override_data(self):
        for record in self:
            if record.hr_override_score not in (False, None):
                if not record.override_reason or not record.override_attachment_ids:
                    raise ValidationError(_("HR overrides require a reason and at least one attachment."))
