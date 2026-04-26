from odoo import api, fields, models


class PerformanceRewardRule(models.Model):
    _name = "performance.reward.rule"
    _description = "Performance Reward Rule"
    _order = "min_score desc"

    min_score = fields.Float(required=True)
    max_score = fields.Float(required=True)
    rating = fields.Char(required=True)
    reward_description = fields.Char(required=True)
    reward_multiplier = fields.Float(
        default=0.0,
        help="Number of basic salaries granted by this reward rule.",
    )
    requires_budget_approval = fields.Boolean()
    requires_board_approval = fields.Boolean()
    active = fields.Boolean(default=True)

    def get_reward_multiplier_value(self):
        self.ensure_one()
        if self.reward_multiplier:
            return self.reward_multiplier
        description_map = {
            "Two basic salaries": 2.0,
            "One basic salary": 1.0,
            "Half salary": 0.5,
            "Quarter salary": 0.25,
            "No reward": 0.0,
        }
        return description_map.get(self.reward_description or "", 0.0)

    @api.model
    def get_rule_for_score(self, score):
        return self.search(
            [("active", "=", True), ("min_score", "<=", score), ("max_score", ">=", score)],
            limit=1,
        )
