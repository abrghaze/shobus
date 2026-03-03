import json, re, glob

def get_ranges_from_liquid(filepath):
    """Extract range settings from a Liquid section schema, handling comments."""
    ranges = {'section': {}, 'blocks': {}}
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    
    match = re.search(r'\{%[-\s]*schema\s*[-\s]*%\}(.*?)\{%[-\s]*endschema\s*[-\s]*%\}', content, re.DOTALL)
    if not match:
        return ranges
    
    schema_text = match.group(1)
    # Remove // comment lines
    lines = schema_text.split('\n')
    clean_lines = [line for line in lines if not line.strip().startswith('//')]
    clean_text = '\n'.join(clean_lines)
    clean_text = re.sub(r',\s*([}\]])', r'\1', clean_text)
    
    try:
        schema = json.loads(clean_text)
    except:
        return ranges
    
    for s in schema.get('settings', []):
        if s.get('type') == 'range' and 'step' in s:
            ranges['section'][s['id']] = {'min': s['min'], 'max': s['max'], 'step': s['step']}
    
    for block in schema.get('blocks', []):
        btype = block.get('type', '')
        if btype not in ranges['blocks']:
            ranges['blocks'][btype] = {}
        for s in block.get('settings', []):
            if s.get('type') == 'range' and 'step' in s:
                ranges['blocks'][btype][s['id']] = {'min': s['min'], 'max': s['max'], 'step': s['step']}
    
    return ranges

# Build map: section_type -> ranges
section_ranges = {}
for liquid_file in glob.glob('sections/*.liquid'):
    section_type = liquid_file.replace('sections\\', '').replace('.liquid', '')
    section_ranges[section_type] = get_ranges_from_liquid(liquid_file)

# Also load global schema ranges
with open('config/settings_schema.json') as f:
    global_schema = json.load(f)
global_ranges = {}
for section in global_schema:
    for s in section.get('settings', []):
        if s.get('type') == 'range' and 'step' in s:
            global_ranges[s['id']] = {'min': s['min'], 'max': s['max'], 'step': s['step']}

def check_value(val, r):
    """Check if val is valid for range spec r."""
    if not isinstance(val, (int, float)):
        return True
    if val < r['min'] or val > r['max']:
        return False
    if (val - r['min']) % r['step'] != 0:
        return False
    return True

errors_found = 0

# Check config/settings_data.json
with open('config/settings_data.json') as f:
    settings = json.load(f)
for key, val in settings.get('current', {}).items():
    if key in global_ranges and not check_value(val, global_ranges[key]):
        r = global_ranges[key]
        print(f"ERROR config/settings_data.json current.{key}={val} (step={r['step']} range={r['min']}-{r['max']})")
        errors_found += 1

# Check all template JSON files
for json_file in glob.glob('templates/*.json'):
    try:
        with open(json_file) as f:
            template = json.load(f)
    except:
        continue
    
    for section_key, section in template.get('sections', {}).items():
        stype = section.get('type', '')
        if stype not in section_ranges:
            continue
        
        sr = section_ranges[stype]
        
        # Check section-level settings
        for key, val in section.get('settings', {}).items():
            if key in sr['section'] and not check_value(val, sr['section'][key]):
                r = sr['section'][key]
                print(f"ERROR {json_file} {section_key}.{key}={val} (step={r['step']} range={r['min']}-{r['max']})")
                errors_found += 1
        
        # Check block-level settings
        for block_key, block in section.get('blocks', {}).items():
            btype = block.get('type', '')
            if btype in sr['blocks']:
                for key, val in block.get('settings', {}).items():
                    if key in sr['blocks'][btype] and not check_value(val, sr['blocks'][btype][key]):
                        r = sr['blocks'][btype][key]
                        print(f"ERROR {json_file} {block_key}.{key}={val} (step={r['step']} range={r['min']}-{r['max']})")
                        errors_found += 1

# Check section group JSON files
for json_file in glob.glob('sections/*.json'):
    try:
        with open(json_file) as f:
            data = json.load(f)
    except:
        continue
    
    for section_key, section in data.get('sections', {}).items():
        stype = section.get('type', '')
        if stype not in section_ranges:
            continue
        sr = section_ranges[stype]
        for key, val in section.get('settings', {}).items():
            if key in sr['section'] and not check_value(val, sr['section'][key]):
                r = sr['section'][key]
                print(f"ERROR {json_file} {section_key}.{key}={val} (step={r['step']} range={r['min']}-{r['max']})")
                errors_found += 1

if errors_found == 0:
    print("ALL CLEAR - no step-range violations found!")
else:
    print(f"\nFound {errors_found} error(s).")
