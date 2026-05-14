from odoo import models, fields
import jq

class OdkImport(models.Model):
    _inherit = 'odk.import'

    target_registry = fields.Selection(
        selection_add=[
            ('g2p.crop.registry', 'Crop Registry'),
        ],
        ondelete={
            'g2p.crop.registry': 'cascade',
        },
    )

    def process_records(self, instance_id=None, last_sync_time=None):
        if self.target_registry == 'g2p.crop.registry':
            return self._process_crop_registry_records(instance_id, last_sync_time)
        return super().process_records(instance_id=instance_id, last_sync_time=last_sync_time)

    def _process_crop_registry_records(self, instance_id=None, last_sync_time=None):
        self.ensure_one()
        data = self.odk_config.download_records(
            instance_id=instance_id,
            last_sync_time=last_sync_time
        )
        partner_count = 0
        for member in data['value']:
            mapped_json = jq.first(self.json_formatter, member)
            mapped_json = self._resolve_crop_registry_m2o(mapped_json)
            mapped_json.pop('total_farmers', None)
            self.env['g2p.crop.registry'].sudo().create(mapped_json)
            partner_count += 1
            data.update({'form_updated': True})
        data.update({'partner_count': partner_count})
        return data

    def _resolve_crop_registry_m2o(self, vals):
        env = self.env

        code_fields = {
            'region_name_id':           'g2p.region',
            'zone_name_id':             'g2p.zone',
            'woreda_name_id':           'g2p.woreda',
            'crop_name_id':             'g2p.crop',
            'crop_variety_id':          'g2p.crop.category',
            'cultivation_crop_name_id': 'g2p.crop',
            'sown_crop_name_id':        'g2p.crop',
            'harvested_crop_name_id':   'g2p.crop',
            'live_stock_type_id':       'g2p.livestock.type',
        }

        name_fields = {
            'crop_season_id': 'g2p.season',
        }

        for field, model in code_fields.items():
            value = vals.get(field)
            if value:
                record = env[model].sudo().search([('code', '=', value)], limit=1)
                vals[field] = record.id if record else False
            else:
                vals[field] = False

        for field, model in name_fields.items():
            value = vals.get(field)
            if value:
                record = env[model].sudo().search([('name', '=', value)], limit=1)
                vals[field] = record.id if record else False
            else:
                vals[field] = False

        return vals