from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PerformanceKpi(models.Model):
    _name = "performance.kpi"
    _description = "Performance KPI"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "cycle_id desc, id"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(tracking=True)
    cycle_id = fields.Many2one("performance.cycle", required=True, tracking=True)
    kpi_level = fields.Selection(
        [
            ("organization", "Organization"),
            ("department", "Department"),
            ("section", "Section"),
            ("employee", "Employee"),
        ],
        required=True,
        tracking=True,
    )
    parent_id = fields.Many2one("performance.kpi", string="Parent KPI")
    child_ids = fields.One2many("performance.kpi", "parent_id", string="Child KPIs")
    department_id = fields.Many2one("hr.department", tracking=True)
    section_id = fields.Many2one("hr.department", tracking=True)
    owner_employee_id = fields.Many2one("hr.employee", tracking=True)
    target_value = fields.Float(required=True, tracking=True)
    measure_unit = fields.Char()
    weight = fields.Float(required=True, tracking=True)
    description = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("locked", "Locked"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )
    score_sheet_id = fields.One2many("performance.kpi.score", "kpi_id", string="Score Sheets")
    child_count = fields.Integer(compute="_compute_related_counts")
    score_sheet_count = fields.Integer(compute="_compute_related_counts")
    goal_count = fields.Integer(compute="_compute_related_counts")

    @api.depends("child_ids", "score_sheet_id")
    def _compute_related_counts(self):
        goal_model = self.env["performance.goal"]
        for record in self:
            record.child_count = len(record.child_ids)
            record.score_sheet_count = len(record.score_sheet_id)
            record.goal_count = goal_model.search_count([("parent_kpi_id", "=", record.id)])

    def _action_open_related(self, name, model, domain):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "views": [[False, "list"], [False, "form"]],
            "target": "current",
            "domain": domain,
            "context": {"create": False},
        }

    def action_view_child_kpis(self):
        self.ensure_one()
        return self._action_open_related(_("Child KPIs"), "performance.kpi", [("parent_id", "=", self.id)])

    def action_view_score_sheets(self):
        self.ensure_one()
        return self._action_open_related(_("KPI Score Sheets"), "performance.kpi.score", [("kpi_id", "=", self.id)])

    def action_view_linked_goals(self):
        self.ensure_one()
        return self._action_open_related(_("Linked Goals"), "performance.goal", [("parent_kpi_id", "=", self.id)])

    @api.constrains("parent_id", "kpi_level")
    def _check_parent_level(self):
        valid_parent_levels = {
            "department": "organization",
            "section": "department",
            "employee": ("department", "section"),
        }
        for record in self:
            if not record.parent_id:
                continue
            expected = valid_parent_levels.get(record.kpi_level)
            if record.kpi_level == "organization":
                raise ValidationError(_("Organization KPIs cannot have a parent KPI."))
            if isinstance(expected, tuple):
                if record.parent_id.kpi_level not in expected:
                    raise ValidationError(_("Employee goals must have a department or section KPI parent."))
            elif record.parent_id.kpi_level != expected:
                raise ValidationError(
                    _("The parent KPI level for %s must be %s.") % (record.kpi_level, expected)
                )

    @api.constrains("weight")
    def _check_weight_range(self):
        for record in self:
            if record.weight <= 0 or record.weight > 100:
                raise ValidationError(_("KPI weights must be greater than 0 and not more than 100."))

    def _check_child_weights_total(self):
        precision = 0.0001
        for record in self.filtered("child_ids"):
            total_weight = sum(record.child_ids.mapped("weight"))
            if abs(total_weight - 100.0) > precision:
                raise ValidationError(
                    _("Child KPI weights under '%s' must total exactly 100%%; current total is %.2f%%.")
                    % (record.display_name, total_weight)
                )

    def action_activate(self):
        self.write({"state": "active"})

    def action_lock(self):
        self._check_child_weights_total()
        self.write({"state": "locked"})

    def action_cancel(self):
        self.write({"state": "cancelled"})
