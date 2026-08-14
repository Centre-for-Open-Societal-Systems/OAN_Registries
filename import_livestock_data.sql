-- =========================================================================
-- IMPORTANT PREREQUISITE:
-- Before running this SQL, you MUST upgrade the module in Odoo so that
-- the database schema is updated. Odoo needs to create the new table 
-- "g2p_livestock_population" and add the new columns to "g2p_livestock_type".
-- =========================================================================

-- 1. Update the existing Livestock Catalog (g2p_livestock_type)
UPDATE g2p_livestock_type 
SET description = 'Arid-zone livestock species tracked in Ethiopia''s national population dashboard.',
    icon_url = 'https://lis.moa.gov.et/wp/wp-content/uploads/2025/05/camel-population.svg',
    dataset_id = 61
WHERE species_code ILIKE 'camel';

UPDATE g2p_livestock_type 
SET description = 'A vital livestock species in Ethiopia, including zebu cattle known for resilience to harsh climates and a crucial role in agriculture and livelihoods.',
    icon_url = 'https://lis.moa.gov.et/wp/wp-content/uploads/2025/05/cattle-population.svg',
    dataset_id = 61
WHERE species_code ILIKE 'cattle';

UPDATE g2p_livestock_type 
SET description = 'Major small ruminant livestock species tracked in Ethiopia''s national population dashboard.',
    icon_url = 'https://lis.moa.gov.et/wp/wp-content/uploads/2025/05/goat-population.svg',
    dataset_id = 61
WHERE species_code ILIKE 'goat';

UPDATE g2p_livestock_type 
SET description = 'Major small ruminant livestock species tracked in Ethiopia''s national population dashboard.',
    icon_url = 'https://lis.moa.gov.et/wp/wp-content/uploads/2025/05/sheep-population.svg',
    dataset_id = 61
WHERE species_code ILIKE 'sheep';

-- 2. Insert Population Data into g2p_livestock_population
-- We use a CTE and JOIN to dynamically get the species_code instead of hardcoding it.
-- The ON CONFLICT ensures it safely updates records if you run it multiple times.

INSERT INTO g2p_livestock_population (species_code, census_year, population_total, source_record_count, create_date, write_date)
WITH data_to_insert (species_code, census_year, population_total, source_record_count) AS (
    VALUES 
    ('camel', 2011, 1102095, 56),
    ('camel', 2012, 2520724, 114),
    ('camel', 2014, 1098290, 54),
    ('camel', 2016, 1210336, 54),
    ('camel', 2017, 1204985, 52),
    ('camel', 2018, 1418435, 50),
    ('camel', 2019, 3172630, 58),
    ('camel', 2020, 3729322, 164),
    ('camel', 2021, 8145756, 166),
    ('camel', 2022, 6979212, 158),
    
    ('cattle', 2011, 53382128, 138),
    ('cattle', 2012, 54832951, 136),
    ('cattle', 2014, 55027213, 132),
    ('cattle', 2016, 59486601, 132),
    ('cattle', 2017, 59486601, 132),
    ('cattle', 2018, 60391952, 132),
    ('cattle', 2019, 59626205, 156),
    ('cattle', 2020, 61591086, 164),
    ('cattle', 2021, 70291692, 166),
    ('cattle', 2022, 66272429, 158),
    
    ('goat', 2011, 22786883, 138),
    ('goat', 2012, 33798728, 136),
    ('goat', 2014, 28163269, 132),
    ('goat', 2016, 30200161, 132),
    ('goat', 2017, 30200161, 132),
    ('goat', 2018, 32738317, 132),
    ('goat', 2019, 50957330, 156),
    ('goat', 2020, 36805893, 164),
    ('goat', 2021, 52463454, 166),
    ('goat', 2022, 45788648, 158),
    
    ('sheep', 2011, 25508939, 138),
    ('sheep', 2012, 27430649, 136),
    ('sheep', 2014, 27347871, 132),
    ('sheep', 2016, 30697879, 132),
    ('sheep', 2017, 30697879, 132),
    ('sheep', 2018, 31302190, 132),
    ('sheep', 2019, 35494018, 156),
    ('sheep', 2020, 32855473, 164),
    ('sheep', 2021, 42914785, 166),
    ('sheep', 2022, 38036905, 158)
)
SELECT 
    t.id AS species_code, 
    d.census_year, 
    d.population_total, 
    d.source_record_count,
    NOW(),
    NOW()
FROM data_to_insert d
JOIN g2p_livestock_type t ON lower(t.species_code) = d.species_code
ON CONFLICT ON CONSTRAINT g2p_livestock_population_species_year_uidx 
DO UPDATE SET 
    population_total = EXCLUDED.population_total,
    source_record_count = EXCLUDED.source_record_count,
    write_date = NOW();
