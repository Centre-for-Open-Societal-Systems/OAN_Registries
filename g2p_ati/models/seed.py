from odoo import fields, models


class G2PSeedCatalog(models.Model):
    _name = "g2p.seed.catalog"
    _description = "Seeds/crops selectable on Ethio-Seed demand trend page"

    name = fields.Char(string="Name", required=True, index=True)


class G2PSeedDemandSummary(models.Model):
    _name = "g2p.seed.demand.summary"
    _description = "Annual seed demand KPIs"

    budget_year = fields.Integer(string="Budget Year", required=True, index=True)
    total_entries = fields.Integer(string="Total Entries")
    total_quantity_demanded = fields.Float(string="Total Quantity Demanded")
    average_quantity_per_entry = fields.Float(string="Average Quantity Per Entry")
    total_estimated_land_ha = fields.Float(string="Total Estimated Land (ha)")
    average_estimated_land_ha = fields.Float(string="Average Estimated Land (ha)")

    _sql_constraints = [
        (
            "seed_demand_summary_budget_year_uidx",
            "unique(budget_year)",
            "Record for this budget year already exists!",
        )
    ]


class G2PSeedDemandTrend(models.Model):
    _name = "g2p.seed.demand.trend"
    _description = "Seed demand trend by year and class"

    budget_year = fields.Integer(string="Budget Year", required=True, index=True)
    seed_class = fields.Char(string="Seed Class", required=True)
    quantity_demanded = fields.Float(string="Quantity Demanded", required=True)

    _sql_constraints = [
        (
            "seed_demand_trend_year_class_uidx",
            "unique(budget_year, seed_class)",
            "Record for this budget year and seed class already exists!",
        )
    ]


class G2PSeedDemandTrendByCrop(models.Model):
    _name = "g2p.seed.demand.trend.by.crop"
    _description = "Seed demand trend by crop, year, and class"

    crop_id = fields.Many2one("g2p.seed.catalog", string="Crop", required=True)
    crop_name = fields.Char(string="Crop Name", required=True)
    budget_year = fields.Integer(string="Budget Year", required=True, index=True)
    seed_class = fields.Char(string="Seed Class", required=True)
    quantity_demanded = fields.Float(string="Quantity Demanded", required=True)

    _sql_constraints = [
        (
            "seed_demand_trend_by_crop_uidx",
            "unique(crop_id, budget_year, seed_class)",
            "Record for this crop, budget year, and seed class already exists!",
        )
    ]
