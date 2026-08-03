from odoo.tests.common import TransactionCase

class TestPestWeedManagement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Farmer',
            'is_farmer': 'yes',
        })

        cls.category = cls.env['g2p.crop.category'].create({
            'name': 'Cereal',
        })

        cls.crop = cls.env['g2p.crop'].create({
            'name': 'Maize',
            'category_id': cls.category.id,
        })

        cls.crop_registry = cls.env['g2p.crop.registry'].create({
            'partner_id': cls.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
        })

        cls.production = cls.env['g2p.crop.production'].create({
            'crop_registry_id': cls.crop_registry.id,
            'crop_name_id': cls.crop.id,
        })

        cls.infestation = cls.env['g2p.crop.infestation.incident'].create({
            'production_id': cls.production.id,
            'crop_name_id': cls.crop.id,
            'observation_date': '2025-06-01'
        })

    def test_pest_method_of_control_onchange(self):
        pest_line = self.env['g2p.crop.pest.line'].new({
            'infestation_id': self.infestation.id,
            'pesticide_method': 'chemical_spray',
            'pesticide_type': 'insecticide',
            'pesticide_name': 'Test Insecticide',
            'pesticide_frequency': 'Once a week'
        })

        # Change method to hand picking
        pest_line.pesticide_method = 'hand_picking'
        pest_line._onchange_pesticide_method()

        # Verify fields are cleared
        self.assertFalse(pest_line.pesticide_type)
        self.assertFalse(pest_line.pesticide_name)
        self.assertFalse(pest_line.pesticide_frequency)

    def test_disease_method_of_control_onchange(self):
        disease_line = self.env['g2p.crop.disease.line'].new({
            'infestation_id': self.infestation.id,
            'method_of_control': 'chemical_spray',
            'fungicide_type': 'fungal',
            'fungicide_name': 'Test Fungicide',
            'frequency_of_application': 'Once a week'
        })

        disease_line.method_of_control = 'early_harvesting'
        disease_line._onchange_method_of_control_disease()

        self.assertFalse(disease_line.fungicide_type)
        self.assertFalse(disease_line.fungicide_name)
        self.assertFalse(disease_line.frequency_of_application)


