/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

export class LivestockDashboard extends Component {
    static template = "g2p_livestock_registry.LivestockDashboard";

    setup() {
        this.orm    = useService("orm");
        this.action = useService("action");
        this.state  = useState({
            loading: true,
            data: null,
            filterOptions: null,
            filters: {
                region_id: false,
                woreda_id: false,
                owner_id: false,
                species: false,
                date_from: false,
                date_to: false,
            },
        });
        onMounted(async () => {
            await this.loadFilterOptions();
            await this.loadData();
        });
    }

    async loadFilterOptions() {
        try {
            this.state.filterOptions = await this.orm.call(
                "g2p.livestock.dashboard", "get_filter_options", [], {});
        } catch (e) {
            console.error(e);
        }
    }

    onFilterChange(key, ev) {
        const val = ev.target.value;
        this.state.filters[key] = (key === "region_id" || key === "woreda_id" || key === "owner_id")
            ? (val ? parseInt(val) : false)
            : (val || false);
    }

    async applyFilters() {
        await this.loadData();
    }

    async resetFilters() {
        this.state.filters = {
            region_id: false, woreda_id: false, owner_id: false,
            species: false, date_from: false, date_to: false,
        };
        await this.loadData();
    }

    async exportReport() {
        try {
            const url = await this.orm.call(
                "g2p.livestock.dashboard", "action_export_report", [], { filters: this.state.filters });
            window.open(url, "_self");
        } catch (e) {
            console.error(e);
        }
    }

    async exportReportPdf() {
        try {
            const url = await this.orm.call(
                "g2p.livestock.dashboard", "action_export_report_pdf", [], { filters: this.state.filters });
            window.open(url, "_self");
        } catch (e) {
            console.error(e);
        }
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "g2p.livestock.dashboard", "get_dashboard_data", [], { filters: this.state.filters });
            this.state.data    = data;
            this.state.loading = false;
            setTimeout(() => this._drawCharts(), 60);
        } catch (e) {
            console.error(e);
            this.state.loading = false;
        }
    }

    _drawCharts() {
        const d = this.state.data;
        if (!d) return;
        this._donut("ld-health-chart",
            ["Healthy","Sick","Quarantined","Deceased"],
            [d.health.healthy, d.health.sick, d.health.quarantined, d.health.deceased],
            ["#22c55e","#f59e0b","#f97316","#ef4444"]);
        this._donut("ld-vax-chart",
            ["Up to date","Overdue","None"],
            [d.vaccination.up_to_date, d.vaccination.overdue, d.vaccination.none],
            ["#3b82f6","#f59e0b","#e2e8f0"]);
    }

    _donut(id, labels, values, colors) {
        const canvas = document.getElementById(id);
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const W = canvas.width, H = canvas.height;
        const cx = W/2, cy = H/2, R = Math.min(W,H)/2 - 4, r = R*0.55;
        const total = values.reduce((a,b) => a+b, 0);
        ctx.clearRect(0,0,W,H);
        if (!total) {
            ctx.beginPath(); ctx.arc(cx,cy,R,0,Math.PI*2);
            ctx.fillStyle="#e5e7eb"; ctx.fill();
        } else {
            let a = -Math.PI/2;
            values.forEach((v,i) => {
                const s = (v/total)*Math.PI*2;
                ctx.beginPath(); ctx.moveTo(cx,cy);
                ctx.arc(cx,cy,R,a,a+s);
                ctx.closePath(); ctx.fillStyle=colors[i]; ctx.fill();
                a += s;
            });
        }
        ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2);
        ctx.fillStyle="#fff"; ctx.fill();
    }

    navTo(domain, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "g2p.livestock.registry",
            views: [[false,"list"],[false,"form"]],
            domain: domain,
            target: "current",
        });
    }

    get healthPct() {
        const d = this.state.data;
        return d && d.total_animals ? Math.round((d.health.healthy/d.total_animals)*100) : 0;
    }
    get vaxPct() {
        const d = this.state.data;
        return d && d.total_animals ? Math.round((d.vaccination.up_to_date/d.total_animals)*100) : 0;
    }
}

registry.category("actions").add("g2p_livestock_dashboard", LivestockDashboard);