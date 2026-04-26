from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .performance_utils import add_working_days


class PerformanceCycle(models.Model):
    _name = "performance.cycle"
    _description = "Performance Evaluation Cycle"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "year desc, id desc"

    name = fields.Char(required=True, tracking=True)
    year = fields.Integer(required=True, tracking=True)
    start_date = fields.Date(required=True, tracking=True)
    goal_setting_start_date = fields.Date(tracking=True)
    goal_submission_deadline = fields.Date(tracking=True)
    manager_approval_deadline = fields.Date(tracking=True)
    hr_approval_deadline = fields.Date(tracking=True)
    goals_lock_date = fields.Date(tracking=True)
    mid_year_review_start = fields.Date(tracking=True)
    mid_year_review_end = fields.Date(tracking=True)
    final_evaluation_start = fields.Date(tracking=True)
    final_evaluation_end = fields.Date(tracking=True)
    result_publish_date = fields.Date(tracking=True)
    appeal_deadline = fields.Date(tracking=True)
    development_plan_deadline = fields.Date(tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("goal_setting", "Goal Setting"),
            ("manager_approval", "Manager Approval"),
            ("hr_approval", "HR Approval"),
            ("goals_locked", "Goals Locked"),
            ("mid_year_review", "Mid-Year Review"),
            ("final_evaluation", "Final Evaluation"),
            ("hr_confirmation", "HR Confirmation"),
            ("published", "Published"),
            ("appeal_period", "Appeal Period"),
            ("closed", "Closed"),
        ],
        default="draft",
        tracking=True,
    )
    evaluation_ids = fields.One2many("performance.evaluation", "cycle_id")
    kpi_ids = fields.One2many("performance.kpi", "cycle_id")
    goal_ids = fields.One2many("performance.goal", "cycle_id")
    eligible_employee_count = fields.Integer(compute="_compute_employee_counts")
    excluded_employee_count = fields.Integer(compute="_compute_employee_counts")
    evaluation_count = fields.Integer(compute="_compute_cycle_metrics")
    completed_evaluation_count = fields.Integer(compute="_compute_cycle_metrics")
    published_evaluation_count = fields.Integer(compute="_compute_cycle_metrics")
    appeal_count = fields.Integer(compute="_compute_cycle_metrics")
    average_final_score = fields.Float(compute="_compute_cycle_metrics")
    completion_rate = fields.Float(compute="_compute_cycle_metrics")
    kpi_count = fields.Integer(compute="_compute_related_counts")
    score_sheet_count = fields.Integer(compute="_compute_related_counts")
    goal_count = fields.Integer(compute="_compute_related_counts")
    development_plan_count = fields.Integer(compute="_compute_related_counts")
    midyear_review_count = fields.Integer(compute="_compute_related_counts")
    reward_count = fields.Integer(compute="_compute_related_counts")
    reward_batch_id = fields.Many2one("performance.reward.batch", readonly=True, copy=False)

    _sql_constraints = [
        ("cycle_year_unique", "unique(year)", "A performance cycle already exists for this year."),
    ]

    @api.depends("evaluation_ids", "year")
    def _compute_employee_counts(self):
        employee_model = self.env["hr.employee"]
        for cycle in self:
            employees = employee_model.search([])
            cycle.eligible_employee_count = len(employees.filtered("is_evaluation_eligible"))
            cycle.excluded_employee_count = len(employees.filtered(lambda emp: not emp.is_evaluation_eligible))

    @api.depends("evaluation_ids.state", "evaluation_ids.final_score", "evaluation_ids.appeal_ids.state")
    def _compute_cycle_metrics(self):
        for cycle in self:
            evaluations = cycle.evaluation_ids
            completed_states = {"manager_submitted", "hr_review", "hr_confirmed", "published", "appealed", "closed"}
            cycle.evaluation_count = len(evaluations)
            cycle.completed_evaluation_count = len(evaluations.filtered(lambda rec: rec.state in completed_states))
            cycle.published_evaluation_count = len(
                evaluations.filtered(lambda rec: rec.state in {"published", "appealed", "closed"})
            )
            cycle.appeal_count = len(evaluations.mapped("appeal_ids"))
            cycle.average_final_score = sum(evaluations.mapped("final_score")) / len(evaluations) if evaluations else 0.0
            cycle.completion_rate = (
                (cycle.completed_evaluation_count / cycle.evaluation_count) * 100.0 if cycle.evaluation_count else 0.0
            )

    @api.depends(
        "kpi_ids",
        "goal_ids",
        "evaluation_ids.development_plan_ids",
        "evaluation_ids.appeal_ids",
        "evaluation_ids.reward_amount",
        "reward_batch_id.evaluation_count",
    )
    def _compute_related_counts(self):
        score_model = self.env["performance.kpi.score"]
        review_model = self.env["performance.midyear.review"]
        for cycle in self:
            cycle.kpi_count = len(cycle.kpi_ids)
            cycle.score_sheet_count = score_model.search_count([("cycle_id", "=", cycle.id)])
            cycle.goal_count = len(cycle.goal_ids)
            cycle.development_plan_count = len(cycle.evaluation_ids.mapped("development_plan_ids"))
            cycle.midyear_review_count = review_model.search_count([("cycle_id", "=", cycle.id)])
            batch = cycle.reward_batch_id or self.env["performance.reward.batch"].search([("cycle_id", "=", cycle.id)], limit=1)
            cycle.reward_count = batch.evaluation_count if batch else len(
                cycle.evaluation_ids.filtered(
                    lambda evaluation: evaluation.reward_amount > 0
                    and evaluation.state in {"hr_confirmed", "published", "appealed", "closed"}
                )
            )

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

    def action_view_evaluations(self):
        self.ensure_one()
        return self._action_open_related(_("Evaluations"), "performance.evaluation", [("cycle_id", "=", self.id)])

    def action_view_kpis(self):
        self.ensure_one()
        return self._action_open_related(_("KPIs"), "performance.kpi", [("cycle_id", "=", self.id)])

    def action_view_score_sheets(self):
        self.ensure_one()
        return self._action_open_related(_("KPI Score Sheets"), "performance.kpi.score", [("cycle_id", "=", self.id)])

    def action_view_goals(self):
        self.ensure_one()
        return self._action_open_related(_("Goals"), "performance.goal", [("cycle_id", "=", self.id)])

    def action_view_appeals(self):
        self.ensure_one()
        return self._action_open_related(_("Appeals"), "performance.appeal", [("cycle_id", "=", self.id)])

    def action_view_development_plans(self):
        self.ensure_one()
        return self._action_open_related(_("Development Plans"), "performance.development.plan", [("cycle_id", "=", self.id)])

    def action_view_midyear_reviews(self):
        self.ensure_one()
        return self._action_open_related(_("Mid-Year Reviews"), "performance.midyear.review", [("cycle_id", "=", self.id)])

    def action_view_rewards(self):
        self.ensure_one()
        batch = self.env["performance.reward.batch"].create_or_sync_for_cycle(self)
        return {
            "type": "ir.actions.act_window",
            "name": _("Reward Batch"),
            "res_model": "performance.reward.batch",
            "res_id": batch.id,
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "current",
            "context": {"create": False},
        }

    @api.constrains("start_date", "result_publish_date")
    def _check_dates(self):
        for cycle in self:
            if cycle.result_publish_date and cycle.start_date and cycle.result_publish_date < cycle.start_date:
                raise ValidationError(_("The result publish date cannot be earlier than the cycle start date."))

    def _set_state(self, state):
        self.write({"state": state})

    def action_start_goal_setting(self):
        self._set_state("goal_setting")

    def action_start_manager_approval(self):
        self._set_state("manager_approval")

    def action_start_hr_approval(self):
        self._set_state("hr_approval")

    def action_lock_goals(self):
        for cycle in self:
            bad_selections = cycle.env["performance.goal.selection"].search(
                [("cycle_id", "=", cycle.id), ("state", "not in", ("hr_approved", "locked"))]
            )
            if bad_selections:
                raise UserError(_("All goal selections must be HR approved before goals can be locked."))
            bad_kpis = cycle.kpi_ids.filtered(lambda kpi: kpi.state != "locked" and kpi.child_ids)
            if bad_kpis:
                bad_kpis._check_child_weights_total()
            cycle.goal_ids.filtered(lambda goal: goal.state == "available").write({"state": "locked"})
            cycle.state = "goals_locked"

    def action_open_mid_year_review(self):
        self._set_state("mid_year_review")

    def action_start_final_evaluation(self):
        self._set_state("final_evaluation")

    def action_open_appeal_period(self):
        for cycle in self:
            if not cycle.result_publish_date:
                cycle.result_publish_date = fields.Date.context_today(cycle)
            if not cycle.appeal_deadline:
                days = self.env["res.config.settings"].get_performance_int("appeal_working_days", 10)
                cycle.appeal_deadline = add_working_days(cycle.result_publish_date, days)
            cycle.state = "appeal_period"

    def action_close_cycle(self):
        self._set_state("closed")

    def action_generate_evaluations(self):
        evaluation_model = self.env["performance.evaluation"]
        discipline_model = self.env["performance.discipline.score"]
        selection_model = self.env["performance.goal.selection"]
        for cycle in self:
            employees = self.env["hr.employee"].search([("active", "=", True)])
            for employee in employees.filtered("is_evaluation_eligible"):
                if not employee.evaluation_department_id:
                    continue
                vals = {
                    "employee_id": employee.id,
                    "cycle_id": cycle.id,
                    "department_id": employee.evaluation_department_id.id,
                    "section_id": employee.evaluation_section_id.id,
                    "manager_id": employee.evaluation_manager_id.id,
                    "evaluation_category": employee.evaluation_category,
                    "state": "waiting_inputs",
                }
                evaluation = evaluation_model.search(
                    [("employee_id", "=", employee.id), ("cycle_id", "=", cycle.id)], limit=1
                )
                if evaluation:
                    evaluation.write(vals)
                else:
                    evaluation = evaluation_model.create(vals)
                if employee.evaluation_category != "manager":
                    discipline = discipline_model.search(
                        [("employee_id", "=", employee.id), ("cycle_id", "=", cycle.id)], limit=1
                    )
                    if not discipline:
                        discipline = discipline_model.create({"employee_id": employee.id, "cycle_id": cycle.id})
                    evaluation.discipline_score_id = discipline
                if employee.evaluation_category == "employee":
                    selection = selection_model.search(
                        [("employee_id", "=", employee.id), ("cycle_id", "=", cycle.id)], limit=1
                    )
                    if not selection:
                        selection_model.create({"employee_id": employee.id, "cycle_id": cycle.id})
                    evaluation.action_sync_goals_from_selection()
            cycle.message_post(body=_("Evaluation records were generated for eligible employees."))

    def action_confirm_evaluations(self):
        for cycle in self:
            cycle._validate_before_confirmation()
            cycle.env["performance.kpi.score"].search(
                [("cycle_id", "=", cycle.id), ("state", "=", "confirmed")]
            ).write({"state": "locked"})
            cycle.env["performance.discipline.score"].search(
                [("cycle_id", "=", cycle.id), ("state", "=", "confirmed")]
            ).write({"state": "locked"})
            cycle.evaluation_ids._compute_all_scores()
            cycle.evaluation_ids.write({"state": "hr_confirmed"})
            self.env["performance.reward.batch"].create_or_sync_for_cycle(cycle)
            cycle.state = "hr_confirmation"

    def _validate_before_confirmation(self):
        self.ensure_one()
        missing_kpi_scores = self.env["performance.kpi"].search(
            [
                ("cycle_id", "=", self.id),
                ("kpi_level", "in", ("organization", "department", "section")),
                ("state", "=", "locked"),
                ("score_sheet_id", "=", False),
            ]
        )
        if missing_kpi_scores:
            raise UserError(_("Some locked institutional KPIs do not have a score sheet."))
        for evaluation in self.evaluation_ids:
            evaluation._validate_for_hr_confirmation()

    def action_publish_results(self):
        for cycle in self:
            if cycle.state != "hr_confirmation":
                raise UserError(_("The cycle must be in HR Confirmation before results can be published."))
            cycle.evaluation_ids._compute_all_scores()
            cycle.evaluation_ids.write({"state": "published"})
            cycle.evaluation_ids._create_development_plans_if_needed()
            self.env["performance.reward.batch"].create_or_sync_for_cycle(cycle)
            cycle.state = "published"
            cycle.result_publish_date = cycle.result_publish_date or fields.Date.context_today(cycle)
            cycle.message_post(body=_("Performance evaluation results have been published."))

    @api.model
    def cron_auto_update_cycle_state(self):
        today = fields.Date.context_today(self)
        cycles = self.search([("state", "!=", "closed")])
        for cycle in cycles:
            if cycle.goal_setting_start_date and today >= cycle.goal_setting_start_date and cycle.state == "draft":
                cycle.state = "goal_setting"
            if (
                cycle.manager_approval_deadline
                and cycle.goal_submission_deadline
                and today > cycle.goal_submission_deadline
                and cycle.state == "goal_setting"
            ):
                cycle.state = "manager_approval"
            if (
                cycle.hr_approval_deadline
                and cycle.manager_approval_deadline
                and today > cycle.manager_approval_deadline
                and cycle.state == "manager_approval"
            ):
                cycle.state = "hr_approval"
            if cycle.goals_lock_date and today >= cycle.goals_lock_date and cycle.state == "hr_approval":
                cycle.state = "goals_locked"
            if cycle.mid_year_review_start and today >= cycle.mid_year_review_start and cycle.state == "goals_locked":
                cycle.state = "mid_year_review"
            if cycle.final_evaluation_start and today >= cycle.final_evaluation_start and cycle.state in ("mid_year_review", "goals_locked"):
                cycle.state = "final_evaluation"
            if cycle.result_publish_date and today >= cycle.result_publish_date and cycle.state == "hr_confirmation":
                cycle.state = "published"
            if cycle.appeal_deadline and today > cycle.appeal_deadline and cycle.state == "appeal_period":
                cycle.state = "closed"

    @api.model
    def cron_send_cycle_deadline_reminders(self):
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        hr_group = self.env.ref("ooc_performance_evaluation.group_performance_hr_manager", raise_if_not_found=False)
        if not activity_type or not hr_group:
            return
        today = fields.Date.context_today(self)
        for cycle in self.search([("state", "!=", "closed")]):
            reminders = [
                (cycle.goal_submission_deadline, "Goal submission deadline"),
                (cycle.manager_approval_deadline, "Manager approval deadline"),
                (cycle.hr_approval_deadline, "HR approval deadline"),
                (cycle.final_evaluation_end, "Final evaluation deadline"),
                (cycle.appeal_deadline, "Appeal deadline"),
                (cycle.development_plan_deadline, "Development plan deadline"),
            ]
            for reminder_date, label in reminders:
                if reminder_date and reminder_date == today:
                    for user in hr_group.users:
                        cycle.activity_schedule(
                            activity_type_id=activity_type.id,
                            user_id=user.id,
                            summary=f"{label} today for {cycle.name}",
                        )
