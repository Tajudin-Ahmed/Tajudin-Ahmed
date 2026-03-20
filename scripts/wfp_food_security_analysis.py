#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

FCS_WEIGHTS = {
    'main_staples': 2,
    'pulses': 3,
    'vegetables': 1,
    'fruit': 1,
    'meat_fish_eggs': 4,
    'milk': 4,
    'sugar': 0.5,
    'oil': 0.5,
}

RCSI_WEIGHTS = {
    'less_preferred_food': 1,
    'borrow_food': 2,
    'limit_portions': 1,
    'restrict_adults': 3,
    'reduce_meals': 1,
}

ALIASES = {
    'hh_id': ['hh_id','household_id','uuid','respondent_id'],
    'gender_head': ['gender_head','sex_head','hh_head_gender','gender_hh_head','sex_of_household_head'],
    'location': ['location','admin1','admin2','district','county','state','village','settlement'],
    'food_exp_share': ['food_expenditure_share','fes','food_share','share_food_expenditure'],
    'main_staples': ['cereals_tubers','main_staples','staples','fcs_staples'],
    'pulses': ['pulses','beans','fcs_pulses'],
    'vegetables': ['vegetables','fcs_vegetables'],
    'fruit': ['fruit','fruits','fcs_fruit'],
    'meat_fish_eggs': ['meat_fish_eggs','meat','fish','eggs','fcs_protein'],
    'milk': ['milk','dairy','fcs_milk'],
    'sugar': ['sugar','fcs_sugar'],
    'oil': ['oil','fats','oil_fat','fcs_oil'],
    'less_preferred_food': ['rcsi_less_preferred_food','less_preferred_food','coping_less_preferred_food'],
    'borrow_food': ['rcsi_borrow_food','borrow_food','borrowed_food'],
    'limit_portions': ['rcsi_limit_portions','limit_portions','smaller_portions'],
    'restrict_adults': ['rcsi_restrict_adults','restrict_adults','adult_restriction'],
    'reduce_meals': ['rcsi_reduce_meals','reduce_meals','meal_reduction'],
    'lcs_stress': ['lcs_stress','stress_coping','stress_strategy'],
    'lcs_crisis': ['lcs_crisis','crisis_coping','crisis_strategy'],
    'lcs_emergency': ['lcs_emergency','emergency_coping','emergency_strategy'],
}


def normalize(name: str) -> str:
    return ''.join(c.lower() if c.isalnum() else '_' for c in name).strip('_')


def find_col(fieldnames, aliases):
    normalized = {normalize(f): f for f in fieldnames}
    for alias in aliases:
        if normalize(alias) in normalized:
            return normalized[normalize(alias)]
    return None


def to_number(value):
    if value is None:
        return None
    text = str(value).strip()
    if text == '':
        return None
    try:
        num = float(text)
        return int(num) if num.is_integer() else num
    except ValueError:
        lowered = text.lower()
        if lowered in {'yes','true','y'}:
            return 1
        if lowered in {'no','false','n'}:
            return 0
        return None


def cap7(v):
    n = to_number(v)
    if n is None:
        return None
    return max(0, min(7, float(n)))


def summarize_missing(rows, fieldnames):
    out = {}
    total = len(rows)
    for f in fieldnames:
        missing = sum(1 for r in rows if str(r.get(f, '')).strip() == '')
        out[f] = {'missing_count': missing, 'missing_pct': round((missing/total)*100, 2) if total else 0}
    return out


def get_record(row, field_map):
    rec = {}
    for key, aliases in ALIASES.items():
        col = field_map.get(key)
        rec[key] = row.get(col) if col else None
    return rec


def classify_fcs(fcs):
    if fcs is None:
        return None, None
    if fcs <= 21:
        return 'poor', 4
    if fcs <= 35:
        return 'borderline', 3
    return 'acceptable', 1


def classify_rcsi(rcsi):
    if rcsi is None:
        return None, None
    if rcsi > 18:
        return 'high', 4
    if rcsi >= 4:
        return 'medium', 3
    return 'low', 1


def classify_lcs(stress, crisis, emergency):
    vals = [to_number(stress), to_number(crisis), to_number(emergency)]
    if vals[2] == 1:
        return 'emergency', 4
    if vals[1] == 1:
        return 'crisis', 3
    if vals[0] == 1:
        return 'stress', 2
    if vals[0] == 0 and vals[1] == 0 and vals[2] == 0:
        return 'none', 1
    return None, None


