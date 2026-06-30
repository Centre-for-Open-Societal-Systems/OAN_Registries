from odoo import api, fields, models, _


class G2PFarmerAPIRequest(models.Model):
    _name = "g2p.farmer.api.request"
    _description = "Farmer Search API Request"
    _order = "create_date desc"  # uses built-in create_date
    _rec_name = "bg_request_id"


    bg_request_id = fields.Char(
        string="Correlation ID",
        index=True,
    )
    reference_id = fields.Char(
        string="Reference ID",
        index=True,
    )
    batch_ids = fields.One2many(
        "g2p.farmer.api.batch",
        "request_id",
        string="Batches",
    )

    process_status = fields.Char(
        string="Status",
        default="PENDING",
    )
    response_status_code = fields.Integer(string="Response HTTP Status")
    attempt_count = fields.Integer(string="Attempt Count", default=0)
    requested_by = fields.Char(string="Requested By")
    # error_message = fields.Text(string="Error Message")
    completed_at = fields.Datetime(string="Completed At")

    request_data = fields.Text(
        string="Request Payload",
        required=True,
    )
    response_data = fields.Text(
        string="Response",
    )



class G2PFarmerAPIBatch(models.Model):
    _name = "g2p.farmer.api.batch"
    _description = "Farmer Search API Batch"
    _order = "create_date desc, batch_number asc"  # use create_date, not created_at


    request_id = fields.Many2one(
        "g2p.farmer.api.request",
        string="API Request",
        required=True,
        index=True,
        ondelete="cascade",
    )

    batch_number = fields.Integer(string="Batch Number", required=True)
    offset = fields.Integer(string="Offset", required=True)
    limit = fields.Integer(string="Limit", required=True)
    total_records = fields.Integer(string="Total Records")

    status = fields.Selection(
        [
            ("PENDING", "PENDING"),
            ("PROCESSING", "PROCESSING"),
            ("PROCESSED", "PROCESSED"),
            ("FAILED", "FAILED"),
        ],
        default="PENDING",
        required=True,
        index=True,
    )
    retry_count = fields.Integer(string="Retry Count", default=0)

    response = fields.Text(
        string="Response",
    )

    def action_open_request(self):
        """Open the related Farmer API Request record."""
        self.ensure_one()
        if not self.request_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "g2p.farmer.api.request",
            "view_mode": "form",
            "res_id": self.request_id.id,
            "target": "current",
        }


