from odoo import fields, models


class G2PLandPrepMethod(models.Model):
    _name = "g2p.land.prep.method"
    _description = "Land Preparation Method"

    name = fields.Char(string="Method Name", required=True)


class G2PWaterResourceLine(models.Model):
    _name = "g2p.water.resource.line"
    _description = "Water Resource Details"
    _rec_name = "water_resource_id"

    crop_registry_id = fields.Many2one('g2p.crop.registry', ondelete="cascade")
    annual_line_id = fields.Many2one('g2p.annual.line', ondelete="cascade")
    cluster_info_id = fields.Many2one('g2p.cluster.information', ondelete="cascade")
    # Cluster-specific FKs
    cluster_annual_line_id = fields.Many2one('g2p.annual.line', ondelete="cascade")
    crop_information_id = fields.Many2one('g2p.crop.information', ondelete="cascade")
    water_resource_id = fields.Many2one('g2p.water.source', string="Water Resource", required=True)
    method_id = fields.Char(string="Method")
    frequency = fields.Char(string="Frequency")

class G2PActualWaterResourceLine(models.Model):
    _name = "g2p.actual.water.resource.line"
    _description = "Actual Water Resource Details"

    crop_registry_id = fields.Many2one('g2p.crop.registry', ondelete="cascade")
    actual_annual_line_id = fields.Many2one('g2p.annual.actual.line', ondelete="cascade")
    annual_line_id = fields.Many2one('g2p.annual.line', ondelete="cascade")
    cluster_info_id = fields.Many2one('g2p.cluster.information', ondelete="cascade")
    water_resource_id = fields.Many2one('g2p.water.source', string="Water Resource", required=True)
    method_id = fields.Char(string="Method")
    frequency = fields.Char(string="Frequency")




