INSERT INTO g2p_crop_category (id, name, description) VALUES
  (1, 'Cereal Crops', NULL),
  (2, 'Pulse Crops', NULL),
  (3, 'Oil Crops', NULL),
  (5, 'Tubers, Roots & Vegetable Crops', NULL),
  (6, 'Fruit Crops', NULL),
  (7, 'Forage and Pasture Crops', NULL),
  (10, 'Other Crops', NULL)
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
SELECT setval('g2p_crop_category_id_seq', (SELECT MAX(id) FROM g2p_crop_category));

INSERT INTO g2p_ecological_zone (id, name, description) VALUES
  (1, 'Kolla', 'Lowland zone, typically below 1,500 m'),
  (2, 'Weyna Dega', 'Mid-altitude zone, typically 1,500-2,300 m'),
  (3, 'Dega', 'Highland zone, typically above 2,300 m')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
SELECT setval('g2p_ecological_zone_id_seq', (SELECT MAX(id) FROM g2p_ecological_zone));
