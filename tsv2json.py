import csv
import glob
import json
import re

FIELDS = {
    "OBJ": "objects",
    "PER": "persons",
    "PLACE": "locations",
    "DATE": "timespans",
    "MISC": "keyterms"
}

def read_files(pattern):
    rows = []
    for file_name in glob.glob(pattern):
        with open(file_name) as file:
            reader = csv.reader(file, delimiter='\t')
            for row in reader:
                file_info = parse_file_name(file_name)
                if file_info:
                    file_info.extend(row)
                    rows.append(file_info)
    return rows

def parse_file_name(file_name):
    match = re.match("annotations/([^_]+)_page(\d{3})\.tsv", file_name)
    if match:
        return [match.group(1), match.group(2)]
    else:
        print(f"file name not parsable: {file_name}")
        return False

def is_row_mappable(row):
    return len(row) > 9 and get_type_for_tag(row[8])

def get_type_for_tag(tag):
    if tag == "_" or tag == "*":
        return False
    for key in FIELDS:
        if tag.startswith(key):
            return FIELDS[key]
    print(f"tag '{tag}' is not mapped")
    return False

def get_lemma(row):
    return row[6] if row[6] != '<unknown>' else row[4]

def map_row(row):
    return {
        "id": f"{row[0]}_{row[1]}_{row[2]}",
        "terms": [row[4]],
        "lemma": get_lemma(row),
        "pages": [int(row[1])],
        "type": get_type_for_tag(row[8]),
        "count": 1
    }

def merge_row(object, row):
    object['terms'][0] += " " + row[4]
    object['lemma'] += " " + get_lemma(row)

def create_lemma_dict(objects):
    dict = {}
    for o in objects:
        if o['lemma'] in dict:
            dict[o['lemma']]['count'] += 1
            if o['pages'][0] not in dict[o['lemma']]['pages']:
                dict[o['lemma']]['pages'].append(o['pages'][0])
            if o['terms'][0] not in dict[o['lemma']]['terms']:
                dict[o['lemma']]['terms'].append(o['terms'][0])
        else:
            dict[o['lemma']] = o
    return dict

def collect_objects(objects):
    result = {
        "objects": { "items": [] },
        "persons": { "items": [] },
        "timespans": { "items": [] },
        "locations": { "items": [] },
        "keyterms": { "items": [] }
    }
    lemma_dict = create_lemma_dict(objects)
    for o in lemma_dict.values():
        type = o.pop('type')
        result[type]['items'].append(o)
    return result

objects = []
rows = read_files("annotations/*.tsv")
last_tag = ""
for row in rows:
    if is_row_mappable(row):
        if row[8] != last_tag:
            objects.append(map_row(row))
        else:
            merge_row(objects[-1], row)
        last_tag = row[8]
    else:
        last_tag = ""

print(json.dumps(collect_objects(objects), indent=4, ensure_ascii=False))
