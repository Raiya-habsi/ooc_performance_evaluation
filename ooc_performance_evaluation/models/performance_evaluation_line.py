from odoo import api, fields, models

from .performance_utils import get_param


class PerformanceEvaluationLine(models.Model):
    _name = "performance.evaluation.line"
    _description = "Performance Evaluation Line"
    _order = "evaluation_id, id"

    evaluation_id = fields.Many2one("performance.evaluation", required=True, ondelete="cascade")
    goal_id = fields.Many2one("performance.goal", required=True)
    target_value = fields.Float(required=True)
    actual_value = fields.Float()
    achievement_score = fields.Float(compute="_compute_scores", store=True)
    weight = fields.Float(required=True)
    weighted_score = fields.Float(compute="_compute_scores", store=True)
    manager_comment = fields.Text()
    evidence_attachment_ids = fields.Many2many("ir.attachment", string="Evidence")

    _sql_constraints = [
        (
            "evaluation_goal_unique",
            "unique(evaluation_id, goal_id)",
            "Each goal can only appear once per evaluation.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        normalized_vals_list = []
        existing_lines = self.browse()
        for vals in vals_list:
            evaluation_id = vals.get("evaluation_id")
            goal_id = vals.get("goal_id")
            if evaluation_id and goal_id:
                existing = self.search(
                    [("evaluation_id", "=", evaluation_id), ("goal_id", "=", goal_id)],
                    limit=1,
                )
                if existing:
                    existing.write(vals)
                    existing_lines |= existing
                    continue
            normalized_vals_list.append(vals)
        records = super().create(normalized_vals_list) if normalized_vals_list else self.browse()
        return existing_lines | records

    @api.depends("actual_value", "target_value", "weight")
    def _compute_scores(self):
        cap_enabled = get_param(self.env, "score_cap", True, bool)
        for line in self:
            if line.target_value:
                achievement = (line.actual_value / line.target_value) * 100.0
            else:
                achievement = 0.0
            if cap_enabled:
                achievement = min(achievement, 100.0)
            line.achievement_score = achievement
            line.weighted_score = (achievement * line.weight) / 100.0
