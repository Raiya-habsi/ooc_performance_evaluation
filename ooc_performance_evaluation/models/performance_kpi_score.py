from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .performance_utils import get_param


class PerformanceKpiScore(models.Model):
    _name = "performance.kpi.score"
    _description = "Performance KPI Score"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "kpi_id"
    _order = "cycle_id desc, id"

    cycle_id = fields.Many2one("performance.cycle", required=True, tracking=True)
    kpi_id = fields.Many2one("performance.kpi", required=True, tracking=True)
    owner_type = fields.Selection(
        [
            ("organization", "Organization"),
            ("department", "Department"),
            ("section", "Section"),
        ],
        compute="_compute_owner_fields",
        store=True,
    )
    department_id = fields.Many2one(
        "hr.department", compute="_compute_owner_fields", store=True, readonly=False
    )
    section_id = fields.Many2one("hr.department", compute="_compute_owner_fields", store=True, readonly=False)
    target_value = fields.Float(required=True, tracking=True)
    actual_value = fields.Float(tracking=True)
    weight = fields.Float(related="kpi_id.weight", store=True, readonly=True)
    achievement_score = fields.Float(compute="_compute_scores", store=True)
    weighted_score = fields.Float(compute="_compute_scores", store=True)
    evidence_attachment_ids = fields.Many2many("ir.attachment", string="Evidence")
    remarks = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("confirmed", "Confirmed"),
            ("locked", "Locked"),
        ],
        default="draft",
        tracking=True,
    )
    confirmed_by = fields.Many2one("res.users", readonly=True)
    confirmed_date = fields.Datetime(readonly=True)

    _sql_constraints = [
        ("kpi_cycle_unique", "unique(cycle_id, kpi_id)", "Each KPI can only have one score sheet per cycle."),
    ]

    @api.depends("kpi_id", "kpi_id.kpi_level", "kpi_id.department_id", "kpi_id.section_id")
    def _compute_owner_fields(self):
        mapping = {
            "organization": "organization",
            "department": "department",
            "section": "section",
        }
        for record in self:
            record.owner_type = mapping.get(record.kpi_id.kpi_level)
            record.department_id = record.kpi_id.department_id
            record.section_id = record.kpi_id.section_id

    @api.depends("target_value", "actual_value", "weight")
    def _compute_scores(self):
        cap_enabled = get_param(self.env, "score_cap", True, bool)
        for record in self:
            if record.target_value:
                achievement = (record.actual_value / record.target_value) * 100.0
            else:
                achievement = 0.0
            if cap_enabled:
                achievement = min(achievement, 100.0)
            record.achievement_score = achievement
            record.weighted_score = (achievement * record.weight) / 100.0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.kpi_id.kpi_level == "employee":
                raise ValidationError(_("Institutional KPI score sheets cannot be created for employee-level KPIs."))
            if not record.target_value:
                record.target_value = record.kpi_id.target_value
        return records

    def action_submit(self):
        self.write({"state": "submitted"})

    def action_confirm(self):
        for record in self:
            if record.state not in ("draft", "submitted"):
                continue
            record.write(
                {
                    "state": "confirmed",
                    "confirmed_by": self.env.user.id,
                    "confirmed_date": fields.Datetime.now(),
                }
            )
            record.cycle_id.evaluation_ids._compute_all_scores()

    def action_lock(self):
        self.write({"state": "locked"})

    def write(self, vals):
        protected_fields = {"actual_value", "remarks", "evidence_attachment_ids", "target_value"}
        install_mode = self.env.context.get("install_mode")
        for record in self:
            if record.state == "locked" and protected_fields.intersection(vals) and not install_mode:
                raise UserError(_("Locked KPI score sheets cannot be modified."))
        result = super().write(vals)
        if protected_fields.intersection(vals):
            self.mapped("cycle_id").evaluation_ids._compute_all_scores()
        return result
