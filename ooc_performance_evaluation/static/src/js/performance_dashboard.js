/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

const { Component, onWillStart, useState } = owl;

class PerformanceDashboard extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({
            scope: "employee",
            loading: false,
            resetFiltersLabel: _t("Reset Filters"),
            labels: {
                dashboardFiltersTitle: _t("Dashboard Filters"),
                dashboardFiltersSubtitle: _t("Refine the KPI, evaluation, and reward insights shown below."),
                operatingPosture: _t("Operating Posture"),
                liveMetrics: _t("Live Metrics"),
                operationalSnapshot: _t("Operational Snapshot"),
                metricsCaption: _t("Click any card to drill into the underlying records."),
                biShortcuts: _t("BI Shortcuts"),
                analysisViews: _t("Analysis Views"),
                biCaption: _t("Open pivot, graph, and approval queues already scoped to the current filters."),
                focusEyebrow: _t("Action Blocks"),
                focusTitle: _t("Priority View"),
                focusCaption: _t("Organized operational blocks tuned to the current dashboard role and filters."),
                analyticsEyebrow: _t("Analytics"),
                analyticsTitle: _t("Visual BI"),
                analyticsCaption: _t("Distribution panels adapt to the active dashboard filters."),
                noRecordsTitle: _t("No records in this panel yet."),
                noRecordsSubtitle: _t("Once the workflow starts producing data, this feed will update automatically."),
                noRelatedSubtitle: _t("Once related actions appear, they will surface here."),
                shareLabel: _t("Share"),
            },
            filters: {
                cycle_id: { label: "", value: "all", options: [] },
                department_id: { label: "", value: "all", options: [] },
                state: { label: "", value: "", options: [] },
                rating: { label: "", value: "", options: [] },
                evaluation_category: { label: "", value: "", options: [] },
                reward_status: { label: "", value: "", options: [] },
            },
            dashboard: {
                hero: { eyebrow: "", title: "", subtitle: "" },
                posture: { tone: "stable", label: "", note: "" },
                hero_pills: [],
                hero_actions: [],
                rail_cards: [],
                metrics: [],
                bi_actions: [],
                focus_panels: [],
                analytics_panels: [],
                primary_list: { eyebrow: "", title: "", caption: "", items: [] },
                secondary_list: { eyebrow: "", title: "", caption: "", items: [] },
            },
        });

        onWillStart(async () => {
            this.state.scope =
                this.props.action?.params?.dashboard_scope ||
                this.props.action?.context?.dashboard_scope ||
                "employee";
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        const filters = Object.fromEntries(
            Object.entries(this.state.filters).map(([key, value]) => [key, value.value])
        );
        const dashboard = await this.orm.call("performance.dashboard", "get_dashboard_data", [this.state.scope, filters]);
        if (dashboard) {
            Object.assign(this.state.dashboard, dashboard);
            if (dashboard.filters) {
                Object.assign(this.state.filters, dashboard.filters);
            }
        }
        this.state.loading = false;
    }

    async onFilterChange(key, ev) {
        this.state.filters[key].value = ev.target.value;
        await this.loadDashboard();
    }

    async resetFilters() {
        for (const filter of Object.values(this.state.filters)) {
            filter.value = filter.options?.[0]?.value || "";
        }
        await this.loadDashboard();
    }

    openAction(action) {
        if (!action) {
            return;
        }
        this.action.doAction(action);
    }
}

PerformanceDashboard.template = "ooc_performance_evaluation.PerformanceDashboard";
registry.category("actions").add("ooc_performance_dashboard", PerformanceDashboard);
