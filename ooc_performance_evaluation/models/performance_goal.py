from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PerformanceGoal(models.Model):
    _name = "performance.goal"
    _description = "Performance Goal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "cycle_id desc, priority, id"

    name = fields.Char(required=True)
    cycle_id = fields.Many2one("performance.cycle", required=True)
    department_id = fields.Many2one("hr.department", required=True)
    section_id = fields.Many2one("hr.department")
    manager_id = fields.Many2one("hr.employee", required=True)
    parent_kpi_id = fields.Many2one("performance.kpi", required=True)
    target_value = fields.Float(required=True)
    measure_unit = fields.Char()
    weight = fields.Float(required=True)
    priority = fields.Selection(
        [("1", "High"), ("2", "Medium"), ("3", "Low")],
        default="2",
    )
    description = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("available", "Available"),
            ("selected", "Selected"),
            ("manager_approved", "Manager Approved"),
            ("hr_approved", "HR Approved"),
            ("locked", "Locked"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )

    @api.constrains("weight")
    def _check_weight(self):
        for goal in self:
            if goal.weight <= 0 or goal.weight > 100:
                raise ValidationError(_("Goal weight must be greater than 0 and not more than 100."))

    @api.constrains("parent_kpi_id")
    def _check_parent_kpi(self):
        for goal in self:
            if goal.parent_kpi_id.kpi_level not in ("department", "section"):
                raise ValidationError(_("Goals must be linked to a department or section KPI."))
            if goal.parent_kpi_id.cycle_id != goal.cycle_id:
                raise ValidationError(_("The parent KPI must belong to the same cycle as the goal."))

    def action_make_available(self):
        self.write({"state": "available"})

    def action_cancel(self):
        self.write({"state": "cancelled"})
