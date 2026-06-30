with open('g2p_crop_registry/views/crop_registry.xml', 'r') as f:
    lines = f.readlines()

# Biennial Crops group is lines 756-888 (0-indexed)
# Wait, let me extract the exact Biennial group.

with open('g2p_crop_registry/views/crop_registry.xml', 'r') as f:
    content = f.read()

import re

# Find the exact Biennial group
biennial_match = re.search(r'(\s*<group string="Biennial Crops" invisible="1">.*?</group>)', content, re.DOTALL)
if biennial_match:
    biennial_group = biennial_match.group(1)
else:
    print("Biennial group not found!")

# Remove it from its current position
content = content.replace(biennial_group, '')

# Find the end of Perennial group to insert Biennial group after it
perennial_end_match = re.search(r'(<group string="Perennial Crops" invisible="1">.*?</group>\n)', content, re.DOTALL)
if perennial_end_match:
    perennial_group_full = perennial_end_match.group(1)
    content = content.replace(perennial_group_full, perennial_group_full + biennial_group + '\n')
else:
    print("Perennial group not found!")

# Now remove the duplicated Sowing, Harvesting, Survey Personnel pages.
# We have a duplicate block that looks like:
duplicate_block = re.search(r'(<page string="Sowing">.*?</page>\n\s*<page string="Harvesting">.*?</page>\n\s*<page string="Survey Personnel">.*?</page>)', content, re.DOTALL)

# Wait, there are two of these blocks. We want to keep the FIRST one and remove the SECOND one.
if duplicate_block:
    matches = list(re.finditer(r'(<page string="Sowing">.*?</page>\n\s*<page string="Harvesting">.*?</page>\n\s*<page string="Survey Personnel">.*?</page>)', content, re.DOTALL))
    if len(matches) > 1:
        # Remove the second match
        start = matches[1].start()
        end = matches[1].end()
        content = content[:start] + content[end:]
        print("Removed duplicate pages")

with open('g2p_crop_registry/views/crop_registry.xml', 'w') as f:
    f.write(content)