def classify_fes(fes):
    n = to_number(fes)
    if n is None:
        return None, None
    if n > 75:
        return 'very_high', 4
    if n > 65:
        return 'high', 3
    if n >= 50:
        return 'medium', 2
    return 'low', 1


def cari_category(current_status, coping_capacity):
    if current_status is None or coping_capacity is None:
        return 'Unclassified'
    score = max(current_status, coping_capacity)
    return {
        1: 'Food Secure',
        2: 'Marginally Food Secure',
        3: 'Moderately Insecure',
        4: 'Severely Insecure',
    }[score]


def simple_bar_svg(counter, title, outpath):
    total = sum(counter.values()) or 1
    cats = ['Food Secure','Marginally Food Secure','Moderately Insecure','Severely Insecure','Unclassified']
    values = [counter.get(c, 0) for c in cats]
    pcts = [v * 100 / total for v in values]
    width, height = 820, 420
    left, bottom = 70, 60
    chart_w, chart_h = 700, 280
    bar_w = chart_w / max(len(cats), 1) * 0.6
    gap = chart_w / max(len(cats), 1)
    colors = ['#2e7d32','#9ccc65','#f9a825','#c62828','#757575']
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<style>text{font-family:Arial,sans-serif;font-size:12px} .title{font-size:18px;font-weight:bold}</style>',
             f'<text x="{width/2}" y="30" text-anchor="middle" class="title">{title}</text>',
             f'<line x1="{left}" y1="{bottom}" x2="{left}" y2="{bottom+chart_h}" stroke="black"/>',
             f'<line x1="{left}" y1="{bottom+chart_h}" x2="{left+chart_w}" y2="{bottom+chart_h}" stroke="black"/>']
    for i in range(0, 101, 20):
        y = bottom + chart_h - (i/100)*chart_h
        lines.append(f'<line x1="{left-5}" y1="{y}" x2="{left+chart_w}" y2="{y}" stroke="#ddd"/>')
        lines.append(f'<text x="{left-10}" y="{y+4}" text-anchor="end">{i}%</text>')
    for idx, (cat, pct, color) in enumerate(zip(cats, pcts, colors)):
        x = left + idx * gap + (gap - bar_w) / 2
        h = (pct/100) * chart_h
        y = bottom + chart_h - h
        lines.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{color}"/>')
        lines.append(f'<text x="{x + bar_w/2}" y="{y-8}" text-anchor="middle">{pct:.1f}%</text>')
        lines.append(f'<text x="{x + bar_w/2}" y="{bottom + chart_h + 20}" text-anchor="middle">{cat}</text>')
    lines.append('</svg>')
    outpath.write_text('\n'.join(lines), encoding='utf-8')


