from datetime import date

from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    evaluation_category = fields.Selection(
        [
            ("employee", "Employee"),
            ("section_head", "Section Head"),
            ("manager", "Manager"),
        ],
        default="employee",
        tracking=True,
    )
    evaluation_section_id = fields.Many2one(
        "hr.department",
        string="Evaluation Section",
        tracking=True,
    )
    evaluation_service_start_date = fields.Date(
        string="Evaluation Service Start Date",
        tracking=True,
        help="Used to determine whether the employee has completed the minimum service period for annual evaluations.",
    )
    performance_manual_basic_salary = fields.Monetary(
        string="Fallback Basic Salary",
        currency_field="company_currency_id",
        tracking=True,
        help="Used for reward calculations when no active HR contract is available.",
    )
    evaluation_manager_id = fields.Many2one(
        "hr.employee",
        string="Evaluation Manager",
        compute="_compute_evaluation_manager",
        store=True,
    )
    evaluation_department_id = fields.Many2one(
        "hr.department",
        string="Evaluation Department",
        compute="_compute_evaluation_department",
        store=True,
    )
    is_evaluation_eligible = fields.Boolean(
        compute="_compute_evaluation_eligibility",
        store=True,
    )
    evaluation_exclusion_reason = fields.Char(
        compute="_compute_evaluation_eligibility",
        store=True,
        readonly=False,
    )

    @api.depends("parent_id")
    def _compute_evaluation_manager(self):
        for employee in self:
            employee.evaluation_manager_id = employee.parent_id

    @api.depends("department_id")
    def _compute_evaluation_department(self):
        for employee in self:
            employee.evaluation_department_id = employee.department_id

    def _get_service_start_date(self):
        self.ensure_one()
        if self.evaluation_service_start_date:
            return self.evaluation_service_start_date
        if "first_contract_date" in self._fields and self.first_contract_date:
            return self.first_contract_date
        if "hire_date" in self._fields and self.hire_date:
            return self.hire_date
        return fields.Date.to_date(self.create_date) if self.create_date else date.today()

    def _get_reward_salary_info(self):
        self.ensure_one()
        if "hr.contract" in self.env:
            contract_model = self.env["hr.contract"]
            contract_fields = contract_model._fields
            domain = [("employee_id", "=", self.id)]
            if "state" in contract_fields:
                domain.append(("state", "not in", ["cancel"]))
            today = fields.Date.context_today(self)
            if "date_start" in contract_fields:
                domain.append(("date_start", "<=", today))
            if "date_end" in contract_fields:
                domain.extend(["|", ("date_end", "=", False), ("date_end", ">=", today)])
            contract = contract_model.search(domain, order="date_start desc, id desc", limit=1)
            if contract and "wage" in contract._fields:
                return {
                    "amount": float(contract.wage or 0.0),
                    "source": "contract",
                    "reference": contract.display_name,
                }
        if self.performance_manual_basic_salary:
            return {
                "amount": float(self.performance_manual_basic_salary or 0.0),
                "source": "manual",
                "reference": _("Employee fallback basic salary"),
            }
        return {
            "amount": 0.0,
            "source": "none",
            "reference": False,
        }

    @api.depends("evaluation_service_start_date", "create_date")
    def _compute_evaluation_eligibility(self):
        today = fields.Date.context_today(self)
        for employee in self:
            start_date = employee._get_service_start_date()
            months_of_service = ((today.year - start_date.year) * 12) + (today.month - start_date.month)
            if today.day < start_date.day:
                months_of_service -= 1
            eligible = months_of_service >= 6
            employee.is_evaluation_eligible = eligible
            employee.evaluation_exclusion_reason = (
                False
                if eligible
                else "Service period is less than six months; annual evaluation is excluded."
            )
