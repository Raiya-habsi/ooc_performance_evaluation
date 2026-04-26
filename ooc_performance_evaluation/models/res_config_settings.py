from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    performance_minimum_goals = fields.Integer(
        string="Minimum Goals",
        config_parameter="ooc_performance_evaluation.minimum_goals",
        default=3,
    )
    performance_maximum_goals = fields.Integer(
        string="Maximum Goals",
        config_parameter="ooc_performance_evaluation.maximum_goals",
        default=5,
    )
    performance_goal_total_weight = fields.Float(
        string="Goal Total Weight",
        config_parameter="ooc_performance_evaluation.goal_total_weight",
        default=100.0,
    )
    performance_score_cap = fields.Boolean(
        string="Cap Achievement Score at 100%",
        config_parameter="ooc_performance_evaluation.score_cap",
        default=True,
    )
    performance_appeal_working_days = fields.Integer(
        string="Appeal Working Days",
        config_parameter="ooc_performance_evaluation.appeal_working_days",
        default=10,
    )
    performance_development_plan_working_days = fields.Integer(
        string="Development Plan Working Days",
        config_parameter="ooc_performance_evaluation.development_plan_working_days",
        default=30,
    )
    performance_low_threshold = fields.Float(
        string="Low Performance Threshold",
        config_parameter="ooc_performance_evaluation.low_performance_threshold",
        default=70.0,
    )
    performance_employee_individual_weight = fields.Float(
        string="Employee Individual Goal Weight",
        config_parameter="ooc_performance_evaluation.employee_individual_weight",
        default=0.9,
    )
    performance_employee_institutional_weight = fields.Float(
        string="Employee Institutional Goal Weight",
        config_parameter="ooc_performance_evaluation.employee_institutional_weight",
        default=0.1,
    )
    performance_goal_component_weight = fields.Float(
        string="Goal Component Weight",
        config_parameter="ooc_performance_evaluation.goal_component_weight",
        default=0.6,
    )
    performance_discipline_component_weight = fields.Float(
        string="Discipline Component Weight",
        config_parameter="ooc_performance_evaluation.discipline_component_weight",
        default=0.3,
    )
    performance_events_component_weight = fields.Float(
        string="Events Component Weight",
        config_parameter="ooc_performance_evaluation.events_component_weight",
        default=0.1,
    )
    performance_manager_goal_component_weight = fields.Float(
        string="Manager Goal Component Weight",
        config_parameter="ooc_performance_evaluation.manager_goal_component_weight",
        default=0.9,
    )
    performance_manager_events_component_weight = fields.Float(
        string="Manager Events Component Weight",
        config_parameter="ooc_performance_evaluation.manager_events_component_weight",
        default=0.1,
    )

    @api.model
    def get_performance_int(self, key, default=0):
        return int(
            self.env["ir.config_parameter"].sudo().get_param(f"ooc_performance_evaluation.{key}", default)
        )
