from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .performance_utils import get_param


class PerformanceEvaluation(models.Model):
    _name = "performance.evaluation"
    _description = "Performance Evaluation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "employee_id"
    _order = "cycle_id desc, department_id, employee_id"

    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    cycle_id = fields.Many2one("performance.cycle", required=True, tracking=True)
    department_id = fields.Many2one("hr.department", required=True, tracking=True)
    section_id = fields.Many2one("hr.department", tracking=True)
    manager_id = fields.Many2one("hr.employee", required=True, tracking=True)
    evaluation_category = fields.Selection(
        [
            ("employee", "Employee"),
            ("section_head", "Section Head"),
            ("manager", "Manager"),
        ],
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many("performance.evaluation.line", "evaluation_id", string="Evaluation Lines")
    discipline_score_id = fields.Many2one("performance.discipline.score")
    individual_score = fields.Float(compute="_compute_all_scores", store=True)
    institutional_score = fields.Float(compute="_compute_all_scores", store=True)
    goal_score = fields.Float(compute="_compute_all_scores", store=True)
    discipline_score = fields.Float(compute="_compute_all_scores", store=True)
    events_score = fields.Float(compute="_compute_all_scores", store=True)
    final_score = fields.Float(compute="_compute_all_scores", store=True)
    rating = fields.Char(compute="_compute_all_scores", store=True)
    reward_currency_id = fields.Many2one(
        "res.currency",
        related="employee_id.company_id.currency_id",
        readonly=True,
        store=True,
    )
    reward_batch_id = fields.Many2one(
        "performance.reward.batch",
        related="cycle_id.reward_batch_id",
        readonly=True,
        store=True,
    )
    reward_batch_state = fields.Selection(
        related="reward_batch_id.state",
        readonly=True,
        store=True,
    )
    reward_rule_id = fields.Many2one("performance.reward.rule", compute="_compute_all_scores", store=True)
    reward_description = fields.Char(compute="_compute_all_scores", store=True)
    reward_multiplier = fields.Float(compute="_compute_all_scores", store=True)
    reward_salary_source = fields.Selection(
        [
            ("contract", "Active Contract"),
            ("manual", "Fallback Salary"),
            ("none", "No Salary Source"),
        ],
        compute="_compute_all_scores",
        store=True,
    )
    reward_salary_reference = fields.Char(compute="_compute_all_scores", store=True)
    reward_basic_salary_amount = fields.Monetary(
        currency_field="reward_currency_id",
        compute="_compute_all_scores",
        store=True,
    )
    reward_amount = fields.Monetary(
        currency_field="reward_currency_id",
        compute="_compute_all_scores",
        store=True,
    )
    reward_requires_budget_approval = fields.Boolean(compute="_compute_all_scores", store=True)
    reward_requires_board_approval = fields.Boolean(compute="_compute_all_scores", store=True)
    reward_budget_approved_by = fields.Many2one("res.users", tracking=True, copy=False)
    reward_budget_approved_date = fields.Datetime(tracking=True, copy=False)
    reward_board_approved_by = fields.Many2one("res.users", tracking=True, copy=False)
    reward_board_approved_date = fields.Datetime(tracking=True, copy=False)
    reward_rejected_by = fields.Many2one("res.users", tracking=True, copy=False)
    reward_rejected_date = fields.Datetime(tracking=True, copy=False)
    reward_rejection_reason = fields.Text(tracking=True, copy=False)
    reward_status = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("eligible", "Eligible"),
            ("pending_budget", "Pending Budget Approval"),
            ("pending_board", "Pending Board Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        compute="_compute_all_scores",
        store=True,
    )
    manager_comment = fields.Text()
    hr_comment = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting_inputs", "Waiting Inputs"),
            ("manager_evaluation", "Manager Evaluation"),
            ("manager_submitted", "Manager Submitted"),
            ("hr_review", "HR Review"),
            ("hr_confirmed", "HR Confirmed"),
            ("published", "Published"),
            ("appealed", "Appealed"),
            ("closed", "Closed"),
        ],
        default="draft",
        tracking=True,
    )
    appeal_ids = fields.One2many("performance.appeal", "evaluation_id")
    development_plan_ids = fields.One2many("performance.development.plan", "evaluation_id")
    line_count = fields.Integer(compute="_compute_related_counts")
    event_count = fields.Integer(compute="_compute_related_counts")
    appeal_count = fields.Integer(compute="_compute_related_counts")
    development_plan_count = fields.Integer(compute="_compute_related_counts")

    _sql_constraints = [
        (
            "evaluation_employee_cycle_unique",
            "unique(employee_id, cycle_id)",
            "An employee can only have one evaluation per cycle.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("employee_id"):
                employee = self.env["hr.employee"].browse(vals["employee_id"])
                vals.setdefault("department_id", employee.evaluation_department_id.id)
                vals.setdefault("section_id", employee.evaluation_section_id.id)
                vals.setdefault("manager_id", employee.evaluation_manager_id.id)
                vals.setdefault("evaluation_category", employee.evaluation_category)
        records = super().create(vals_list)
        records._ensure_discipline_score_records()
        records.action_sync_goals_from_selection()
        return records

    def write(self, vals):
        reward_snapshot = {
            record.id: (record.reward_rule_id.id, record.reward_amount)
            for record in self
        }
        result = super().write(vals)
        if {"employee_id", "cycle_id", "evaluation_category"} & set(vals):
            self._ensure_discipline_score_records()
            self.action_sync_goals_from_selection()
        if not self.env.context.get("skip_reward_reset"):
            changed_rewards = self.filtered(
                lambda record: reward_snapshot.get(record.id) != (record.reward_rule_id.id, record.reward_amount)
            )
            changed_rewards._reset_reward_approvals()
        return result

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        for evaluation in self:
            employee = evaluation.employee_id
            if not employee:
                evaluation.department_id = False
                evaluation.section_id = False
                evaluation.manager_id = False
                evaluation.evaluation_category = False
                evaluation.discipline_score_id = False
                return
            evaluation.department_id = employee.evaluation_department_id
            evaluation.section_id = employee.evaluation_section_id
            evaluation.manager_id = employee.evaluation_manager_id
            evaluation.evaluation_category = employee.evaluation_category
            if evaluation.cycle_id and evaluation.evaluation_category != "manager":
                evaluation.discipline_score_id = self.env["performance.discipline.score"].search(
                    [
                        ("employee_id", "=", employee.id),
                        ("cycle_id", "=", evaluation.cycle_id.id),
                    ],
                    limit=1,
                )

    @api.onchange("cycle_id")
    def _onchange_cycle_id(self):
        for evaluation in self:
            if evaluation.employee_id and evaluation.cycle_id and evaluation.evaluation_category != "manager":
                evaluation.discipline_score_id = self.env["performance.discipline.score"].search(
                    [
                        ("employee_id", "=", evaluation.employee_id.id),
                        ("cycle_id", "=", evaluation.cycle_id.id),
                    ],
                    limit=1,
                )
            elif evaluation.evaluation_category == "manager":
                evaluation.discipline_score_id = False

    @api.depends("line_ids", "appeal_ids", "development_plan_ids", "employee_id", "cycle_id")
    def _compute_related_counts(self):
        event_model = self.env["performance.event.participation"]
        for evaluation in self:
            evaluation.line_count = len(evaluation.line_ids)
            evaluation.appeal_count = len(evaluation.appeal_ids)
            evaluation.development_plan_count = len(evaluation.development_plan_ids)
            evaluation.event_count = event_model.search_count(
                [("employee_id", "=", evaluation.employee_id.id), ("cycle_id", "=", evaluation.cycle_id.id)]
            ) if evaluation.employee_id and evaluation.cycle_id else 0

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

    def action_view_goal_lines(self):
        self.ensure_one()
        return self._action_open_related(_("Evaluation Lines"), "performance.evaluation.line", [("evaluation_id", "=", self.id)])

    def action_view_events(self):
        self.ensure_one()
        return self._action_open_related(
            _("Events"),
            "performance.event.participation",
            [("employee_id", "=", self.employee_id.id), ("cycle_id", "=", self.cycle_id.id)],
        )

    def action_view_appeals(self):
        self.ensure_one()
        return self._action_open_related(_("Appeals"), "performance.appeal", [("evaluation_id", "=", self.id)])

    def action_view_development_plans(self):
        self.ensure_one()
        return self._action_open_related(_("Development Plans"), "performance.development.plan", [("evaluation_id", "=", self.id)])

    def action_view_discipline_record(self):
        self.ensure_one()
        if not self.discipline_score_id:
            return self._action_open_related(
                _("Discipline"),
                "performance.discipline.score",
                [("employee_id", "=", self.employee_id.id), ("cycle_id", "=", self.cycle_id.id)],
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Discipline"),
            "res_model": "performance.discipline.score",
            "res_id": self.discipline_score_id.id,
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "current",
            "context": {"create": False},
        }

    def action_view_reward_batch(self):
        self.ensure_one()
        batch = self.reward_batch_id or self.env["performance.reward.batch"].create_or_sync_for_cycle(self.cycle_id)
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

    def _ensure_discipline_score_records(self):
        discipline_model = self.env["performance.discipline.score"]
        for evaluation in self:
            if (
                not evaluation.employee_id
                or not evaluation.cycle_id
                or evaluation.evaluation_category == "manager"
            ):
                continue
            discipline = evaluation.discipline_score_id or discipline_model.search(
                [
                    ("employee_id", "=", evaluation.employee_id.id),
                    ("cycle_id", "=", evaluation.cycle_id.id),
                ],
                limit=1,
            )
            if not discipline:
                discipline = discipline_model.create(
                    {
                        "employee_id": evaluation.employee_id.id,
                        "cycle_id": evaluation.cycle_id.id,
                    }
                )
            if evaluation.discipline_score_id != discipline:
                evaluation.discipline_score_id = discipline

    def _get_institutional_score_total(self):
        self.ensure_one()
        score_model = self.env["performance.kpi.score"]
        base_domain = [
            ("cycle_id", "=", self.cycle_id.id),
            ("state", "in", ("confirmed", "locked")),
        ]
        if self.evaluation_category == "employee":
            section_scores = score_model.search(base_domain + [("owner_type", "=", "section"), ("section_id", "=", self.section_id.id)])
            if section_scores:
                return sum(section_scores.mapped("weighted_score"))
            department_scores = score_model.search(
                base_domain + [("owner_type", "=", "department"), ("department_id", "=", self.department_id.id)]
            )
            return sum(department_scores.mapped("weighted_score"))
        if self.evaluation_category == "section_head":
            section_scores = score_model.search(base_domain + [("owner_type", "=", "section"), ("section_id", "=", self.section_id.id)])
            if section_scores:
                return sum(section_scores.mapped("weighted_score"))
            department_scores = score_model.search(
                base_domain + [("owner_type", "=", "department"), ("department_id", "=", self.department_id.id)]
            )
            return sum(department_scores.mapped("weighted_score"))
        organization_scores = score_model.search(base_domain + [("owner_type", "=", "organization")])
        if organization_scores:
            return sum(organization_scores.mapped("weighted_score"))
        department_scores = score_model.search(
            base_domain + [("owner_type", "=", "department"), ("department_id", "=", self.department_id.id)]
        )
        return sum(department_scores.mapped("weighted_score"))

    def _get_events_score(self):
        self.ensure_one()
        count = self.env["performance.event.participation"].search_count(
            [("employee_id", "=", self.employee_id.id), ("cycle_id", "=", self.cycle_id.id)]
        )
        if count == 0:
            return 0.0
        if count <= 2:
            return 60.0
        if count <= 4:
            return 80.0
        return 100.0

    def _has_institutional_inputs(self):
        self.ensure_one()
        score_model = self.env["performance.kpi.score"]
        base_domain = [("cycle_id", "=", self.cycle_id.id), ("state", "in", ("confirmed", "locked"))]
        if self.evaluation_category in ("employee", "section_head") and self.section_id:
            if score_model.search_count(base_domain + [("owner_type", "=", "section"), ("section_id", "=", self.section_id.id)]):
                return True
        if self.department_id and score_model.search_count(
            base_domain + [("owner_type", "=", "department"), ("department_id", "=", self.department_id.id)]
        ):
            return True
        return bool(score_model.search_count(base_domain + [("owner_type", "=", "organization")]))

    @api.depends(
        "line_ids.weighted_score",
        "discipline_score_id.score",
        "discipline_score_id.hr_override_score",
        "evaluation_category",
        "employee_id",
        "employee_id.performance_manual_basic_salary",
        "cycle_id",
        "department_id",
        "reward_batch_state",
        "reward_budget_approved_by",
        "reward_board_approved_by",
        "reward_rejected_by",
        "section_id",
        "state",
    )
    def _compute_all_scores(self):
        reward_model = self.env["performance.reward.rule"]
        employee_individual_weight = get_param(self.env, "employee_individual_weight", 0.9, float)
        employee_institutional_weight = get_param(self.env, "employee_institutional_weight", 0.1, float)
        goal_component_weight = get_param(self.env, "goal_component_weight", 0.6, float)
        discipline_component_weight = get_param(self.env, "discipline_component_weight", 0.3, float)
        events_component_weight = get_param(self.env, "events_component_weight", 0.1, float)
        manager_goal_component_weight = get_param(self.env, "manager_goal_component_weight", 0.9, float)
        manager_events_component_weight = get_param(self.env, "manager_events_component_weight", 0.1, float)
        for evaluation in self:
            evaluation.individual_score = sum(evaluation.line_ids.mapped("weighted_score"))
            evaluation.institutional_score = evaluation._get_institutional_score_total()
            evaluation.events_score = evaluation._get_events_score()
            evaluation.discipline_score = (
                evaluation.discipline_score_id.hr_override_score
                if evaluation.discipline_score_id and evaluation.discipline_score_id.hr_override_score not in (False, None)
                else evaluation.discipline_score_id.score
            )
            if evaluation.evaluation_category == "employee":
                evaluation.goal_score = (
                    evaluation.individual_score * employee_individual_weight
                    + evaluation.institutional_score * employee_institutional_weight
                )
                evaluation.final_score = (
                    evaluation.goal_score * goal_component_weight
                    + evaluation.discipline_score * discipline_component_weight
                    + evaluation.events_score * events_component_weight
                )
            elif evaluation.evaluation_category == "section_head":
                evaluation.goal_score = evaluation.institutional_score
                evaluation.final_score = (
                    evaluation.goal_score * goal_component_weight
                    + evaluation.discipline_score * discipline_component_weight
                    + evaluation.events_score * events_component_weight
                )
            else:
                evaluation.goal_score = evaluation.institutional_score
                evaluation.final_score = (
                    evaluation.goal_score * manager_goal_component_weight
                    + evaluation.events_score * manager_events_component_weight
                )
            salary_info = evaluation.employee_id._get_reward_salary_info() if evaluation.employee_id else {
                "amount": 0.0,
                "source": "none",
                "reference": False,
            }
            evaluation.reward_salary_source = salary_info["source"]
            evaluation.reward_salary_reference = salary_info["reference"]
            evaluation.reward_basic_salary_amount = salary_info["amount"]
            reward_rule = reward_model.get_rule_for_score(evaluation.final_score)
            evaluation.reward_rule_id = reward_rule
            evaluation.rating = reward_rule.rating if reward_rule else _("Unrated")
            evaluation.reward_description = reward_rule.reward_description if reward_rule else False
            evaluation.reward_multiplier = reward_rule.get_reward_multiplier_value() if reward_rule else 0.0
            evaluation.reward_amount = evaluation.reward_basic_salary_amount * evaluation.reward_multiplier
            evaluation.reward_requires_budget_approval = bool(
                reward_rule.requires_budget_approval if reward_rule else False
            )
            evaluation.reward_requires_board_approval = bool(
                reward_rule.requires_board_approval if reward_rule else False
            )
            if not reward_rule or evaluation.reward_amount <= 0:
                evaluation.reward_status = "not_applicable"
            elif evaluation.reward_rejected_by:
                evaluation.reward_status = "rejected"
            elif evaluation.state not in ("hr_confirmed", "published", "appealed", "closed"):
                evaluation.reward_status = "eligible"
            elif evaluation.reward_batch_state in (False, "draft", "ready"):
                evaluation.reward_status = "eligible"
            elif evaluation.reward_requires_budget_approval and not evaluation.reward_budget_approved_by:
                evaluation.reward_status = "pending_budget"
            elif evaluation.reward_requires_board_approval and not evaluation.reward_board_approved_by:
                evaluation.reward_status = "pending_board"
            else:
                evaluation.reward_status = "approved"

    def _reset_reward_approvals(self):
        if not self:
            return
        self.with_context(skip_reward_reset=True).write(
            {
                "reward_budget_approved_by": False,
                "reward_budget_approved_date": False,
                "reward_board_approved_by": False,
                "reward_board_approved_date": False,
                "reward_rejected_by": False,
                "reward_rejected_date": False,
                "reward_rejection_reason": False,
            }
        )

    def action_approve_reward_budget(self):
        for evaluation in self:
            if not evaluation.reward_rule_id or evaluation.reward_amount <= 0:
                raise UserError(_("This evaluation has no payable reward to approve."))
            evaluation.with_context(skip_reward_reset=True).write(
                {
                    "reward_budget_approved_by": self.env.user.id,
                    "reward_budget_approved_date": fields.Datetime.now(),
                    "reward_rejected_by": False,
                    "reward_rejected_date": False,
                }
            )

    def action_approve_reward_board(self):
        for evaluation in self:
            if not evaluation.reward_rule_id or evaluation.reward_amount <= 0:
                raise UserError(_("This evaluation has no payable reward to approve."))
            if evaluation.reward_requires_budget_approval and not evaluation.reward_budget_approved_by:
                raise UserError(_("Budget approval is required before board approval."))
            evaluation.with_context(skip_reward_reset=True).write(
                {
                    "reward_board_approved_by": self.env.user.id,
                    "reward_board_approved_date": fields.Datetime.now(),
                    "reward_rejected_by": False,
                    "reward_rejected_date": False,
                }
            )

    def action_reject_reward(self):
        for evaluation in self:
            if not evaluation.reward_rejection_reason:
                raise ValidationError(_("Provide a rejection reason before rejecting the reward."))
            evaluation.with_context(skip_reward_reset=True).write(
                {
                    "reward_rejected_by": self.env.user.id,
                    "reward_rejected_date": fields.Datetime.now(),
                    "reward_budget_approved_by": False,
                    "reward_budget_approved_date": False,
                    "reward_board_approved_by": False,
                    "reward_board_approved_date": False,
                }
            )

    def action_reset_reward_approval(self):
        self._reset_reward_approvals()

    def action_sync_goals_from_selection(self):
        line_model = self.env["performance.evaluation.line"]
        for evaluation in self:
            if evaluation.evaluation_category != "employee":
                if evaluation.line_ids:
                    evaluation.line_ids.unlink()
                continue
            selection = self.env["performance.goal.selection"].search(
                [("employee_id", "=", evaluation.employee_id.id), ("cycle_id", "=", evaluation.cycle_id.id)], limit=1
            )
            selected_goals = selection.goal_ids
            existing_by_goal = {line.goal_id.id: line for line in evaluation.line_ids}
            keep_goal_ids = set(selected_goals.ids)
            for line in evaluation.line_ids.filtered(lambda l: l.goal_id.id not in keep_goal_ids):
                line.unlink()
            for goal in selected_goals:
                if goal.id in existing_by_goal:
                    existing_by_goal[goal.id].write({"target_value": goal.target_value, "weight": goal.weight})
                else:
                    line_model.create(
                        {
                            "evaluation_id": evaluation.id,
                            "goal_id": goal.id,
                            "target_value": goal.target_value,
                            "weight": goal.weight,
                        }
                    )

    def action_start_manager_evaluation(self):
        self._ensure_discipline_score_records()
        self.write({"state": "manager_evaluation"})

    def _validate_manager_submission(self):
        self._ensure_discipline_score_records()
        for evaluation in self:
            if not evaluation.manager_id:
                raise ValidationError(_("Evaluation manager is required."))
            if not evaluation.department_id:
                raise ValidationError(_("Evaluation department is required."))
            if evaluation.evaluation_category == "employee":
                if not evaluation.line_ids:
                    raise ValidationError(_("Employee evaluations require approved goals."))
                if any(line.actual_value in (False, None) for line in evaluation.line_ids):
                    raise ValidationError(_("All evaluation lines must have actual values before submission."))
            if evaluation.evaluation_category != "manager" and not evaluation.discipline_score_id:
                raise ValidationError(_("A discipline score record is required for this evaluation."))
            if not evaluation._has_institutional_inputs():
                raise ValidationError(_("A confirmed institutional KPI score is required before submission."))

    def action_submit_manager(self):
        self._validate_manager_submission()
        self.write({"state": "manager_submitted"})

    def action_send_to_hr(self):
        self._ensure_discipline_score_records()
        self.write({"state": "hr_review"})

    def action_hr_confirm(self):
        self._ensure_discipline_score_records()
        for evaluation in self:
            evaluation._validate_for_hr_confirmation()
        self.write({"state": "hr_confirmed"})

    def _validate_for_hr_confirmation(self):
        self.ensure_one()
        self._ensure_discipline_score_records()
        if not self.manager_id or not self.department_id or not self.evaluation_category:
            raise ValidationError(_("Manager, department, and evaluation category are mandatory."))
        if self.evaluation_category != "manager" and not self.discipline_score_id:
            raise ValidationError(_("Discipline data is missing for %s.") % self.employee_id.name)
        if self.events_score in (False, None):
            raise ValidationError(_("Event data is missing for %s.") % self.employee_id.name)
        if self.evaluation_category == "employee":
            selection = self.env["performance.goal.selection"].search(
                [("employee_id", "=", self.employee_id.id), ("cycle_id", "=", self.cycle_id.id)], limit=1
            )
            if not selection or selection.state not in ("hr_approved", "locked"):
                raise ValidationError(_("Goals are not HR approved for %s.") % self.employee_id.name)
            if abs(sum(self.line_ids.mapped("weight")) - get_param(self.env, "goal_total_weight", 100.0, float)) > 0.0001:
                raise ValidationError(_("Goal weights must total 100%% for %s.") % self.employee_id.name)
        if self.state not in ("manager_submitted", "hr_review", "hr_confirmed", "published"):
            raise ValidationError(_("Manager evaluation is missing for %s.") % self.employee_id.name)
        if self.final_score < 0:
            raise ValidationError(_("Final score cannot be negative."))

    def action_publish(self):
        self.write({"state": "published"})
        self._create_development_plans_if_needed()

    def _create_development_plans_if_needed(self):
        threshold = get_param(self.env, "low_performance_threshold", 70.0, float)
        plan_model = self.env["performance.development.plan"]
        deadline_days = self.env["res.config.settings"].get_performance_int("development_plan_working_days", 30)
        for evaluation in self:
            needs_plan = evaluation.rating in ("Acceptable", "Weak") or evaluation.final_score < threshold
            if not needs_plan or evaluation.development_plan_ids:
                continue
            plan_model.create(
                {
                    "employee_id": evaluation.employee_id.id,
                    "evaluation_id": evaluation.id,
                    "cycle_id": evaluation.cycle_id.id,
                    "manager_id": evaluation.manager_id.id,
                }
            )._set_default_deadline(deadline_days)
