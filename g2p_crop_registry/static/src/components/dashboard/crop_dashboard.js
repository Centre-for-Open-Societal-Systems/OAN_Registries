/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class CropDashboard extends Component {
    static template = "crop_registry.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            options: {
                seasons: [],
                crops: [],
                regions: [],
                zones: [],
                woredas: [],
            },
            filters: {
                season_id: "",
                crop_id: "",
                region_id: "",
                zone_id: "",
                woreda_id: "",
            },
            stats: {
                total_planned_crop_area: 0,
                total_expected_yield: 0,
                total_actual_yield: 0,
                ratio_planned: 0,
                table_data: [],
            }
        });

        this.charts = {
            yield: null,
            area: null,
            areaComp: null,
            regionYield: null,
        };

        onWillStart(async () => {
            await loadJS("https://cdn.jsdelivr.net/npm/chart.js");
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js");
            await this.loadFilterOptions();
            await this.loadDashboardData();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    async loadFilterOptions() {
        const options = await this.orm.call("g2p.crop.registry", "get_dashboard_filter_options", []);
        this.state.options = options;
    }

    async loadDashboardData() {
        const stats = await this.orm.call("g2p.crop.registry", "get_dashboard_stats", [this.state.filters]);
        this.state.stats = stats;
        
        if (this.charts.yield) this.updateCharts();
    }

    async onFilterChange() {
        await this.loadDashboardData();
    }

    async clearFilters() {
        this.state.filters = {
            season_id: "",
            crop_id: "",
            region_id: "",
            zone_id: "",
            woreda_id: "",
        };
        await this.loadDashboardData();
    }

    renderCharts() {
        const yieldCtx = document.getElementById('yieldChart').getContext('2d');
        const areaCtx = document.getElementById('areaChart').getContext('2d');
        const areaCompCtx = document.getElementById('areaCompChart').getContext('2d');
        const regionYieldCtx = document.getElementById('regionYieldChart').getContext('2d');

        // Yield Chart (Line/Bar)
        this.charts.yield = new Chart(yieldCtx, {
            type: 'line',
            data: {
                labels: this.state.stats.top_crops_planned_labels || [],
                datasets: [
                    {
                        label: 'Expected Yield',
                        data: this.state.stats.top_crops_planned_data || [],
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgb(54, 162, 235)',
                        borderWidth: 1
                    },
                    {
                        label: 'Actual Yield',
                        data: this.state.stats.top_crops_actual_data || [],
                        backgroundColor: 'rgba(75, 192, 192, 0.5)',
                        borderColor: 'rgb(75, 192, 192)',
                        borderWidth: 1
                    }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        // Area Doughnut Chart
        this.charts.area = new Chart(areaCtx, {
            type: 'doughnut',
            data: {
                labels: this.state.stats.top_crops_area_labels || [],
                datasets: [{
                    data: this.state.stats.top_crops_area_data || [],
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(54, 162, 235, 0.7)',
                        'rgba(255, 206, 86, 0.7)',
                        'rgba(75, 192, 192, 0.7)',
                        'rgba(153, 102, 255, 0.7)',
                    ]
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        // Area Comparison Chart
        this.charts.areaComp = new Chart(areaCompCtx, {
            type: 'bar',
            data: {
                labels: this.state.stats.area_comp_labels || [],
                datasets: [
                    {
                        label: 'Planned Area (HA)',
                        data: this.state.stats.area_comp_planned || [],
                        backgroundColor: 'rgba(255, 159, 64, 0.5)',
                        borderColor: 'rgb(255, 159, 64)',
                        borderWidth: 1
                    },
                    {
                        label: 'Actual Area (HA)',
                        data: this.state.stats.area_comp_actual || [],
                        backgroundColor: 'rgba(153, 102, 255, 0.5)',
                        borderColor: 'rgb(153, 102, 255)',
                        borderWidth: 1
                    }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        // Region Yield Chart
        this.charts.regionYield = new Chart(regionYieldCtx, {
            type: 'bar',
            data: {
                labels: this.state.stats.region_labels || [],
                datasets: [
                    {
                        label: 'Expected Yield',
                        data: this.state.stats.region_planned_yield || [],
                        backgroundColor: 'rgba(255, 205, 86, 0.5)',
                        borderColor: 'rgb(255, 205, 86)',
                        borderWidth: 1
                    },
                    {
                        label: 'Actual Yield',
                        data: this.state.stats.region_actual_yield || [],
                        backgroundColor: 'rgba(201, 203, 207, 0.5)',
                        borderColor: 'rgb(201, 203, 207)',
                        borderWidth: 1
                    }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    updateCharts() {
        this.charts.yield.data.labels = this.state.stats.top_crops_planned_labels;
        this.charts.yield.data.datasets[0].data = this.state.stats.top_crops_planned_data;
        this.charts.yield.data.datasets[1].data = this.state.stats.top_crops_actual_data;
        this.charts.yield.update();

        this.charts.area.data.labels = this.state.stats.top_crops_area_labels;
        this.charts.area.data.datasets[0].data = this.state.stats.top_crops_area_data;
        this.charts.area.update();

        this.charts.areaComp.data.labels = this.state.stats.area_comp_labels;
        this.charts.areaComp.data.datasets[0].data = this.state.stats.area_comp_planned;
        this.charts.areaComp.data.datasets[1].data = this.state.stats.area_comp_actual;
        this.charts.areaComp.update();

        this.charts.regionYield.data.labels = this.state.stats.region_labels;
        this.charts.regionYield.data.datasets[0].data = this.state.stats.region_planned_yield;
        this.charts.regionYield.data.datasets[1].data = this.state.stats.region_actual_yield;
        this.charts.regionYield.update();
    }

    async exportPDF() {
        const pdfContent = document.createElement('div');
        pdfContent.style.padding = '20px';
        pdfContent.style.fontFamily = 'Arial, sans-serif';
        
        const printStyles = document.createElement('style');
        printStyles.innerHTML = `
            table { page-break-inside: auto; }
            tr { page-break-inside: avoid; page-break-after: auto; }
            thead { display: table-header-group; }
            tfoot { display: table-footer-group; }
        `;
        pdfContent.appendChild(printStyles);

        // Header
        const header = document.createElement('div');
        header.innerHTML = `
            <h1 style="text-align: center; color: #333;">Crop Sown Registry Report</h1>
            <hr style="margin-bottom: 20px;">
        `;
        pdfContent.appendChild(header);

        // Filters applied
        const activeFilters = [];
        if (this.state.filters.season_id) {
            const s = this.state.options.seasons.find(x => x.id == this.state.filters.season_id);
            if (s) activeFilters.push(`Season: ${s.name}`);
        }
        if (this.state.filters.crop_id) {
            const c = this.state.options.crops.find(x => x.id == this.state.filters.crop_id);
            if (c) activeFilters.push(`Crop: ${c.name}`);
        }
        
        if (activeFilters.length > 0) {
            const filtersDiv = document.createElement('div');
            filtersDiv.innerHTML = `<strong>Filters Applied:</strong> ${activeFilters.join(', ')}<br><br>`;
            pdfContent.appendChild(filtersDiv);
        }

        // Charts snapshots
        const chartGrid = document.createElement('div');
        chartGrid.style.display = 'flex';
        chartGrid.style.flexWrap = 'wrap';
        chartGrid.style.gap = '20px';
        chartGrid.style.marginBottom = '30px';
        
        const canvasIds = ['yieldChart', 'areaChart', 'areaCompChart', 'regionYieldChart'];
        for (const id of canvasIds) {
            const canvas = document.getElementById(id);
            if (canvas) {
                const img = document.createElement('img');
                img.src = canvas.toDataURL('image/png');
                img.style.width = '48%';
                img.style.objectFit = 'contain';
                chartGrid.appendChild(img);
            }
        }
        pdfContent.appendChild(chartGrid);

        // Table Title on New Page
        const tableTitle = document.createElement('h3');
        tableTitle.id = 'tableTitle';
        tableTitle.innerHTML = 'Crop Sown Registry Details';
        tableTitle.style.color = '#333';
        tableTitle.style.marginBottom = '15px';
        tableTitle.style.textAlign = 'center';
        pdfContent.appendChild(tableTitle);

        // Data Table
        const table = document.createElement('table');
        table.style.width = '100%';
        table.style.borderCollapse = 'collapse';
        table.style.marginTop = '20px';
        
        const thead = `
            <thead>
                <tr style="background-color: #f8f9fa; text-align: left;">
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Farmer Name</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Fayda ID</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Zone</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Crop Name</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Season</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Planned Area</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Actual Area</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Expected Yield</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Actual Yield</th>
                </tr>
            </thead>
        `;
        
        let tbody = '<tbody>';
        for (const row of this.state.stats.table_data) {
            tbody += `
                <tr style="page-break-inside: avoid;">
                    <td style="border: 1px solid #dee2e6; padding: 8px;">${row.farmer_name || ''}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">${row.fyda_id || ''}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">${row.zone || ''}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">${row.crop_name || ''}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">${row.season || ''}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">${row.planned_area || 0}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">${row.actual_area || 0}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">${row.expected_yield || 0}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">${row.actual_yield || 0}</td>
                </tr>
            `;
        }
        tbody += '</tbody>';
        table.innerHTML = thead + tbody;
        
        pdfContent.appendChild(table);

        // Generate PDF
        const opt = {
            margin:       10,
            filename:     'crop_sown_registry_report.pdf',
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2, windowWidth: 1200 },
            jsPDF:        { unit: 'mm', format: 'a4', orientation: 'landscape' },
            pagebreak:    { mode: 'css', before: '#tableTitle', avoid: 'tr' }
        };

        html2pdf().set(opt).from(pdfContent).save();
    }
}

registry.category("actions").add("crop_registry.dashboard", CropDashboard);
