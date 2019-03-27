import csv
import glob
import json
import re
import sys
import os

FIELDS = {
    "OBJ": "objects",
    "PER": "persons",
    "PLACE": "locations",
    "DATE": "timespans",
    "MISC": "keyterms"
}

PAGE_OFFSET = 41

def read_files(pattern):
    rows = []
    for file_name in glob.glob(pattern):
        with open(file_name) as file:
            reader = csv.reader(file, delimiter='\t')
            for row in reader:
                file_info = parse_file_name(os.path.basename(file_name))
                if file_info:
                    file_info.extend(row)
                    rows.append(file_info)
    return rows

def parse_file_name(file_name):
    match = re.match("(\d+[_\.][^_]+)_page(\d{3})\.[a-z]{3}", file_name)
    if match:
        return [match.group(1), match.group(2)]
    else:
        print(f"file name not parsable: {file_name}", file=sys.stderr)
        return False

def is_row_mappable(row):
    return len(row) > 9 and get_type(row)

def get_type(row):
    tag = get_type_tag(row)
    return get_type_for_tag(tag)

def get_type_tag(row):
    if len(row) > 10:
        return row[9]
    else:
        return row[8]

def get_type_for_tag(tag):
    if tag == "_" or tag == "*" or tag == '':
        return False
    for key in FIELDS:
        if tag.startswith(key):
            return FIELDS[key]
    print(f"tag '{tag}' is not mapped", file=sys.stderr)
    return False

def get_lemma(row):
    return row[6] if row[6] != '<unknown>' else row[4]

def map_row(row):
    return {
        "id": f"{row[0]}_{row[1]}_{row[2]}",
        "terms": { row[4] },
        "lemma": get_lemma(row),
        "pages": { int(row[1]) - PAGE_OFFSET },
        "type": get_type(row),
        "count": 1,
        "references": set()
    }

def merge_row(object, row):
    object['terms'] = { list(object['terms'])[0] + " " + row[4] }
    object['lemma'] += " " + get_lemma(row)

def create_lemma_dict(objects):
    dict = {}
    for o in objects:
        if o['lemma'] in dict:
            dict[o['lemma']]['count'] += 1
            dict[o['lemma']]['pages'].update(o['pages'])
            dict[o['lemma']]['terms'].update(o['terms'])
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

def map_rows(rows):
    objects = []
    last_tag = ""
    for row in rows:
        if is_row_mappable(row):
            if get_type_tag(row) != last_tag:
                objects.append(map_row(row))
            else:
                merge_row(objects[-1], row)
            last_tag = get_type_tag(row)
        else:
            last_tag = ""
    return objects

def enrich_items(items, csv_file, enrich):
    rows = parse_csv(csv_file)
    for row in rows:
        file_info = parse_file_name(row[3])
        page = int(file_info[1]) - PAGE_OFFSET
        term = row[1]
        item = find_item_by_term_and_page(items, term, page)
        if item:
            enrich(item, row)

def enrich_location(location, row):
    if row[7] != '':
        location['references'].add(create_reference("iDAI.gazetteer", row[7], "https://gazetteer.dainst.org/place/"))
    if row[8] != '':
        location['references'].add(create_reference("GND", row[8], "http://d-nb.info/gnd/"))

def enrich_object(object, row):
    if row[8] != '':
        object['references'].add(create_reference("iDAI.objects", row[8], "https://arachne.dainst.org/entity/"))
    if row[11] != '':
        object['references'].add(Reference({ "url": row[11] }))

def enrich_person(person, row):
    if row[6] != '':
        person['references'].add(create_reference("GND", row[6], "http://d-nb.info/gnd/"))
    if row[7] != '':
        person['references'].add(create_reference("viaf", row[7], "http://viaf.org/viaf/"))

class Reference(dict):
    def __hash__(self):
        return hash(self['url'])

def create_reference(type, id, prefix):
    return Reference({
        "id": id,
        "url": prefix + id,
        "type": type
    })

def parse_csv(file_name):
    with open(file_name) as file:
        return list(csv.reader(file, delimiter=';'))[1:] # skip header

def find_item_by_term_and_page(items, term, page):
    for item in items:
        if term in item['terms'] and page in item['pages']:
            return item
    print(f"No match for term '{term}' on page {page}", file=sys.stderr)

def custom_json_serializer(obj):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError

rows = read_files("annotations/*.tsv")
objects = map_rows(rows)
objects = collect_objects(objects)
enrich_items(objects['locations']['items'], "annotations/Orte_A-II-BraE-GerE-081.csv", enrich_location)
enrich_items(objects['objects']['items'], "annotations/Objekte_A-II-BraE-GerE-081.csv", enrich_object)
enrich_items(objects['persons']['items'], "annotations/Personen_A-II-BraE-GerE-081.csv", enrich_person)

print(json.dumps(objects, indent=4, ensure_ascii=False, default=custom_json_serializer))
