"""Read-only checks for ekiden CSV source records. No source files are changed."""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = [ROOT / 'results_2025.csv', ROOT / 'results_2026.csv']
REQUIRED = ('year','race','team_number','team','leg','athlete','leg_time','leg_rank','cumulative_time','passing_rank')

def seconds(value):
    parts = str(value).strip().split(':')
    if len(parts) not in (2,3) or not all(p.isdigit() for p in parts):
        raise ValueError('invalid time')
    values = [int(p) for p in parts]
    if any(p >= 60 for p in values[1:]):
        raise ValueError('invalid time component')
    return sum(v * 60 ** i for i,v in enumerate(reversed(values)))

def main():
    issues=[]; groups=defaultdict(list); totals={}; seen=set()
    def issue(level, code, file, line, detail):
        issues.append(dict(level=level,code=code,file=file,line=line,detail=detail))
    for path in FILES:
        if not path.exists():
            issue('error','missing_file',path.name,None,'CSVが存在しません'); continue
        count=0
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if not reader.fieldnames or any(k not in reader.fieldnames for k in REQUIRED):
                issue('error','columns',path.name,1,'必須列がありません'); continue
            for line,row in enumerate(reader,2):
                count+=1
                key=(row['year'],row['race'],row['team_number'],row['leg'])
                if key in seen: issue('error','duplicate',path.name,line,'大会・年・チーム番号・区間が重複')
                seen.add(key)
                athlete=(row['athlete'] or '').strip()
                if not athlete: issue('error','missing_athlete',path.name,line,'氏名が空欄')
                elif ' ' not in athlete and '　' not in athlete: issue('review','name_format',path.name,line,f'氏名の区切りなし。欠落の可能性: {athlete}')
                elif len(athlete.replace(' ','').replace('　','')) <= 2: issue('review','short_name',path.name,line,f'短い氏名: {athlete}')
                try: leg=int(row['leg'])
                except (ValueError,TypeError): leg=0
                if not 1 <= leg <= 8: issue('error','leg_range',path.name,line,'区間が1～8の範囲外')
                try: lap=seconds(row['leg_time'])
                except ValueError: lap=None;issue('error','invalid_leg_time',path.name,line,'区間タイムが不正')
                cumulative=None
                if (row['cumulative_time'] or '').strip():
                    try: cumulative=seconds(row['cumulative_time'])
                    except ValueError: issue('error','invalid_cumulative',path.name,line,'累計タイムが不正')
                groups[key[:3]].append((leg,lap,cumulative,path.name,line,row['team']))
        totals[path.name]=count
        if count != 216: issue('review','unexpected_count',path.name,None,f'{count}件（想定216件）')
    for key,rows in groups.items():
        rows.sort()
        if [r[0] for r in rows] != list(range(1,9)):
            issue('error','incomplete_legs',rows[0][3],None,f'{key}: 区間構成が不正');continue
        running=0
        for leg,lap,cumulative,file,line,team in rows:
            if lap is None: continue
            running+=lap
            if cumulative is not None and running != cumulative:
                issue('error','cumulative_mismatch',file,line,f'{key} {team} {leg}区: 区間合計{running}秒 / CSV累計{cumulative}秒')
        if rows[-1][2] is None: issue('review','missing_final_cumulative',rows[-1][3],rows[-1][4],f'{key}: 最終累計が空欄')
    result={'summary':{'source_rows':totals,'teams_by_race':len(groups),'errors':sum(x['level']=='error' for x in issues),'reviews':sum(x['level']=='review' for x in issues)},'issues':issues,'limitations':['公式PDFとの独立照合は行っていません','氏名の形式チェックは候補抽出であり、誤記の確定判定ではありません','総合順位の正誤は検証対象外です']}
    (ROOT/'validation_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))
    if result['summary']['errors']: raise SystemExit(1)
if __name__=='__main__': main()
