import json
from pathlib import Path
from collections import defaultdict

PUBLIC = Path(__file__).parent.parent / 'public'
MANIFESTS = PUBLIC / 'manifest'

CONTRIB_INDEX = defaultdict(list)
READER_INDEX = defaultdict(list)

for mf_file in MANIFESTS.glob('*.json'):
    if mf_file.name == 'errors.json':
        mf_file.rename(PUBLIC / 'errors.json')
        continue

    with mf_file.open() as f:
        data = json.load(f)

    print(data['name'], data['package_metadata']['version'])
    for contrib_type, contribs in data.get('contributions', {}).items():
        if not contribs:
            continue
        CONTRIB_INDEX[contrib_type].append(data['name'])
        if contrib_type == 'readers':
            for contrib in contribs:
                for pattern in contrib['filename_patterns']:
                    READER_INDEX[pattern].append(data['name'])


(PUBLIC / 'contributions.json').write_text(json.dumps(CONTRIB_INDEX))
(PUBLIC / 'readers.json').write_text(json.dumps(READER_INDEX))
