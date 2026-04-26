from odoo import _, api, fields, models


class PerformanceDashboard(models.AbstractModel):
    _name = "performance.dashboard"
    _description = "Performance Dashboard"

    def _action_window(self, name, model, domain=None, context=None, res_id=False, view_mode="list,form"):
        action = {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "form" if res_id else view_mode,
            "target": "current",
            "context": context or {"create": False},
        }
        if res_id:
            action["res_id"] = res_id
            action["views"] = [[False, "form"]]
        else:
            action["domain"] = domain or []
            action["views"] = [[False, mode] for mode in view_mode.split(",") if mode in {"list", "form", "graph", "pivot", "kanban"}]
        return action

    def _normalize_filters(self, filters=None):
        filters = filters or {}
        normalized = {
            "cycle_id": int(filters["cycle_id"]) if filters.get("cycle_id") not in (False, None, "", "all") else False,
            "department_id": int(filters["department_id"]) if filters.get("department_id") not in (False, None, "", "all") else False,
            "state": filters.get("state") or False,
            "rating": filters.get("rating") or False,
            "evaluation_category": filters.get("evaluation_category") or False,
            "reward_status": filters.get("reward_status") or False,
        }
        return normalized

    def _apply_evaluation_filters(self, domain, filters):
        filters = self._normalize_filters(filters)
        if filters["cycle_id"]:
            domain.append(("cycle_id", "=", filters["cycle_id"]))
        if filters["department_id"]:
            domain.append(("department_id", "=", filters["department_id"]))
        if filters["state"]:
            domain.append(("state", "=", filters["state"]))
        if filters["rating"]:
            domain.append(("rating", "=", filters["rating"]))
        if filters["evaluation_category"]:
            domain.append(("evaluation_category", "=", filters["evaluation_category"]))
        if filters["reward_status"]:
            domain.append(("reward_status", "=", filters["reward_status"]))
        return domain

    def _apply_cycle_filter(self, domain, filters):
        filters = self._normalize_filters(filters)
        if filters["cycle_id"]:
            domain.append(("cycle_id", "=", filters["cycle_id"]))
        return domain

    def _evaluation_domain_for_scope(self, scope, filters=None):
        user = self.env.user
        if scope == "employee":
            domain = [("employee_id.user_id", "=", user.id)]
            return self._apply_evaluation_filters(domain, filters)
        if scope == "manager":
            domain = [("manager_id.user_id", "=", user.id)]
            return self._apply_evaluation_filters(domain, filters)
        if scope == "section":
            domain = [("employee_id.evaluation_section_id.manager_id.user_id", "=", user.id)]
            return self._apply_evaluation_filters(domain, filters)
        return self._apply_evaluation_filters([], filters)

    def _selection_domain_for_scope(self, scope, filters=None):
        user = self.env.user
        if scope == "employee":
            domain = [("employee_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        if scope == "manager":
            domain = [("manager_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        if scope == "section":
            domain = [("employee_id.evaluation_section_id.manager_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        return self._apply_cycle_filter([], filters)

    def _appeal_domain_for_scope(self, scope, filters=None):
        user = self.env.user
        if scope == "employee":
            domain = [("employee_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        if scope == "manager":
            domain = [("evaluation_id.manager_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        if scope == "section":
            domain = [("employee_id.evaluation_section_id.manager_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        return self._apply_cycle_filter([], filters)

    def _plan_domain_for_scope(self, scope, filters=None):
        user = self.env.user
        if scope == "employee":
            domain = [("employee_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        if scope == "manager":
            domain = [("manager_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        if scope == "section":
            domain = [("employee_id.evaluation_section_id.manager_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        return self._apply_cycle_filter([], filters)

    def _event_domain_for_scope(self, scope, filters=None):
        user = self.env.user
        if scope == "employee":
            domain = [("employee_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        if scope == "manager":
            domain = [("employee_id.parent_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        if scope == "section":
            domain = [("employee_id.evaluation_section_id.manager_id.user_id", "=", user.id)]
            return self._apply_cycle_filter(domain, filters)
        return self._apply_cycle_filter([], filters)

    def _build_filter_payload(self, scope, filters):
        filters = self._normalize_filters(filters)
        option_filters = dict(filters, department_id=False, evaluation_category=False)
        option_scope = scope if scope in ("employee", "manager", "section") else "hr"
        option_domain = self._evaluation_domain_for_scope(option_scope, option_filters)
        available_departments = self.env["performance.evaluation"].sudo().search(option_domain).mapped("department_id")
        visible_filters = self._visible_filters_for_scope(scope)
        cycle_options = [{"value": "all", "label": _("All Cycles")}]
        cycle_options.extend(
            {
                "value": str(cycle.id),
                "label": cycle.name,
            }
            for cycle in self.env["performance.cycle"].sudo().search([], order="year desc, id desc", limit=12)
        )
        return {
            "cycle_id": {
                "label": _("Cycle"),
                "value": str(filters["cycle_id"]) if filters["cycle_id"] else "all",
                "options": cycle_options,
                "visible": "cycle_id" in visible_filters,
            },
            "department_id": {
                "label": _("Department"),
                "value": str(filters["department_id"]) if filters["department_id"] else "all",
                "options": [{"value": "all", "label": _("All Departments")}]
                + [{"value": str(department.id), "label": department.display_name} for department in available_departments.sorted("name")],
                "visible": "department_id" in visible_filters,
            },
            "state": {
                "label": _("Evaluation State"),
                "value": filters["state"] or "",
                "options": [{"value": "", "label": _("All States")}]
                + [{"value": value, "label": label} for value, label in self.env["performance.evaluation"]._fields["state"].selection],
                "visible": "state" in visible_filters,
            },
            "rating": {
                "label": _("Rating"),
                "value": filters["rating"] or "",
                "options": [{"value": "", "label": _("All Ratings")}]
                + [{"value": rating, "label": self._display_rating(rating)} for rating in ["Excellent", "Very Good", "Good", "Acceptable", "Weak"]],
                "visible": "rating" in visible_filters,
            },
            "evaluation_category": {
                "label": _("Category"),
                "value": filters["evaluation_category"] or "",
                "options": [{"value": "", "label": _("All Categories")}]
                + [{"value": value, "label": label} for value, label in self.env["performance.evaluation"]._fields["evaluation_category"].selection],
                "visible": "evaluation_category" in visible_filters,
            },
            "reward_status": {
                "label": _("Reward Status"),
                "value": filters["reward_status"] or "",
                "options": [{"value": "", "label": _("All Reward States")}]
                + [{"value": value, "label": label} for value, label in self.env["performance.evaluation"]._fields["reward_status"].selection],
                "visible": "reward_status" in visible_filters,
            },
        }

    def _build_bi_actions(self, scope, filters):
        eval_domain = self._evaluation_domain_for_scope(scope if scope in ("employee", "manager", "section") else "hr", filters)
        cycle_filter = self._normalize_filters(filters)["cycle_id"]
        cycle_domain = [("id", "=", cycle_filter)] if cycle_filter else []
        return [
            {
                "label": _("Evaluation Pivot"),
                "description": _("Analyze scores by cycle, department, rating, and reward state."),
                "action": self._action_window(_("Evaluation Pivot"), "performance.evaluation", domain=eval_domain, view_mode="pivot,graph,list,form"),
            },
            {
                "label": _("Reward Approval Queue"),
                "description": _("Review payable staff rewards and their approval stage."),
                "action": self._action_window(_("Staff Rewards Approval"), "performance.reward.batch", domain=cycle_domain, view_mode="list,form"),
            },
            {
                "label": _("Cycle BI"),
                "description": _("Open cycle-level progress, completion, and publication analysis."),
                "action": self._action_window(_("Evaluation Cycles"), "performance.cycle", domain=cycle_domain, view_mode="graph,pivot,list,form"),
            },
        ]

    def _latest_cycle(self):
        return self.env["performance.cycle"].sudo().search([], order="year desc, id desc", limit=1)

    def _scope_label(self, scope):
        return {
            "employee": _("My Performance Desk"),
            "manager": _("Team Performance Console"),
            "section": _("Section Performance Console"),
            "hr": _("HR Performance Command Center"),
            "executive": _("Executive Performance Overview"),
        }.get(scope, _("Performance Dashboard"))

    def _recent_item(self, title, badge, meta=None, side_value=None, side_label=None, footnote=None, action=None):
        return {
            "title": title,
            "badge": badge or "",
            "meta": meta or [],
            "side_value": side_value or "",
            "side_label": side_label or "",
            "footnote": footnote or "",
            "action": action,
        }

    def _build_posture(self, tone, label, note):
        return {"tone": tone, "label": label, "note": note}

    def _visible_filters_for_scope(self, scope):
        scope_map = {
            "employee": {"cycle_id", "state", "rating", "reward_status"},
            "manager": {"cycle_id", "state", "rating", "reward_status"},
            "section": {"cycle_id", "state", "rating", "reward_status"},
            "hr": {"cycle_id", "department_id", "state", "rating", "evaluation_category", "reward_status"},
            "executive": {"cycle_id", "department_id", "rating", "reward_status"},
        }
        return scope_map.get(scope, {"cycle_id", "state", "rating", "reward_status"})

    def _display_rating(self, rating):
        return {
            "Excellent": _("Excellent"),
            "Very Good": _("Very Good"),
            "Good": _("Good"),
            "Acceptable": _("Acceptable"),
            "Weak": _("Weak"),
        }.get(rating, rating or _("Unrated"))

    def _build_distribution_item(self, label, value, total, hint, action=None, sublabel=None):
        ratio = round((value / total) * 100.0, 2) if total else 0.0
        return {
            "label": label,
            "value": value,
            "ratio": ratio,
            "hint": hint,
            "sublabel": sublabel or "",
            "action": action,
        }

    def _build_focus_item(self, label, value, note, action=None, tone="neutral"):
        return {
            "label": label,
            "value": value,
            "note": note,
            "action": action,
            "tone": tone,
        }

    def _build_dashboard_analytics(self, scope, filters):
        eval_scope = scope if scope in ("employee", "manager", "section") else "hr"
        eval_domain = self._evaluation_domain_for_scope(eval_scope, filters)
        evaluations = self.env["performance.evaluation"].sudo().search(eval_domain)
        total_evaluations = len(evaluations)
        reward_total = round(sum(evaluations.mapped("reward_amount")), 2)
        rating_items = []
        for rating in ["Excellent", "Very Good", "Good", "Acceptable", "Weak"]:
            count = len(evaluations.filtered(lambda evaluation, current=rating: evaluation.rating == current))
            rating_items.append(
                self._build_distribution_item(
                    self._display_rating(rating),
                    count,
                    total_evaluations,
                    _("%s evaluation(s)") % count,
                    action=self._action_window(_("Evaluations"), "performance.evaluation", domain=eval_domain + [("rating", "=", rating)]),
                )
            )

        reward_items = []
        for status, label in self.env["performance.evaluation"]._fields["reward_status"].selection:
            status_evaluations = evaluations.filtered(lambda evaluation, current=status: evaluation.reward_status == current)
            amount = round(sum(status_evaluations.mapped("reward_amount")), 2)
            reward_items.append(
                self._build_distribution_item(
                    label,
                    amount,
                    reward_total,
                    _("%s staff") % len(status_evaluations),
                    action=self._action_window(_("Evaluations"), "performance.evaluation", domain=eval_domain + [("reward_status", "=", status)]),
                    sublabel=_("Amount"),
                )
            )

        department_items = []
        department_map = {}
        for evaluation in evaluations.filtered("department_id"):
            bucket = department_map.setdefault(
                evaluation.department_id.id,
                {"department": evaluation.department_id, "count": 0, "score": 0.0},
            )
            bucket["count"] += 1
            bucket["score"] += evaluation.final_score
        ranked_departments = sorted(
            department_map.values(),
            key=lambda entry: (entry["score"] / entry["count"]) if entry["count"] else 0.0,
            reverse=True,
        )[:5]
        top_department_score = max(
            [(entry["score"] / entry["count"]) for entry in ranked_departments if entry["count"]],
            default=0.0,
        )
        for entry in ranked_departments:
            average_score = round(entry["score"] / entry["count"], 2) if entry["count"] else 0.0
            department_items.append(
                self._build_distribution_item(
                    entry["department"].display_name,
                    average_score,
                    top_department_score,
                    _("%s evaluation(s)") % entry["count"],
                    action=self._action_window(
                        _("Department Evaluations"),
                        "performance.evaluation",
                        domain=eval_domain + [("department_id", "=", entry["department"].id)],
                    ),
                    sublabel=_("Avg Score"),
                )
            )

        return [
            {
                "eyebrow": _("Ratings"),
                "title": _("Rating Distribution"),
                "caption": _("How the current evaluation population is distributed across the final ratings."),
                "items": rating_items,
            },
            {
                "eyebrow": _("Rewards"),
                "title": _("Reward Pipeline"),
                "caption": _("Reward exposure by approval status for the current filters."),
                "items": reward_items,
                "summary_label": _("Total Reward Exposure"),
                "summary_value": reward_total,
            },
            {
                "eyebrow": _("Departments"),
                "title": _("Department Leaders"),
                "caption": _("Best average scores across departments within the current analysis scope."),
                "items": department_items,
            },
        ]

    def _get_employee_dashboard(self, filters=None):
        eval_model = self.env["performance.evaluation"].sudo()
        selection_model = self.env["performance.goal.selection"].sudo()
        appeal_model = self.env["performance.appeal"].sudo()
        plan_model = self.env["performance.development.plan"].sudo()
        event_model = self.env["performance.event.participation"].sudo()
        eval_domain = self._evaluation_domain_for_scope("employee", filters)
        latest_eval = eval_model.search(eval_domain, order="cycle_id desc, id desc", limit=1)
        latest_selection = selection_model.search(self._selection_domain_for_scope("employee", filters), order="cycle_id desc, id desc", limit=1)
        open_appeals = appeal_model.search(self._appeal_domain_for_scope("employee", filters) + [("state", "not in", ("closed", "decision_issued", "rejected_late"))])
        active_plans = plan_model.search(self._plan_domain_for_scope("employee", filters) + [("state", "not in", ("completed", "closed"))])
        events_count = event_model.search_count(self._event_domain_for_scope("employee", filters))
        posture = self._build_posture(
            "stable" if latest_eval and latest_eval.final_score >= 80 else "attention" if latest_eval else "active",
            _("On Track") if latest_eval and latest_eval.final_score >= 80 else _("Needs Attention") if latest_eval else _("Waiting Inputs"),
            _("Your latest score is %s with a %s rating.") % (round(latest_eval.final_score, 2), self._display_rating(latest_eval.rating)) if latest_eval else _("Your evaluation record is waiting for the first cycle inputs."),
        )
        primary_items = []
        for evaluation in eval_model.search(eval_domain, order="cycle_id desc, id desc", limit=5):
            primary_items.append(
                self._recent_item(
                    evaluation.employee_id.name,
                    evaluation.state,
                    meta=[evaluation.cycle_id.name, evaluation.department_id.display_name or "", evaluation.evaluation_category],
                    side_value=round(evaluation.final_score, 2),
                    side_label=self._display_rating(evaluation.rating),
                    footnote=evaluation.manager_comment or _("No manager note yet."),
                    action=self._action_window(_("Evaluation"), "performance.evaluation", res_id=evaluation.id),
                )
            )
        secondary_items = []
        for plan in active_plans[:5]:
            secondary_items.append(
                self._recent_item(
                    _("Development Plan"),
                    plan.state,
                    meta=[plan.cycle_id.name, plan.manager_id.name or ""],
                    side_value=round(plan.progress, 0),
                    side_label=_("Progress"),
                    footnote=plan.deadline and _("Deadline %s") % plan.deadline or _("Deadline pending"),
                    action=self._action_window(_("Development Plan"), "performance.development.plan", res_id=plan.id),
                )
            )
        if not secondary_items:
            for appeal in appeal_model.search(self._appeal_domain_for_scope("employee", filters), order="id desc", limit=5):
                secondary_items.append(
                    self._recent_item(
                        appeal.appeal_reason,
                        appeal.state,
                        meta=[appeal.cycle_id.name, appeal.evaluation_id.employee_id.name],
                        side_value=appeal.submission_date or "",
                        side_label=_("Submitted"),
                        footnote=appeal.final_decision or appeal.requested_change or "",
                        action=self._action_window(_("Appeal"), "performance.appeal", res_id=appeal.id),
                    )
                )
        focus_panels = [
            {
                "eyebrow": _("Current Cycle"),
                "title": _("My Standing"),
                "caption": _("Your current cycle status, reward position, and development exposure."),
                "items": [
                    self._build_focus_item(
                        _("Goal Selection"),
                        latest_selection.state if latest_selection else _("Not Selected"),
                        _("Current goal agreement for the selected cycle."),
                        self._action_window(_("My Goals"), "performance.goal.selection", domain=self._selection_domain_for_scope("employee", filters)),
                        "teal",
                    ),
                    self._build_focus_item(
                        _("Reward Status"),
                        latest_eval.reward_status if latest_eval else _("Pending"),
                        _("Latest reward stage attached to your published evaluation."),
                        latest_eval and latest_eval.reward_batch_id and self._action_window(_("Reward Batch"), "performance.reward.batch", res_id=latest_eval.reward_batch_id.id) or None,
                        "mint",
                    ),
                    self._build_focus_item(
                        _("Development Plans"),
                        len(active_plans),
                        _("Open development plans requiring your follow-up."),
                        self._action_window(_("Development Plans"), "performance.development.plan", domain=self._plan_domain_for_scope("employee", filters)),
                        "amber",
                    ),
                ],
            },
            {
                "eyebrow": _("Action Items"),
                "title": _("Employee Follow Up"),
                "caption": _("The items that still require your attention in the current workflow."),
                "items": [
                    self._build_focus_item(
                        _("Open Appeals"),
                        len(open_appeals),
                        _("Appeals still moving through review or committee response."),
                        self._action_window(_("Appeals"), "performance.appeal", domain=self._appeal_domain_for_scope("employee", filters)),
                        "rose",
                    ),
                    self._build_focus_item(
                        _("Event Contributions"),
                        events_count,
                        _("Institutional participation records counted in your evaluation."),
                        self._action_window(_("Events"), "performance.event.participation", domain=self._event_domain_for_scope("employee", filters)),
                        "slate",
                    ),
                    self._build_focus_item(
                        _("Latest Evaluation"),
                        round(latest_eval.final_score, 2) if latest_eval else _("Pending"),
                        _("Most recent final score in your filtered dashboard scope."),
                        latest_eval and self._action_window(_("Evaluation"), "performance.evaluation", res_id=latest_eval.id) or None,
                        "teal",
                    ),
                ],
            },
        ]
        return {
            "hero": {
                "eyebrow": _("Personal Workspace"),
                "title": self._scope_label("employee"),
                "subtitle": _("Track your approved goals, published evaluations, appeals, and development actions from one place."),
            },
            "posture": posture,
            "hero_pills": [
                {"label": _("Latest Score"), "value": round(latest_eval.final_score, 2) if latest_eval else _("Pending")},
                {"label": _("Goal Status"), "value": latest_selection.state if latest_selection else _("Not Selected")},
                {"label": _("Open Appeals"), "value": len(open_appeals)},
            ],
            "hero_actions": [
                {"label": _("My Evaluations"), "variant": "light", "action": self._action_window(_("My Evaluation"), "performance.evaluation", domain=eval_domain)},
                {"label": _("My Goals"), "variant": "soft", "action": self._action_window(_("My Goals"), "performance.goal.selection", domain=self._selection_domain_for_scope("employee", filters))},
                {"label": _("Development Plans"), "variant": "dark", "action": self._action_window(_("Development Plans"), "performance.development.plan", domain=self._plan_domain_for_scope("employee", filters))},
            ],
            "rail_cards": [
                {"label": _("Evaluations"), "value": eval_model.search_count(eval_domain), "hint": _("All of your cycle evaluations"), "action": self._action_window(_("My Evaluation"), "performance.evaluation", domain=eval_domain)},
                {"label": _("Approved Goals"), "value": latest_selection.total_goal_count if latest_selection else 0, "hint": _("Current approved goal set"), "action": self._action_window(_("My Goals"), "performance.goal.selection", domain=self._selection_domain_for_scope("employee", filters))},
                {"label": _("Event Contributions"), "value": events_count, "hint": _("Recognized institutional contributions"), "action": self._action_window(_("Events"), "performance.event.participation", domain=self._event_domain_for_scope("employee", filters))},
                {"label": _("Appeals"), "value": appeal_model.search_count(self._appeal_domain_for_scope("employee", filters)), "hint": _("Appeal records you submitted"), "action": self._action_window(_("Appeals"), "performance.appeal", domain=self._appeal_domain_for_scope("employee", filters))},
                {"label": _("Development Plans"), "value": plan_model.search_count(self._plan_domain_for_scope("employee", filters)), "hint": _("Plans assigned to you"), "action": self._action_window(_("Development Plans"), "performance.development.plan", domain=self._plan_domain_for_scope("employee", filters))},
            ],
            "metrics": [
                {"label": _("Goal Score"), "value": round(latest_eval.goal_score, 2) if latest_eval else 0, "hint": _("Weighted individual and institutional result"), "tone": "teal", "action": latest_eval and self._action_window(_("Evaluation"), "performance.evaluation", res_id=latest_eval.id)},
                {"label": _("Institutional"), "value": round(latest_eval.institutional_score, 2) if latest_eval else 0, "hint": _("Shared KPI score pulled into your evaluation"), "tone": "mint", "action": latest_eval and self._action_window(_("Evaluation"), "performance.evaluation", res_id=latest_eval.id)},
                {"label": _("Discipline"), "value": round(latest_eval.discipline_score, 2) if latest_eval else 0, "hint": _("Attendance and leave-based score"), "tone": "amber", "action": latest_eval and self._action_window(_("Evaluation"), "performance.evaluation", res_id=latest_eval.id)},
                {"label": _("Events"), "value": round(latest_eval.events_score, 2) if latest_eval else 0, "hint": _("Institutional participation contribution"), "tone": "rose", "action": self._action_window(_("Events"), "performance.event.participation", domain=self._event_domain_for_scope("employee", filters))},
            ],
            "focus_panels": focus_panels,
            "primary_list": {
                "eyebrow": _("Recent Results"),
                "title": _("Evaluation Timeline"),
                "caption": _("Your latest performance records and their publication state."),
                "items": primary_items,
            },
            "secondary_list": {
                "eyebrow": _("Follow Up"),
                "title": _("Plans And Appeals"),
                "caption": _("Active plans first, then appeal records when they exist."),
                "items": secondary_items,
            },
        }

    def _get_manager_dashboard(self, scope, filters=None):
        eval_model = self.env["performance.evaluation"].sudo()
        selection_model = self.env["performance.goal.selection"].sudo()
        appeal_model = self.env["performance.appeal"].sudo()
        plan_model = self.env["performance.development.plan"].sudo()
        employee_model = self.env["hr.employee"].sudo()
        eval_domain = self._evaluation_domain_for_scope(scope, filters)
        pending_eval_domain = eval_domain + [("state", "in", ("waiting_inputs", "manager_evaluation", "manager_submitted", "hr_review"))]
        selection_domain = self._selection_domain_for_scope(scope, filters)
        pending_goal_domain = selection_domain + [("state", "in", ("submitted", "manager_approved"))]
        if scope == "manager":
            team_domain = [("parent_id.user_id", "=", self.env.user.id)]
            scope_title = self._scope_label("manager")
            scope_eyebrow = _("Direct Reports")
            institutional_score = 0.0
        else:
            team_domain = [("evaluation_section_id.manager_id.user_id", "=", self.env.user.id)]
            scope_title = self._scope_label("section")
            scope_eyebrow = _("Section Oversight")
            latest_cycle = self._latest_cycle()
            section_scores = self.env["performance.kpi.score"].sudo().search(
                [("cycle_id", "=", latest_cycle.id), ("owner_type", "=", "section"), ("section_id.manager_id.user_id", "=", self.env.user.id), ("state", "in", ("confirmed", "locked"))]
            ) if latest_cycle else self.env["performance.kpi.score"]
            institutional_score = sum(section_scores.mapped("weighted_score")) if section_scores else 0.0
        evaluations = eval_model.search(eval_domain)
        latest_cycle = self._latest_cycle()
        average_score = sum(evaluations.mapped("final_score")) / len(evaluations) if evaluations else 0.0
        pending_goal_count = selection_model.search_count(pending_goal_domain)
        pending_eval_count = eval_model.search_count(pending_eval_domain)
        open_appeals = appeal_model.search(self._appeal_domain_for_scope(scope, filters) + [("state", "not in", ("closed", "decision_issued", "rejected_late"))])
        active_plans = plan_model.search(self._plan_domain_for_scope(scope, filters) + [("state", "not in", ("completed", "closed"))])
        team_size = employee_model.search_count(team_domain)
        posture = self._build_posture(
            "attention" if pending_goal_count or pending_eval_count else "stable",
            _("Review Queue Active") if pending_goal_count or pending_eval_count else _("Stable Delivery"),
            _("There are %s goal approvals and %s evaluations still requiring action.") % (pending_goal_count, pending_eval_count)
            if pending_goal_count or pending_eval_count
            else _("No approval bottlenecks are visible for your current scope."),
        )
        top_items = []
        for evaluation in eval_model.search(eval_domain, order="final_score desc, id desc", limit=5):
            top_items.append(
                self._recent_item(
                    evaluation.employee_id.name,
                    self._display_rating(evaluation.rating),
                    meta=[evaluation.cycle_id.name, evaluation.department_id.display_name or "", evaluation.state],
                    side_value=round(evaluation.final_score, 2),
                    side_label=_("Score"),
                    footnote=evaluation.manager_comment or "",
                    action=self._action_window(_("Evaluation"), "performance.evaluation", res_id=evaluation.id),
                )
            )
        queue_items = []
        for selection in selection_model.search(pending_goal_domain, order="submitted_date asc, id asc", limit=5):
            queue_items.append(
                self._recent_item(
                    selection.employee_id.name,
                    selection.state,
                    meta=[selection.cycle_id.name, selection.department_id.display_name or ""],
                    side_value=selection.total_goal_count,
                    side_label=_("Goals"),
                    footnote=selection.manager_comment or selection.hr_comment or "",
                    action=self._action_window(_("Goal Selection"), "performance.goal.selection", res_id=selection.id),
                )
            )
        if not queue_items:
            for evaluation in eval_model.search(pending_eval_domain, order="cycle_id desc, id desc", limit=5):
                queue_items.append(
                    self._recent_item(
                        evaluation.employee_id.name,
                        evaluation.state,
                        meta=[evaluation.cycle_id.name, evaluation.evaluation_category],
                        side_value=round(evaluation.goal_score, 2),
                        side_label=_("Goal Score"),
                        footnote=evaluation.hr_comment or evaluation.manager_comment or "",
                        action=self._action_window(_("Evaluation"), "performance.evaluation", res_id=evaluation.id),
                    )
                )
        focus_panels = [
            {
                "eyebrow": _("Action Priority"),
                "title": _("Approval Pressure"),
                "caption": _("Where your current managerial attention is required first."),
                "items": [
                    self._build_focus_item(
                        _("Goal Approvals"),
                        pending_goal_count,
                        _("Goal selections still waiting for your approval lane."),
                        self._action_window(_("Goal Approvals"), "performance.goal.selection", domain=pending_goal_domain),
                        "amber",
                    ),
                    self._build_focus_item(
                        _("Pending Evaluations"),
                        pending_eval_count,
                        _("Evaluations still moving through review and submission."),
                        self._action_window(_("Evaluations"), "performance.evaluation", domain=pending_eval_domain),
                        "rose",
                    ),
                    self._build_focus_item(
                        _("Open Appeals"),
                        len(open_appeals),
                        _("Appeals in your reporting line that still need a response."),
                        self._action_window(_("Appeals"), "performance.appeal", domain=self._appeal_domain_for_scope(scope, filters)),
                        "slate",
                    ),
                ],
            },
            {
                "eyebrow": _("Team Health"),
                "title": _("Delivery Signals"),
                "caption": _("A compact view of performance strength, risk, and follow-up activity."),
                "items": [
                    self._build_focus_item(
                        _("Team Size"),
                        team_size,
                        _("Employees currently visible in your dashboard scope."),
                        None,
                        "teal",
                    ),
                    self._build_focus_item(
                        _("Average Score"),
                        round(average_score, 2),
                        _("Average final score across visible evaluations."),
                        self._action_window(_("Evaluations"), "performance.evaluation", domain=eval_domain),
                        "mint",
                    ),
                    self._build_focus_item(
                        _("Open Plans"),
                        len(active_plans),
                        _("Development plans still active for your people."),
                        self._action_window(_("Development Plans"), "performance.development.plan", domain=self._plan_domain_for_scope(scope, filters)),
                        "amber",
                    ),
                ] + ([
                    self._build_focus_item(
                        _("Section KPI"),
                        round(institutional_score, 2),
                        _("Central section KPI feeding section-head and employee results."),
                        latest_cycle and self._action_window(_("KPI Score Sheet"), "performance.kpi.score", domain=[("cycle_id", "=", latest_cycle.id), ("owner_type", "=", "section"), ("section_id.manager_id.user_id", "=", self.env.user.id)]) or None,
                        "teal",
                    )
                ] if scope == "section" else []),
            },
        ]
        return {
            "hero": {
                "eyebrow": scope_eyebrow,
                "title": scope_title,
                "subtitle": _("Monitor approvals, evaluation readiness, published scores, and follow-up actions for the people you oversee."),
            },
            "posture": posture,
            "hero_pills": [
                {"label": _("Team Size"), "value": team_size},
                {"label": _("Average Score"), "value": round(average_score, 2)},
                {"label": _("Open Appeals"), "value": len(open_appeals)},
            ],
            "hero_actions": [
                {"label": _("Team Evaluations"), "variant": "light", "action": self._action_window(_("Evaluations"), "performance.evaluation", domain=eval_domain)},
                {"label": _("Goal Approvals"), "variant": "soft", "action": self._action_window(_("Goal Approvals"), "performance.goal.selection", domain=selection_domain)},
                {"label": _("Development Plans"), "variant": "dark", "action": self._action_window(_("Development Plans"), "performance.development.plan", domain=self._plan_domain_for_scope(scope, filters))},
            ],
            "rail_cards": [
                {"label": _("Evaluations"), "value": eval_model.search_count(eval_domain), "hint": _("Records in your current scope"), "action": self._action_window(_("Evaluations"), "performance.evaluation", domain=eval_domain)},
                {"label": _("Pending Approvals"), "value": pending_goal_count, "hint": _("Goal selections waiting action"), "action": self._action_window(_("Goal Approvals"), "performance.goal.selection", domain=pending_goal_domain)},
                {"label": _("Pending Evaluations"), "value": pending_eval_count, "hint": _("Evaluations not yet finalized"), "action": self._action_window(_("Evaluations"), "performance.evaluation", domain=pending_eval_domain)},
                {"label": _("Published Results"), "value": eval_model.search_count(eval_domain + [("state", "in", ("published", "appealed", "closed"))]), "hint": _("Published or archived results"), "action": self._action_window(_("Published Evaluations"), "performance.evaluation", domain=eval_domain + [("state", "in", ("published", "appealed", "closed"))])},
                {"label": _("Open Appeals"), "value": len(open_appeals), "hint": _("Appeals requiring follow-up"), "action": self._action_window(_("Appeals"), "performance.appeal", domain=self._appeal_domain_for_scope(scope, filters))},
            ],
            "metrics": [
                {"label": _("Average Score"), "value": round(average_score, 2), "hint": _("Average across visible evaluations"), "tone": "teal", "action": self._action_window(_("Evaluations"), "performance.evaluation", domain=eval_domain)},
                {"label": _("Excellent Ratings"), "value": eval_model.search_count(eval_domain + [("rating", "=", "Excellent")]), "hint": _("Top performers in your scope"), "tone": "mint", "action": self._action_window(_("Excellent Evaluations"), "performance.evaluation", domain=eval_domain + [("rating", "=", "Excellent")])},
                {"label": _("Weak Ratings"), "value": eval_model.search_count(eval_domain + [("rating", "=", "Weak")]), "hint": _("Cases needing recovery plans"), "tone": "amber", "action": self._action_window(_("Weak Evaluations"), "performance.evaluation", domain=eval_domain + [("rating", "=", "Weak")])},
                {"label": _("Development Plans"), "value": len(active_plans), "hint": _("Open plans requiring follow-up"), "tone": "rose", "action": self._action_window(_("Development Plans"), "performance.development.plan", domain=self._plan_domain_for_scope(scope, filters))},
            ] + ([{"label": _("Section KPI"), "value": round(institutional_score, 2), "hint": _("Central institutional score feeding section evaluations"), "tone": "slate", "action": latest_cycle and self._action_window(_("KPI Score Sheet"), "performance.kpi.score", domain=[("cycle_id", "=", latest_cycle.id), ("owner_type", "=", "section"), ("section_id.manager_id.user_id", "=", self.env.user.id)])}] if scope == "section" else []),
            "focus_panels": focus_panels,
            "primary_list": {
                "eyebrow": _("Top Results"),
                "title": _("Top Performers"),
                "caption": _("Highest scores in your visible evaluation set."),
                "items": top_items,
            },
            "secondary_list": {
                "eyebrow": _("Action Queue"),
                "title": _("Approvals And Reviews"),
                "caption": _("Goal approvals first, then pending evaluations when the approval queue is clear."),
                "items": queue_items,
            },
        }

    def _get_hr_dashboard(self, scope, filters=None):
        cycle_model = self.env["performance.cycle"].sudo()
        eval_model = self.env["performance.evaluation"].sudo()
        appeal_model = self.env["performance.appeal"].sudo()
        plan_model = self.env["performance.development.plan"].sudo()
        kpi_model = self.env["performance.kpi"].sudo()
        normalized_filters = self._normalize_filters(filters)
        latest_cycle = self.env["performance.cycle"].sudo().browse(normalized_filters["cycle_id"]) if normalized_filters["cycle_id"] else self._latest_cycle()
        latest_cycle_eval_domain = [("cycle_id", "=", latest_cycle.id)] if latest_cycle else []
        latest_evaluations = eval_model.search(latest_cycle_eval_domain) if latest_cycle else eval_model.browse()
        missing_kpi_domain = [
            ("cycle_id", "=", latest_cycle.id),
            ("kpi_level", "in", ("organization", "department", "section")),
            ("state", "=", "locked"),
            ("score_sheet_id", "=", False),
        ] if latest_cycle else []
        missing_discipline_domain = latest_cycle_eval_domain + [("evaluation_category", "!=", "manager"), ("discipline_score_id", "=", False)] if latest_cycle else []
        pending_hr_domain = latest_cycle_eval_domain + [("state", "=", "hr_review")] if latest_cycle else []
        pending_appeal_domain = [("cycle_id", "=", latest_cycle.id), ("state", "not in", ("closed", "decision_issued", "rejected_late"))] if latest_cycle else [("state", "not in", ("closed", "decision_issued", "rejected_late"))]
        open_plan_domain = [("cycle_id", "=", latest_cycle.id), ("state", "not in", ("completed", "closed"))] if latest_cycle else [("state", "not in", ("completed", "closed"))]
        missing_kpi_count = kpi_model.search_count(missing_kpi_domain) if latest_cycle else 0
        missing_discipline_count = eval_model.search_count(missing_discipline_domain) if latest_cycle else 0
        pending_hr_count = eval_model.search_count(pending_hr_domain) if latest_cycle else 0
        reward_batch = latest_cycle.reward_batch_id if latest_cycle else self.env["performance.reward.batch"]
        posture = self._build_posture(
            "attention" if missing_kpi_count or missing_discipline_count or pending_hr_count else "stable",
            _("HR Review Required") if missing_kpi_count or missing_discipline_count or pending_hr_count else _("Cycle Controlled"),
            _("Latest cycle %s has %s missing KPI sheets, %s missing discipline links, and %s evaluations in HR review.") % (latest_cycle.name, missing_kpi_count, missing_discipline_count, pending_hr_count)
            if latest_cycle
            else _("Create a cycle to begin performance operations."),
        )
        cycle_items = []
        for cycle in cycle_model.search([], order="year desc, id desc", limit=5):
            cycle_items.append(
                self._recent_item(
                    cycle.name,
                    cycle.state,
                    meta=[_("Eligible %s") % cycle.eligible_employee_count, _("Appeals %s") % cycle.appeal_count],
                    side_value=round(cycle.average_final_score, 2),
                    side_label=_("Avg Score"),
                    footnote=_("%s/%s evaluations completed") % (cycle.completed_evaluation_count, cycle.evaluation_count),
                    action=self._action_window(_("Cycle"), "performance.cycle", res_id=cycle.id),
                )
            )
        review_items = []
        for evaluation in eval_model.search(pending_hr_domain, order="id asc", limit=5):
            review_items.append(
                self._recent_item(
                    evaluation.employee_id.name,
                    evaluation.state,
                    meta=[evaluation.cycle_id.name, evaluation.department_id.display_name or ""],
                    side_value=round(evaluation.final_score, 2),
                    side_label=_("Current Score"),
                    footnote=evaluation.hr_comment or evaluation.manager_comment or "",
                    action=self._action_window(_("Evaluation"), "performance.evaluation", res_id=evaluation.id),
                )
            )
        focus_panels = [
            {
                "eyebrow": _("Cycle Control"),
                "title": _("Data Readiness"),
                "caption": _("Critical inputs that must be complete before the cycle can move safely."),
                "items": [
                    self._build_focus_item(
                        _("Missing KPI Sheets"),
                        missing_kpi_count,
                        _("Locked institutional KPIs without centralized scores."),
                        self._action_window(_("Institutional KPIs"), "performance.kpi", domain=missing_kpi_domain),
                        "rose",
                    ),
                    self._build_focus_item(
                        _("Missing Discipline"),
                        missing_discipline_count,
                        _("Evaluations that still need discipline linkage."),
                        self._action_window(_("Evaluations"), "performance.evaluation", domain=missing_discipline_domain),
                        "amber",
                    ),
                    self._build_focus_item(
                        _("HR Review Queue"),
                        pending_hr_count,
                        _("Evaluations still waiting for HR confirmation."),
                        self._action_window(_("HR Evaluations"), "performance.evaluation", domain=pending_hr_domain),
                        "teal",
                    ),
                ],
            },
            {
                "eyebrow": _("Reward Governance"),
                "title": _("Cycle Reward Batch"),
                "caption": _("The current approval exposure for staff rewards in the selected cycle."),
                "items": [
                    self._build_focus_item(
                        _("Batch State"),
                        reward_batch.state if reward_batch else _("Not Ready"),
                        _("Reward batch lifecycle for the selected cycle."),
                        reward_batch and self._action_window(_("Reward Batch"), "performance.reward.batch", res_id=reward_batch.id) or None,
                        "slate",
                    ),
                    self._build_focus_item(
                        _("Pending Budget"),
                        reward_batch.pending_budget_count if reward_batch else 0,
                        _("Reward records still waiting for budget approval."),
                        reward_batch and self._action_window(_("Reward Batch"), "performance.reward.batch", res_id=reward_batch.id) or None,
                        "amber",
                    ),
                    self._build_focus_item(
                        _("Pending Board"),
                        reward_batch.pending_board_count if reward_batch else 0,
                        _("Reward records escalated to board approval."),
                        reward_batch and self._action_window(_("Reward Batch"), "performance.reward.batch", res_id=reward_batch.id) or None,
                        "rose",
                    ),
                    self._build_focus_item(
                        _("Approved Rewards"),
                        reward_batch.approved_count if reward_batch else 0,
                        _("Reward records fully approved in the batch."),
                        reward_batch and self._action_window(_("Reward Batch"), "performance.reward.batch", res_id=reward_batch.id) or None,
                        "mint",
                    ),
                ],
            },
        ]
        return {
            "hero": {
                "eyebrow": _("Performance Operations"),
                "title": self._scope_label(scope),
                "subtitle": _("Coordinate centralized KPI scoring, cycle readiness, HR review, appeals, and development follow-up from one control room."),
            },
            "posture": posture,
            "hero_pills": [
                {"label": _("Latest Cycle"), "value": latest_cycle.name if latest_cycle else _("None")},
                {"label": _("Completion"), "value": latest_cycle and round(latest_cycle.completion_rate, 2) or 0},
                {"label": _("Pending Appeals"), "value": appeal_model.search_count(pending_appeal_domain)},
            ],
            "hero_actions": [
                {"label": _("Cycles"), "variant": "light", "action": self._action_window(_("Evaluation Cycles"), "performance.cycle", domain=[])},
                {"label": _("KPI Score Sheet"), "variant": "soft", "action": self._action_window(_("KPI Score Sheet"), "performance.kpi.score", domain=latest_cycle and [("cycle_id", "=", latest_cycle.id)] or [])},
                {"label": _("HR Evaluations"), "variant": "dark", "action": self._action_window(_("HR Evaluations"), "performance.evaluation", domain=latest_cycle_eval_domain)},
                {"label": _("Reward Batch"), "variant": "soft", "action": self._action_window(_("Staff Rewards Approval"), "performance.reward.batch", domain=latest_cycle and [("cycle_id", "=", latest_cycle.id)] or [])},
            ],
            "rail_cards": [
                {"label": _("Cycles"), "value": cycle_model.search_count([]), "hint": _("All performance cycles"), "action": self._action_window(_("Evaluation Cycles"), "performance.cycle", domain=[])},
                {"label": _("Eligible Staff"), "value": latest_cycle.eligible_employee_count if latest_cycle else 0, "hint": _("Latest cycle eligibility snapshot"), "action": latest_cycle and self._action_window(_("Cycle"), "performance.cycle", res_id=latest_cycle.id)},
                {"label": _("Evaluations"), "value": len(latest_evaluations), "hint": _("Latest cycle evaluation records"), "action": self._action_window(_("Evaluations"), "performance.evaluation", domain=latest_cycle_eval_domain)},
                {"label": _("Appeals"), "value": appeal_model.search_count(pending_appeal_domain), "hint": _("Open appeal workload"), "action": self._action_window(_("Appeals"), "performance.appeal", domain=pending_appeal_domain)},
                {"label": _("Plans Open"), "value": plan_model.search_count(open_plan_domain), "hint": _("Development plans still active"), "action": self._action_window(_("Development Plans"), "performance.development.plan", domain=open_plan_domain)},
            ],
            "metrics": [
                {"label": _("Average Score"), "value": round(latest_cycle.average_final_score, 2) if latest_cycle else 0, "hint": _("Average final score in the latest cycle"), "tone": "teal", "action": self._action_window(_("Evaluations"), "performance.evaluation", domain=latest_cycle_eval_domain)},
                {"label": _("Published"), "value": latest_cycle.published_evaluation_count if latest_cycle else 0, "hint": _("Results already published"), "tone": "mint", "action": self._action_window(_("Published Evaluations"), "performance.evaluation", domain=latest_cycle_eval_domain + [("state", "in", ("published", "appealed", "closed"))])},
                {"label": _("Missing KPI"), "value": missing_kpi_count, "hint": _("Locked institutional KPI records without score sheets"), "tone": "amber", "action": self._action_window(_("Institutional KPIs"), "performance.kpi", domain=missing_kpi_domain)},
                {"label": _("Missing Discipline"), "value": missing_discipline_count, "hint": _("Non-manager evaluations still missing discipline"), "tone": "rose", "action": self._action_window(_("Evaluations"), "performance.evaluation", domain=missing_discipline_domain)},
                {"label": _("HR Review"), "value": pending_hr_count, "hint": _("Evaluations waiting HR confirmation"), "tone": "slate", "action": self._action_window(_("HR Evaluations"), "performance.evaluation", domain=pending_hr_domain)},
            ],
            "focus_panels": focus_panels,
            "primary_list": {
                "eyebrow": _("Cycle Monitor"),
                "title": _("Recent Cycles"),
                "caption": _("Cycle-level completion, average score, and appeal exposure."),
                "items": cycle_items,
            },
            "secondary_list": {
                "eyebrow": _("Review Queue"),
                "title": _("Evaluations Awaiting HR"),
                "caption": _("Latest records still in HR review."),
                "items": review_items,
            },
        }

    def _get_executive_dashboard(self, filters=None):
        eval_model = self.env["performance.evaluation"].sudo()
        normalized_filters = self._normalize_filters(filters)
        cycle = self.env["performance.cycle"].sudo().browse(normalized_filters["cycle_id"]) if normalized_filters["cycle_id"] else self._latest_cycle()
        eval_domain = self._evaluation_domain_for_scope("hr", filters)
        if cycle:
            eval_domain = [("cycle_id", "=", cycle.id)] + [domain for domain in eval_domain if domain[0] != "cycle_id"]
        evaluations = eval_model.search(eval_domain) if cycle else eval_model.browse()
        organization_score = 0.0
        reward_batch = cycle.reward_batch_id if cycle else self.env["performance.reward.batch"]
        if cycle:
            organization_score = sum(
                self.env["performance.kpi.score"].sudo().search(
                    [("cycle_id", "=", cycle.id), ("owner_type", "=", "organization"), ("state", "in", ("confirmed", "locked"))]
                ).mapped("weighted_score")
            )
        department_rows = []
        if cycle:
            self.env.cr.execute(
                """
                SELECT d.id, d.name, ROUND(AVG(e.final_score)::numeric, 2)
                FROM performance_evaluation e
                JOIN hr_department d ON d.id = e.department_id
                WHERE e.cycle_id = %s
                GROUP BY d.id, d.name
                ORDER BY AVG(e.final_score) DESC, d.name ASC
                LIMIT 5
                """,
                [cycle.id],
            )
            department_rows = self.env.cr.fetchall()
        performer_items = []
        for evaluation in eval_model.search(eval_domain, order="final_score desc, id desc", limit=5):
            performer_items.append(
                self._recent_item(
                    evaluation.employee_id.name,
                    self._display_rating(evaluation.rating),
                    meta=[evaluation.department_id.display_name or "", evaluation.evaluation_category],
                    side_value=round(evaluation.final_score, 2),
                    side_label=_("Score"),
                    footnote=evaluation.cycle_id.name,
                    action=self._action_window(_("Evaluation"), "performance.evaluation", res_id=evaluation.id),
                )
            )
        comparison_items = []
        for department_id, department_name, average_score in department_rows:
            comparison_items.append(
                self._recent_item(
                    department_name,
                    _("Department"),
                    meta=[cycle.name if cycle else ""],
                    side_value=average_score,
                    side_label=_("Avg Score"),
                    footnote=_("Ranked against other departments in the current cycle."),
                    action=self._action_window(_("Department Evaluations"), "performance.evaluation", domain=eval_domain + [("department_id", "=", department_id)]),
                )
            )
        posture = self._build_posture(
            "stable" if cycle and cycle.completion_rate >= 90 else "active",
            _("Portfolio Stable") if cycle and cycle.completion_rate >= 90 else _("Cycle In Motion"),
            _("Latest cycle %s is %.2f%% complete with an organization KPI score of %.2f.") % (cycle.name, cycle.completion_rate, organization_score) if cycle else _("No cycle data is available yet."),
        )
        focus_panels = [
            {
                "eyebrow": _("Executive Signals"),
                "title": _("Portfolio Health"),
                "caption": _("A compact executive view of delivery, risk, and intervention demand."),
                "items": [
                    self._build_focus_item(
                        _("Published Results"),
                        cycle.published_evaluation_count if cycle else 0,
                        _("Results already published in the selected cycle."),
                        self._action_window(_("Published Evaluations"), "performance.evaluation", domain=eval_domain + [("state", "in", ("published", "appealed", "closed"))]),
                        "teal",
                    ),
                    self._build_focus_item(
                        _("Weak Ratings"),
                        eval_model.search_count(eval_domain + [("rating", "=", "Weak")]),
                        _("Employees requiring close performance intervention."),
                        self._action_window(_("Weak Evaluations"), "performance.evaluation", domain=eval_domain + [("rating", "=", "Weak")]),
                        "rose",
                    ),
                    self._build_focus_item(
                        _("Open Appeals"),
                        self.env["performance.appeal"].sudo().search_count(cycle and [("cycle_id", "=", cycle.id), ("state", "not in", ("closed", "decision_issued", "rejected_late"))] or []),
                        _("Appeals still moving through the decision process."),
                        self._action_window(_("Appeals"), "performance.appeal", domain=cycle and [("cycle_id", "=", cycle.id)] or []),
                        "amber",
                    ),
                ],
            },
            {
                "eyebrow": _("Reward Exposure"),
                "title": _("Reward Governance"),
                "caption": _("Cycle-level reward totals and approval position for executive visibility."),
                "items": [
                    self._build_focus_item(
                        _("Batch State"),
                        reward_batch.state if reward_batch else _("Not Ready"),
                        _("Current reward approval stage for the cycle."),
                        reward_batch and self._action_window(_("Reward Batch"), "performance.reward.batch", res_id=reward_batch.id) or None,
                        "slate",
                    ),
                    self._build_focus_item(
                        _("Reward Total"),
                        reward_batch.total_reward_amount if reward_batch else 0,
                        _("Total monetary exposure for the staff reward batch."),
                        reward_batch and self._action_window(_("Reward Batch"), "performance.reward.batch", res_id=reward_batch.id) or None,
                        "mint",
                    ),
                    self._build_focus_item(
                        _("Pending Board"),
                        reward_batch.pending_board_count if reward_batch else 0,
                        _("Reward records waiting for board approval."),
                        reward_batch and self._action_window(_("Reward Batch"), "performance.reward.batch", res_id=reward_batch.id) or None,
                        "rose",
                    ),
                ],
            },
        ]
        return {
            "hero": {
                "eyebrow": _("Executive Readout"),
                "title": self._scope_label("executive"),
                "subtitle": _("Review organization KPI achievement, rating distribution, top performers, and department comparisons without opening operational records first."),
            },
            "posture": posture,
            "hero_pills": [
                {"label": _("Organization Score"), "value": round(organization_score, 2)},
                {"label": _("Average Score"), "value": round(sum(evaluations.mapped("final_score")) / len(evaluations), 2) if evaluations else 0},
                {"label": _("Appeals"), "value": cycle and cycle.appeal_count or 0},
            ],
            "hero_actions": [
                {"label": _("Cycle Overview"), "variant": "light", "action": cycle and self._action_window(_("Cycle"), "performance.cycle", res_id=cycle.id) or self._action_window(_("Evaluation Cycles"), "performance.cycle", domain=[])},
                {"label": _("Published Results"), "variant": "soft", "action": self._action_window(_("Published Evaluations"), "performance.evaluation", domain=eval_domain + [("state", "in", ("published", "appealed", "closed"))])},
                {"label": _("Institutional KPIs"), "variant": "dark", "action": self._action_window(_("KPI Score Sheet"), "performance.kpi.score", domain=cycle and [("cycle_id", "=", cycle.id)] or [])},
                {"label": _("Reward Batch"), "variant": "soft", "action": self._action_window(_("Staff Rewards Approval"), "performance.reward.batch", domain=cycle and [("cycle_id", "=", cycle.id)] or [])},
            ],
            "rail_cards": [
                {"label": _("Published"), "value": cycle and cycle.published_evaluation_count or 0, "hint": _("Published evaluations in the latest cycle"), "action": self._action_window(_("Published Evaluations"), "performance.evaluation", domain=eval_domain + [("state", "in", ("published", "appealed", "closed"))])},
                {"label": _("Excellent"), "value": eval_model.search_count(eval_domain + [("rating", "=", "Excellent")]), "hint": _("Employees with excellent ratings"), "action": self._action_window(_("Excellent Evaluations"), "performance.evaluation", domain=eval_domain + [("rating", "=", "Excellent")])},
                {"label": _("Very Good"), "value": eval_model.search_count(eval_domain + [("rating", "=", "Very Good")]), "hint": _("Very good performers"), "action": self._action_window(_("Very Good Evaluations"), "performance.evaluation", domain=eval_domain + [("rating", "=", "Very Good")])},
                {"label": _("Weak"), "value": eval_model.search_count(eval_domain + [("rating", "=", "Weak")]), "hint": _("Low performers requiring intervention"), "action": self._action_window(_("Weak Evaluations"), "performance.evaluation", domain=eval_domain + [("rating", "=", "Weak")])},
                {"label": _("Development Plans"), "value": self.env["performance.development.plan"].sudo().search_count([("cycle_id", "=", cycle.id)]) if cycle else 0, "hint": _("Plans created from latest cycle results"), "action": self._action_window(_("Development Plans"), "performance.development.plan", domain=cycle and [("cycle_id", "=", cycle.id)] or [])},
            ],
            "metrics": [
                {"label": _("Organization KPI"), "value": round(organization_score, 2), "hint": _("Central institutional score at organization level"), "tone": "teal", "action": self._action_window(_("KPI Score Sheet"), "performance.kpi.score", domain=cycle and [("cycle_id", "=", cycle.id), ("owner_type", "=", "organization")] or [])},
                {"label": _("Department KPIs"), "value": self.env["performance.kpi.score"].sudo().search_count(cycle and [("cycle_id", "=", cycle.id), ("owner_type", "=", "department")] or []), "hint": _("Department-level score sheets"), "tone": "mint", "action": self._action_window(_("KPI Score Sheet"), "performance.kpi.score", domain=cycle and [("cycle_id", "=", cycle.id), ("owner_type", "=", "department")] or [])},
                {"label": _("Section KPIs"), "value": self.env["performance.kpi.score"].sudo().search_count(cycle and [("cycle_id", "=", cycle.id), ("owner_type", "=", "section")] or []), "hint": _("Section-level score sheets"), "tone": "amber", "action": self._action_window(_("KPI Score Sheet"), "performance.kpi.score", domain=cycle and [("cycle_id", "=", cycle.id), ("owner_type", "=", "section")] or [])},
                {"label": _("Open Appeals"), "value": self.env["performance.appeal"].sudo().search_count(cycle and [("cycle_id", "=", cycle.id), ("state", "not in", ("closed", "decision_issued", "rejected_late"))] or []), "hint": _("Appeals still in progress"), "tone": "rose", "action": self._action_window(_("Appeals"), "performance.appeal", domain=cycle and [("cycle_id", "=", cycle.id)] or [])},
            ],
            "focus_panels": focus_panels,
            "primary_list": {
                "eyebrow": _("Top Performers"),
                "title": _("Highest Scores"),
                "caption": _("Best published outcomes in the current cycle."),
                "items": performer_items,
            },
            "secondary_list": {
                "eyebrow": _("Department View"),
                "title": _("Department Comparison"),
                "caption": _("Average scores by department for the latest cycle."),
                "items": comparison_items,
            },
        }

    @api.model
    def get_dashboard_data(self, scope=None, filters=None):
        scope = scope or "employee"
        filters = self._normalize_filters(filters)
        if scope == "employee":
            data = self._get_employee_dashboard(filters)
        elif scope in ("manager", "section"):
            data = self._get_manager_dashboard(scope, filters)
        elif scope == "executive":
            data = self._get_executive_dashboard(filters)
        else:
            data = self._get_hr_dashboard(scope, filters)
        data["filters"] = self._build_filter_payload(scope, filters)
        data["bi_actions"] = self._build_bi_actions(scope, filters)
        data["analytics_panels"] = self._build_dashboard_analytics(scope, filters)
        return data
