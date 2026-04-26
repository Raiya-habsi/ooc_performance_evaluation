from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .performance_utils import get_param


class PerformanceGoalSelection(models.Model):
    _name = "performance.goal.selection"
    _description = "Performance Goal Selection"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "employee_id"
    _order = "cycle_id desc, id desc"

    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    cycle_id = fields.Many2one("performance.cycle", required=True, tracking=True)
    goal_ids = fields.Many2many("performance.goal", string="Selected Goals", tracking=True)
    manager_id = fields.Many2one("hr.employee", compute="_compute_employee_links", store=True)
    department_id = fields.Many2one("hr.department", compute="_compute_employee_links", store=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("manager_approved", "Manager Approved"),
            ("hr_approved", "HR Approved"),
            ("locked", "Locked"),
            ("returned", "Returned"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        tracking=True,
    )
    submitted_date = fields.Datetime(readonly=True)
    manager_approved_date = fields.Datetime(readonly=True)
    hr_approved_date = fields.Datetime(readonly=True)
    manager_comment = fields.Text()
    hr_comment = fields.Text()
    total_goal_count = fields.Integer(compute="_compute_totals")
    total_weight = fields.Float(compute="_compute_totals")
    related_evaluation_count = fields.Integer(compute="_compute_related_counts")

    _sql_constraints = [
        (
            "selection_employee_cycle_unique",
            "unique(employee_id, cycle_id)",
            "An employee can only have one goal selection per cycle.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_related_evaluations()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"goal_ids", "employee_id", "cycle_id"} & set(vals):
            self._sync_related_evaluations()
        return result

    @api.depends("employee_id", "employee_id.evaluation_manager_id", "employee_id.evaluation_department_id")
    def _compute_employee_links(self):
        for record in self:
            record.manager_id = record.employee_id.evaluation_manager_id
            record.department_id = record.employee_id.evaluation_department_id

    @api.depends("goal_ids", "goal_ids.weight")
    def _compute_totals(self):
        for record in self:
            record.total_goal_count = len(record.goal_ids)
            record.total_weight = sum(record.goal_ids.mapped("weight"))

    @api.depends("employee_id", "cycle_id")
    def _compute_related_counts(self):
        eval_model = self.env["performance.evaluation"]
        for record in self:
            record.related_evaluation_count = eval_model.search_count(
                [("employee_id", "=", record.employee_id.id), ("cycle_id", "=", record.cycle_id.id)]
            ) if record.employee_id and record.cycle_id else 0

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

    def action_view_selected_goals(self):
        self.ensure_one()
        return self._action_open_related(_("Selected Goals"), "performance.goal", [("id", "in", self.goal_ids.ids)])

    def action_view_related_evaluation(self):
        self.ensure_one()
        domain = [("employee_id", "=", self.employee_id.id), ("cycle_id", "=", self.cycle_id.id)]
        evaluation = self.env["performance.evaluation"].search(domain, limit=1)
        if evaluation:
            return {
                "type": "ir.actions.act_window",
                "name": _("Evaluation"),
                "res_model": "performance.evaluation",
                "res_id": evaluation.id,
                "view_mode": "form",
                "views": [[False, "form"]],
                "target": "current",
                "context": {"create": False},
            }
        return self._action_open_related(_("Related Evaluation"), "performance.evaluation", domain)

    def _check_goal_selection_validity(self):
        minimum_goals = get_param(self.env, "minimum_goals", 3, int)
        maximum_goals = get_param(self.env, "maximum_goals", 5, int)
        required_weight = get_param(self.env, "goal_total_weight", 100.0, float)
        if minimum_goals <= 0:
            minimum_goals = 3
        if maximum_goals <= 0:
            maximum_goals = 5
        if maximum_goals < minimum_goals:
            maximum_goals = minimum_goals
        if required_weight <= 0:
            required_weight = 100.0
        for record in self:
            if record.employee_id.evaluation_category != "employee":
                raise ValidationError(_("Only employees in the 'Employee' category can submit individual goals."))
            if record.cycle_id.goal_submission_deadline and fields.Date.context_today(record) > record.cycle_id.goal_submission_deadline:
                raise ValidationError(_("The goal submission deadline has passed."))
            if len(record.goal_ids) < minimum_goals or len(record.goal_ids) > maximum_goals:
                raise ValidationError(
                    _("Goal selection must contain between %s and %s goals.") % (minimum_goals, maximum_goals)
                )
            if abs(sum(record.goal_ids.mapped("weight")) - required_weight) > 0.0001:
                raise ValidationError(_("Selected goals must total %.2f%% weight.") % required_weight)
            bad_goals = record.goal_ids.filtered(
                lambda goal: not goal.parent_kpi_id
                or goal.cycle_id != record.cycle_id
                or goal.department_id != record.department_id
            )
            if bad_goals:
                raise ValidationError(_("All selected goals must be linked to a parent KPI and the employee department."))

    def _schedule_activity(self, user, summary):
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if activity_type and user:
            self.activity_schedule(activity_type_id=activity_type.id, user_id=user.id, summary=summary)

    def _sync_related_evaluations(self):
        for record in self:
            evaluation = self.env["performance.evaluation"].search(
                [("employee_id", "=", record.employee_id.id), ("cycle_id", "=", record.cycle_id.id)],
                limit=1,
            )
            if evaluation:
                evaluation.action_sync_goals_from_selection()

    def action_submit(self):
        self._check_goal_selection_validity()
        for record in self:
            record.write({"state": "submitted", "submitted_date": fields.Datetime.now()})
            record.goal_ids.filtered(lambda goal: goal.state == "available").write({"state": "selected"})
            if record.manager_id.user_id:
                record._schedule_activity(record.manager_id.user_id, _("Goal selection needs approval"))

    def action_manager_approve(self):
        for record in self:
            if self.env.user != record.manager_id.user_id and not self.env.user.has_group(
                "ooc_performance_evaluation.group_performance_hr_officer"
            ):
                raise UserError(_("Only the employee's manager or HR can approve the goal selection."))
            record.write({"state": "manager_approved", "manager_approved_date": fields.Datetime.now()})
            record.goal_ids.filtered(lambda goal: goal.state == "selected").write({"state": "manager_approved"})

    def action_return_for_correction(self):
        self.write({"state": "returned"})

    def action_reject(self):
        self.write({"state": "rejected"})

    def action_hr_approve(self):
        for record in self:
            record._check_goal_selection_validity()
            record.write({"state": "hr_approved", "hr_approved_date": fields.Datetime.now()})
            record.goal_ids.filtered(lambda goal: goal.state in ("selected", "manager_approved")).write(
                {"state": "hr_approved"}
            )
            evaluation = self.env["performance.evaluation"].search(
                [("employee_id", "=", record.employee_id.id), ("cycle_id", "=", record.cycle_id.id)], limit=1
            )
            if evaluation:
                evaluation.action_sync_goals_from_selection()

    def action_lock(self):
        self.write({"state": "locked"})
        self.mapped("goal_ids").filtered(lambda goal: goal.state == "hr_approved").write({"state": "locked"})
