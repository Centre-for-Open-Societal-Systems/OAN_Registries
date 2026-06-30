import re

with open('g2p_crop_registry/views/crop_registry.xml', 'r') as f:
    lines = f.readlines()

# Find where Biennial Crops starts
biennial_start = -1
for i, line in enumerate(lines):
    if '<group string="Biennial Crops"' in line:
        biennial_start = i
        break

if biennial_start != -1:
    # Find where Biennial Crops ends
    biennial_end = -1
    stack = 0
    for i in range(biennial_start, len(lines)):
        if '<group' in lines[i]:
            stack += lines[i].count('<group')
        if '</group>' in lines[i]:
            stack -= lines[i].count('</group>')
        if stack == 0:
            biennial_end = i
            break
    
    print(f"Biennial group from {biennial_start} to {biennial_end}")
    
    biennial_lines = lines[biennial_start:biennial_end+1]
    
    # Remove it
    del lines[biennial_start:biennial_end+1]
    
    # Find where Perennial Crops ends
    perennial_start = -1
    for i, line in enumerate(lines):
        if '<group string="Perennial Crops"' in line:
            perennial_start = i
            break
            
    if perennial_start != -1:
        perennial_end = -1
        stack = 0
        for i in range(perennial_start, len(lines)):
            if '<group' in lines[i]:
                stack += lines[i].count('<group')
            if '</group>' in lines[i]:
                stack -= lines[i].count('</group>')
            if stack == 0:
                perennial_end = i
                break
                
        print(f"Perennial group from {perennial_start} to {perennial_end}")
        
        # Insert Biennial right after Perennial
        lines = lines[:perennial_end+1] + biennial_lines + lines[perennial_end+1:]
        print("Moved successfully")

# Write back
with open('g2p_crop_registry/views/crop_registry.xml', 'w') as f:
    f.writelines(lines)
