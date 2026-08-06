-- =========================================================================
-- IMPORTANT PREREQUISITE:
-- Before running this SQL, you MUST restart/upgrade the module in Odoo so that
-- the database schema is updated. Odoo needs to create the new tables
-- "g2p_seed_catalog", "g2p_seed_demand_summary", etc.
-- =========================================================================

-- seed_catalog
-- Source: https://ethioseed.moa.gov.et/load-seeds-home-page/
-- Records: 129

INSERT INTO g2p_seed_catalog (id, name) VALUES
  (1, 'Maize ( Zea mays L.)'),
  (2, 'Bread wheat (Triticum aestivum L.)'),
  (3, 'Durum Wheat'),
  (4, 'Food Barley'),
  (5, 'Malt Barley'),
  (6, 'Tef ( Eragrostis tef)'),
  (7, 'Sorghum (Sorghum bicolor)'),
  (8, 'Millet'),
  (9, 'Rice'),
  (10, 'Finger Millet'),
  (12, 'Triticale'),
  (13, 'Emmer wheat (Aja)'),
  (14, 'Buck wheat'),
  (15, 'Pearl millet'),
  (16, 'Foxtail millet'),
  (17, 'Quinoa'),
  (18, 'Food oat'),
  (19, 'Faba bean'),
  (20, 'Field pea'),
  (21, 'Dekoko'),
  (22, 'Chickpea'),
  (23, 'Cowpea'),
  (24, 'Lentil'),
  (25, 'Common/Haricot/ bean'),
  (26, 'Soybean'),
  (27, 'Grass pea/ ''Guaya'''),
  (28, 'Mung bean'),
  (29, 'Fenugreek'),
  (30, 'Noug'),
  (31, 'Linseed'),
  (32, 'Rapeseed'),
  (33, 'Sesame'),
  (34, 'Groundnut'),
  (35, 'Sunflower'),
  (36, 'Safflower'),
  (37, 'Vernonia'),
  (38, 'Castor'),
  (39, 'Camelina sativa'),
  (40, 'Irish potato'),
  (41, 'Sweet potato'),
  (42, 'Taro'),
  (43, 'Cassava'),
  (44, 'Enset'),
  (45, 'Yam'),
  (46, 'Tomato'),
  (47, 'Garlic'),
  (48, 'Onion'),
  (49, 'Shallot'),
  (50, 'Sweet/Hot Pepper'),
  (51, 'Cabbage'),
  (52, 'Carrot'),
  (53, 'Okra'),
  (54, 'Anchote'),
  (55, 'Summer squash'),
  (56, 'Summarsquash'),
  (57, 'Coriander'),
  (58, 'Black pepper'),
  (59, 'Ginger'),
  (60, 'Turmeric'),
  (61, 'Cardamom'),
  (62, 'Sweet annie'),
  (63, 'Citronella grass'),
  (64, 'Pyrethrum'),
  (65, 'Cumin'),
  (66, 'Lemmon grass'),
  (67, 'Speare mint'),
  (68, 'Spanish mint'),
  (69, 'African marigold'),
  (70, 'Rose Scented Geranium'),
  (71, 'Chamomile'),
  (72, 'Lemon verbena'),
  (73, 'Stevia'),
  (74, 'Hibiscus'),
  (75, 'Lavender'),
  (76, 'Majoram/Oregano'),
  (77, 'Sage'),
  (78, 'Vanilla'),
  (79, 'Basil'),
  (80, 'Banana'),
  (81, 'Mango'),
  (82, 'Pineapple'),
  (83, 'Wine grape'),
  (84, 'Avocado'),
  (85, 'Date palm'),
  (86, 'Tree lucerne'),
  (87, 'Elephant grass'),
  (88, 'Rhode'),
  (89, 'Panicum'),
  (90, 'Dolicos lablab'),
  (91, 'Phalaries'),
  (92, 'Trifolium'),
  (93, 'Vetch'),
  (94, 'Cow pea'),
  (95, 'Andropogon'),
  (96, 'Pigeon pea'),
  (97, 'Oats'),
  (98, 'Sesbania'),
  (99, 'Pennisetum polystachion'),
  (100, 'Panicum maximum'),
  (101, 'Lupin'),
  (102, 'Alfalfa (Medicago sativa)'),
  (103, 'Pennisetum sphacelatum'),
  (104, 'Perennial grass'),
  (105, 'Desho grass'),
  (106, 'Napier grass'),
  (107, 'Local forage legume'),
  (108, 'Mulberry'),
  (109, 'Cotton'),
  (110, 'Kenaf'),
  (111, 'Sugarcane'),
  (112, 'Coffee'),
  (113, 'Tobaco'),
  (114, 'Adzuki bean'),
  (115, 'Lima bean'),
  (116, 'Lettuce'),
  (117, 'Water melon'),
  (118, 'Musk melon'),
  (119, 'Broccoli'),
  (120, 'Cauliflower'),
  (121, 'Snap pea'),
  (122, 'Snow pea'),
  (123, 'Sweet corn'),
  (124, 'Kororima'),
  (125, 'Rose'),
  (126, 'Brachiaria brizantha cv. Xaraes descriptors'),
  (127, 'Sorghum forage'),
  (128, 'Forage Soyabean'),
  (129, 'Cacao'),
  (132, 'Ethiopian mustard')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;

