from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PerformanceRewardBatch(models.Model):
    _name = "performance.reward.batch"
    _description = "Performance Reward Batch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "cycle_id desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    cycle_id = fields.Many2one("performance.cycle", required=True, tracking=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    evaluation_ids = fields.Many2many(
        "performance.evaluation",
        compute="_compute_evaluations",
        string="Reward Evaluations",
    )
    evaluation_count = fields.Integer(compute="_compute_metrics")
    total_reward_amount = fields.Monetary(
        compute="_compute_metrics",
        currency_field="currency_id",
    )
    pending_budget_count = fields.Integer(compute="_compute_metrics")
    pending_board_count = fields.Integer(compute="_compute_metrics")
    approved_count = fields.Integer(compute="_compute_metrics")
    rejected_count = fields.Integer(compute="_compute_metrics")
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("ready", "Ready"),
            ("budget_review", "Budget Review"),
            ("board_review", "Board Review"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("closed", "Closed"),
        ],
        default="draft",
        tracking=True,
    )
    rejection_reason = fields.Text(tracking=True)

    _sql_constraints = [
        ("cycle_unique_reward_batch", "unique(cycle_id)", "Only one reward batch can exist per cycle."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        batches = super().create(vals_list)
        for batch in batches:
            if batch.cycle_id and batch.cycle_id.reward_batch_id != batch:
                batch.cycle_id.sudo().write({"reward_batch_id": batch.id})
        return batches

    @api.depends("cycle_id.name", "cycle_id.year")
    def _compute_name(self):
        for batch in self:
            if batch.cycle_id:
                batch.name = _("Reward Batch - %s") % batch.cycle_id.name
            else:
                batch.name = _("Reward Batch")

    @api.depends("cycle_id")
    def _compute_evaluations(self):
        for batch in self:
            if not batch.cycle_id:
                batch.evaluation_ids = False
                continue
            batch.evaluation_ids = batch._get_reward_evaluations()

    @api.depends("cycle_id")
    def _compute_metrics(self):
        for batch in self:
            evaluations = batch._get_reward_evaluations() if batch.cycle_id else self.env["performance.evaluation"]
            batch.evaluation_count = len(evaluations)
            batch.total_reward_amount = sum(evaluations.mapped("reward_amount"))
            batch.pending_budget_count = len(evaluations.filtered(lambda evaluation: evaluation.reward_status == "pending_budget"))
            batch.pending_board_count = len(evaluations.filtered(lambda evaluation: evaluation.reward_status == "pending_board"))
            batch.approved_count = len(evaluations.filtered(lambda evaluation: evaluation.reward_status == "approved"))
            batch.rejected_count = len(evaluations.filtered(lambda evaluation: evaluation.reward_status == "rejected"))

    def _get_reward_evaluations(self):
        self.ensure_one()
        return self.env["performance.evaluation"].search(
            [
                ("cycle_id", "=", self.cycle_id.id),
                ("reward_amount", ">", 0),
                ("state", "in", ("hr_confirmed", "published", "appealed", "closed")),
            ],
            order="department_id, employee_id",
        )

    @api.model
    def create_or_sync_for_cycle(self, cycle):
        cycle = cycle if cycle._name == "performance.cycle" else self.env["performance.cycle"].browse(cycle)
        batch = self.search([("cycle_id", "=", cycle.id)], limit=1)
        if not batch:
            batch = self.create({"cycle_id": cycle.id})
        elif cycle.reward_batch_id != batch:
            cycle.sudo().write({"reward_batch_id": batch.id})
        batch.action_prepare()
        return batch

    @api.model
    def _sync_cycle_links(self):
        for batch in self.search([]):
            if batch.cycle_id and batch.cycle_id.reward_batch_id != batch:
                batch.cycle_id.sudo().write({"reward_batch_id": batch.id})
            batch.action_prepare()
        return True

    def action_prepare(self):
        for batch in self:
            if not batch.cycle_id:
                continue
            if not batch.evaluation_ids:
                batch.state = "draft"
                continue
            if batch.rejected_count and batch.rejected_count == batch.evaluation_count:
                batch.state = "rejected"
            elif batch.approved_count and batch.approved_count == batch.evaluation_count:
                batch.state = "approved"
            elif batch.pending_board_count:
                batch.state = "board_review"
            elif batch.pending_budget_count:
                batch.state = "budget_review"
            else:
                batch.state = "ready"
        return True

    def action_submit_budget(self):
        for batch in self:
            if not batch.evaluation_ids:
                raise UserError(_("There are no staff rewards to submit in this cycle."))
            if any(batch.evaluation_ids.mapped("reward_requires_budget_approval")):
                batch.state = "budget_review"
            elif any(batch.evaluation_ids.mapped("reward_requires_board_approval")):
                batch.state = "board_review"
            else:
                batch.state = "approved"

    def action_approve_budget(self):
        for batch in self:
            pending = batch.evaluation_ids.filtered(
                lambda evaluation: evaluation.reward_status in ("eligible", "pending_budget")
            )
            if not pending:
                raise UserError(_("There are no reward records waiting for budget approval."))
            pending.action_approve_reward_budget()
            if batch.evaluation_ids.filtered(lambda evaluation: evaluation.reward_status == "pending_board"):
                batch.state = "board_review"
            else:
                batch.state = "approved"

    def action_approve_board(self):
        for batch in self:
            pending = batch.evaluation_ids.filtered(lambda evaluation: evaluation.reward_status == "pending_board")
            if not pending:
                raise UserError(_("There are no reward records waiting for board approval."))
            pending.action_approve_reward_board()
            batch.state = "approved"

    def action_reject_batch(self):
        for batch in self:
            if not batch.rejection_reason:
                raise ValidationError(_("Provide a rejection reason before rejecting the batch."))
            evaluations = batch.evaluation_ids.filtered(
                lambda evaluation: evaluation.reward_status in ("eligible", "pending_budget", "pending_board", "approved")
            )
            if not evaluations:
                raise UserError(_("There are no reward records available to reject in this batch."))
            evaluations.write({"reward_rejection_reason": batch.rejection_reason})
            evaluations.action_reject_reward()
            batch.state = "rejected"

    def action_reset_batch(self):
        for batch in self:
            if batch.evaluation_ids:
                batch.evaluation_ids.action_reset_reward_approval()
            batch.rejection_reason = False
            batch.state = "ready" if batch.evaluation_ids else "draft"

    def action_close_batch(self):
        self.write({"state": "closed"})

    def action_view_evaluations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Staff Rewards"),
            "res_model": "performance.evaluation",
            "view_mode": "list,pivot,graph,form",
            "views": [[False, "list"], [False, "pivot"], [False, "graph"], [False, "form"]],
            "target": "current",
            "domain": [("id", "in", self.evaluation_ids.ids)],
            "context": {
                "search_default_group_reward_status": 1,
                "create": False,
            },
        }
