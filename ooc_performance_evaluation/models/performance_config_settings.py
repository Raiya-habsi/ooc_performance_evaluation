from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PerformanceConfigSettings(models.Model):
    _name = "performance.config.settings"
    _description = "Performance Configuration"

    name = fields.Char(default="Performance Evaluation Settings", required=True)
    minimum_goals = fields.Integer(default=3, required=True)
    maximum_goals = fields.Integer(default=5, required=True)
    goal_total_weight = fields.Float(default=100.0, required=True)
    score_cap = fields.Boolean(default=True)
    appeal_working_days = fields.Integer(default=10, required=True)
    development_plan_working_days = fields.Integer(default=30, required=True)
    low_performance_threshold = fields.Float(default=70.0, required=True)
    employee_individual_weight = fields.Float(default=0.9, required=True)
    employee_institutional_weight = fields.Float(default=0.1, required=True)
    goal_component_weight = fields.Float(default=0.6, required=True)
    discipline_component_weight = fields.Float(default=0.3, required=True)
    events_component_weight = fields.Float(default=0.1, required=True)
    manager_goal_component_weight = fields.Float(default=0.9, required=True)
    manager_events_component_weight = fields.Float(default=0.1, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_parameters()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._sync_to_parameters()
        return result

    def _sync_to_parameters(self):
        param_model = self.env["ir.config_parameter"].sudo()
        for record in self:
            param_model.set_param("ooc_performance_evaluation.minimum_goals", record.minimum_goals)
            param_model.set_param("ooc_performance_evaluation.maximum_goals", record.maximum_goals)
            param_model.set_param("ooc_performance_evaluation.goal_total_weight", record.goal_total_weight)
            param_model.set_param("ooc_performance_evaluation.score_cap", record.score_cap)
            param_model.set_param("ooc_performance_evaluation.appeal_working_days", record.appeal_working_days)
            param_model.set_param(
                "ooc_performance_evaluation.development_plan_working_days",
                record.development_plan_working_days,
            )
            param_model.set_param(
                "ooc_performance_evaluation.low_performance_threshold",
                record.low_performance_threshold,
            )
            param_model.set_param(
                "ooc_performance_evaluation.employee_individual_weight",
                record.employee_individual_weight,
            )
            param_model.set_param(
                "ooc_performance_evaluation.employee_institutional_weight",
                record.employee_institutional_weight,
            )
            param_model.set_param("ooc_performance_evaluation.goal_component_weight", record.goal_component_weight)
            param_model.set_param(
                "ooc_performance_evaluation.discipline_component_weight",
                record.discipline_component_weight,
            )
            param_model.set_param(
                "ooc_performance_evaluation.events_component_weight",
                record.events_component_weight,
            )
            param_model.set_param(
                "ooc_performance_evaluation.manager_goal_component_weight",
                record.manager_goal_component_weight,
            )
            param_model.set_param(
                "ooc_performance_evaluation.manager_events_component_weight",
                record.manager_events_component_weight,
            )

    @api.constrains("minimum_goals", "maximum_goals", "goal_total_weight")
    def _check_goal_limits(self):
        for record in self:
            if record.minimum_goals <= 0:
                raise ValidationError("Minimum goals must be greater than 0.")
            if record.maximum_goals < record.minimum_goals:
                raise ValidationError("Maximum goals must be greater than or equal to minimum goals.")
            if record.goal_total_weight <= 0:
                raise ValidationError("Goal total weight must be greater than 0.")