-- Update sequence since we manually provided IDs
SELECT setval('g2p_seed_catalog_id_seq', (SELECT MAX(id) FROM g2p_seed_catalog));

-- seed_demand_summary
-- Source: https://ethioseed.moa.gov.et/api/demand-summary/
-- Records: 1

INSERT INTO g2p_seed_demand_summary (budget_year, total_entries, total_quantity_demanded, average_quantity_per_entry, total_estimated_land_ha, average_estimated_land_ha) VALUES
  (2017, 429, 3732506, 8700.48, 3493601.03, 13334.36)
ON CONFLICT ON CONSTRAINT g2p_seed_demand_summary_seed_demand_summary_budget_year_uidx DO NOTHING;

-- seed_demand_trend
-- Source: https://ethioseed.moa.gov.et/api/demand-summary/
-- Records: 5

INSERT INTO g2p_seed_demand_trend (budget_year, seed_class, quantity_demanded) VALUES
  (2017, 'Basic', 180148),
  (2017, 'Breeder', 50),
  (2017, 'Certified (C1)', 3552308),
  (2018, 'Basic', 4),
  (2018, 'Certified (C1)', 3114536)
ON CONFLICT ON CONSTRAINT g2p_seed_demand_trend_seed_demand_trend_year_class_uidx DO NOTHING;

-- seed_demand_trend_by_crop
-- Source: https://ethioseed.moa.gov.et/seed-demand-trend-by-class/{seed_id}/
-- Records: 18

INSERT INTO g2p_seed_demand_trend_by_crop (crop_id, crop_name, budget_year, seed_class, quantity_demanded) VALUES
  (1, 'Maize ( Zea mays L.)', 2017, 'Basic', 104691),
  (1, 'Maize ( Zea mays L.)', 2017, 'Certified (C1)', 1340557),
  (1, 'Maize ( Zea mays L.)', 2018, 'Basic', 0),
  (1, 'Maize ( Zea mays L.)', 2018, 'Certified (C1)', 1190811),
  (2, 'Bread wheat (Triticum aestivum L.)', 2017, 'Basic', 2607),
  (2, 'Bread wheat (Triticum aestivum L.)', 2017, 'Certified (C1)', 1118480),
  (2, 'Bread wheat (Triticum aestivum L.)', 2018, 'Basic', 4),
  (2, 'Bread wheat (Triticum aestivum L.)', 2018, 'Certified (C1)', 1224744),
  (6, 'Tef ( Eragrostis tef)', 2017, 'Certified (C1)', 118478),
  (6, 'Tef ( Eragrostis tef)', 2018, 'Certified (C1)', 73964),
  (7, 'Sorghum (Sorghum bicolor)', 2017, 'Basic', 12756),
  (7, 'Sorghum (Sorghum bicolor)', 2017, 'Certified (C1)', 87927),
  (7, 'Sorghum (Sorghum bicolor)', 2018, 'Basic', 0),
  (7, 'Sorghum (Sorghum bicolor)', 2018, 'Certified (C1)', 29369),
  (33, 'Sesame', 2017, 'Basic', 2163),
  (33, 'Sesame', 2017, 'Certified (C1)', 128001),
  (33, 'Sesame', 2018, 'Basic', 0),
  (33, 'Sesame', 2018, 'Certified (C1)', 11875)
ON CONFLICT ON CONSTRAINT g2p_seed_demand_trend_by_crop_seed_demand_trend_by_crop_uidx DO NOTHING;