def analyze(csv_path: Path, outdir: Path):
    with csv_path.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f'No data rows found in {csv_path}')
    fieldnames = rows[0].keys()
    field_map = {k: find_col(fieldnames, v) for k, v in ALIASES.items()}
    results = []
    for row in rows:
        rec = get_record(row, field_map)
        fcs = None
        if all(field_map.get(k) for k in FCS_WEIGHTS):
            parts = []
            for key, wt in FCS_WEIGHTS.items():
                val = cap7(rec[key])
                parts.append(None if val is None else val * wt)
            if all(v is not None for v in parts):
                fcs = round(sum(parts), 2)
        rcsi = None
        if all(field_map.get(k) for k in RCSI_WEIGHTS):
            parts = []
            for key, wt in RCSI_WEIGHTS.items():
                val = to_number(rec[key])
                parts.append(None if val is None else float(val) * wt)
            if all(v is not None for v in parts):
                rcsi = round(sum(parts), 2)
        lcs_label, lcs_score = classify_lcs(rec['lcs_stress'], rec['lcs_crisis'], rec['lcs_emergency'])
        fes_label, fes_score = classify_fes(rec['food_exp_share'])
        fcs_label, fcs_score = classify_fcs(fcs)
        rcsi_label, rcsi_score = classify_rcsi(rcsi)
        current_status = None if fcs_score is None and rcsi_score is None else max(v for v in [fcs_score, rcsi_score] if v is not None)
        coping_capacity = None if lcs_score is None and fes_score is None else max(v for v in [lcs_score, fes_score] if v is not None)
        cari = cari_category(current_status, coping_capacity)
        results.append({
            'hh_id': rec['hh_id'],
            'gender_head': rec['gender_head'] or 'Unknown',
            'location': rec['location'] or 'Unknown',
            'fcs': fcs,
            'fcs_category': fcs_label,
            'rcsi': rcsi,
            'rcsi_category': rcsi_label,
            'lcs_category': lcs_label,
            'food_expenditure_share_category': fes_label,
            'cari_category': cari,
        })
    cat_counter = Counter(r['cari_category'] for r in results)
    disagg = {}
    for group in ['gender_head', 'location']:
        bucket = defaultdict(Counter)
        for r in results:
            bucket[r[group]][r['cari_category']] += 1
        disagg[group] = {k: dict(v) for k, v in bucket.items()}
    summary = {
        'source_file': str(csv_path),
        'row_count': len(rows),
        'columns': list(fieldnames),
        'column_mapping': field_map,
        'missingness': summarize_missing(rows, fieldnames),
        'inconsistencies': {
            'fcs_out_of_range_rows': sum(1 for r in results if r['fcs'] is not None and not (0 <= r['fcs'] <= 112)),
            'rcsi_negative_rows': sum(1 for r in results if r['rcsi'] is not None and r['rcsi'] < 0),
            'unknown_gender_rows': sum(1 for r in results if r['gender_head'] == 'Unknown'),
            'unknown_location_rows': sum(1 for r in results if r['location'] == 'Unknown'),
        },
        'indicator_coverage': {
            'fcs_complete_pct': round(sum(r['fcs'] is not None for r in results) * 100 / len(results), 2),
            'rcsi_complete_pct': round(sum(r['rcsi'] is not None for r in results) * 100 / len(results), 2),
            'lcs_complete_pct': round(sum(r['lcs_category'] is not None for r in results) * 100 / len(results), 2),
        },
        'indicator_summary': {
            'fcs_mean': round(mean([r['fcs'] for r in results if r['fcs'] is not None]), 2) if any(r['fcs'] is not None for r in results) else None,
            'rcsi_mean': round(mean([r['rcsi'] for r in results if r['rcsi'] is not None]), 2) if any(r['rcsi'] is not None for r in results) else None,
            'cari_counts': dict(cat_counter),
            'cari_pct': {k: round(v * 100 / len(results), 2) for k, v in cat_counter.items()},
        },
        'disaggregation': disagg,
        'methodology_note': 'CARI classification uses the worse of current status (FCS and rCSI) and coping capacity (LCS and food expenditure share). Thresholds should be validated against the survey questionnaire before operational use.'
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / 'analysis_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    with (outdir / 'household_results.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    simple_bar_svg(cat_counter, 'CARI Food Security Classification', outdir / 'cari_categories.svg')
    return summary


def main():
    parser = argparse.ArgumentParser(description='Analyze WFP food security outcome monitoring CSV data.')
    parser.add_argument('input', nargs='?', help='Path to a CSV file. If omitted, the script searches the repo for CSV files.')
    parser.add_argument('--outdir', default='outputs/wfp_analysis', help='Directory for generated outputs.')
    args = parser.parse_args()
    csv_path = Path(args.input) if args.input else None
    if csv_path is None:
        candidates = [p for p in Path('.').glob('**/*.csv') if '.git/' not in str(p) and 'outputs/' not in str(p)]
        candidates = [p for p in candidates if p.name != 'ubuntu.csv' and p.name != 'debian.csv']
        if not candidates:
            raise SystemExit('No survey CSV file was found in the repository. Add the uploaded WFP dataset and rerun the script.')
        csv_path = candidates[0]
    summary = analyze(csv_path, Path(args.outdir))
    print(json.dumps({
        'source_file': summary['source_file'],
        'row_count': summary['row_count'],
        'cari_pct': summary['indicator_summary']['cari_pct'],
        'outputs': [str(Path(args.outdir) / x) for x in ['analysis_summary.json','household_results.csv','cari_categories.svg']]
    }, indent=2))

if __name__ == '__main__':
    main()
