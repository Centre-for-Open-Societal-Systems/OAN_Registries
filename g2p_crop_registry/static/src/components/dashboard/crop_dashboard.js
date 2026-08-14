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
            table { width: 100%; border-collapse: collapse; margin-top: 20px; table-layout: fixed; word-wrap: break-word; }
            th, td { border: 1px solid #dee2e6; padding: 5px; font-size: 10px; overflow-wrap: break-word; }
            th { background-color: #f8f9fa; text-align: left; font-size: 11px; }
            thead { display: table-header-group; }
            tfoot { display: table-footer-group; }
            
            .chart-row-full { margin-bottom: 40px; text-align: center; page-break-inside: avoid; }
            .chart-col-full img { height: 320px; width: auto; max-width: 100%; display: block; margin: 0 auto; background: white; }
            
            .chart-row-half { display: flex; justify-content: space-between; margin-bottom: 20px; page-break-before: always; }
            .chart-col-half { width: 48%; text-align: center; }
            .chart-col-half img { width: 100%; height: auto; display: block; margin: 0 auto; background: white; }
            
            .chart-title { text-align: center; color: #555; margin-bottom: 5px; font-size: 14px; font-weight: bold; }
        `;
        pdfContent.appendChild(printStyles);

        // Header
        const header = document.createElement('div');
        header.innerHTML = `
            <h1 style="text-align: center; color: #333; margin-bottom: 5px;">Crop Sown Registry Report</h1>
            <hr style="margin-bottom: 20px; border: 1px solid #eee;">
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

        // Charts snapshots - Custom Layout
        const chartGrid = document.createElement('div');
        chartGrid.id = 'chartsContainer';
        
        const chartTitles = {
            'yieldChart': 'Expected vs Actual Yield (Overall)',
            'areaChart': 'Area Distribution by Crop',
            'areaCompChart': 'Planned vs Actual Area',
            'regionYieldChart': 'Yield Comparison by Region'
        };

        const createChartContainer = (canvasId, isHalfWidth) => {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return null;
            
            const container = document.createElement('div');
            container.className = isHalfWidth ? 'chart-col-half' : 'chart-col-full';
            
            const title = document.createElement('div');
            title.className = 'chart-title';
            title.innerText = chartTitles[canvasId];
            container.appendChild(title);

            const img = document.createElement('img');
            img.src = canvas.toDataURL('image/png', 1.0);
            container.appendChild(img);
            
            return container;
        };
        
        // 1. First graph: yieldChart (Full width)
        const row1 = document.createElement('div');
        row1.className = 'chart-row-full';
        const yieldContainer = createChartContainer('yieldChart', false);
        if (yieldContainer) row1.appendChild(yieldContainer);
        chartGrid.appendChild(row1);

        // 2. Second graph: areaCompChart (Full width)
        const row2 = document.createElement('div');
        row2.className = 'chart-row-full';
        const areaCompContainer = createChartContainer('areaCompChart', false);
        if (areaCompContainer) row2.appendChild(areaCompContainer);
        chartGrid.appendChild(row2);

        // 3. Third section: areaChart & regionYieldChart (Horizontally aligned, forced to next page)
        const row3 = document.createElement('div');
        row3.className = 'chart-row-half';
        const areaContainer = createChartContainer('areaChart', true);
        const regionYieldContainer = createChartContainer('regionYieldChart', true);
        
        if (areaContainer) row3.appendChild(areaContainer);
        if (regionYieldContainer) row3.appendChild(regionYieldContainer);
        
        chartGrid.appendChild(row3);
        
        pdfContent.appendChild(chartGrid);

        // Table Container (will be forced to a new page)
        const tableContainer = document.createElement('div');
        tableContainer.id = 'tableContainer';

        // Table Title
        const tableTitle = document.createElement('h3');
        tableTitle.innerHTML = 'Crop Sown Registry Details';
        tableTitle.style.color = '#333';
        tableTitle.style.marginBottom = '15px';
        tableTitle.style.textAlign = 'center';
        tableTitle.style.marginTop = '0px';
        tableContainer.appendChild(tableTitle);

        // Data Table
        const table = document.createElement('table');
        const thead = `
            <thead>
                <tr>
                    <th>Farmer Name</th>
                    <th>Fayda ID</th>
                    <th>Zone</th>
                    <th>Crop Name</th>
                    <th>Season</th>
                    <th>Planned Area</th>
                    <th>Actual Area</th>
                    <th>Expected Yield</th>
                    <th>Actual Yield</th>
                </tr>
            </thead>
        `;
        
        let tbody = '<tbody>';
        for (const row of this.state.stats.table_data) {
            tbody += `
                <tr>
                    <td>${row.farmer_name || ''}</td>
                    <td>${row.fyda_id || ''}</td>
                    <td>${row.zone || ''}</td>
                    <td>${row.crop_name || ''}</td>
                    <td>${row.season || ''}</td>
                    <td>${parseFloat(row.planned_area || 0).toFixed(2)}</td>
                    <td>${parseFloat(row.actual_area || 0).toFixed(2)}</td>
                    <td>${parseFloat(row.expected_yield || 0).toFixed(2)}</td>
                    <td>${parseFloat(row.actual_yield || 0).toFixed(2)}</td>
                </tr>
            `;
        }
        tbody += '</tbody>';
        table.innerHTML = thead + tbody;
        tableContainer.appendChild(table);

        pdfContent.appendChild(tableContainer);

        // Generate PDF
        const opt = {
            margin:       10,
            filename:     'crop_sown_registry_report.pdf',
            image:        { type: 'jpeg', quality: 1.0 },
            html2canvas:  { scale: 2, useCORS: true, windowWidth: 1200 },
            jsPDF:        { unit: 'mm', format: 'a4', orientation: 'landscape' },
            pagebreak:    { mode: 'css', before: ['.page-break', '#tableContainer'], avoid: ['.chart-row', 'tr'] }
        };

        html2pdf().set(opt).from(pdfContent).save();
    }
}

registry.category("actions").add("crop_registry.dashboard", CropDashboard);
