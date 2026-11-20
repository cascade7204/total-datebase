"""Build a conservative, reproducible SQLite database from existing ekiden CSVs.
No athlete identities are merged automatically. Run: python migrate.py
"""
import csv, json, sqlite3, collections, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = [ROOT / 'results_2025.csv', ROOT / 'results_2026.csv']
DB = ROOT / 'ekiden_v2.sqlite3'
SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE teams (id INTEGER PRIMARY KEY, canonical_name TEXT NOT NULL UNIQUE, category TEXT NOT NULL DEFAULT '大学');
CREATE TABLE team_names (team_id INTEGER NOT NULL REFERENCES teams(id), name TEXT NOT NULL, valid_from TEXT, valid_to TEXT, UNIQUE(team_id,name,valid_from));
CREATE TABLE athletes (id INTEGER PRIMARY KEY, display_name TEXT NOT NULL, identity_status TEXT NOT NULL DEFAULT 'provisional');
CREATE TABLE races (id INTEGER PRIMARY KEY, name TEXT NOT NULL, year INTEGER NOT NULL, event_date TEXT, source_url TEXT, UNIQUE(name,year));
CREATE TABLE team_race_results (id INTEGER PRIMARY KEY, race_id INTEGER NOT NULL REFERENCES races(id), team_id INTEGER NOT NULL REFERENCES teams(id), team_number INTEGER NOT NULL, overall_rank INTEGER, overall_time TEXT, UNIQUE(race_id,team_number));
CREATE TABLE performances (id INTEGER PRIMARY KEY, race_id INTEGER NOT NULL REFERENCES races(id), team_race_id INTEGER NOT NULL REFERENCES team_race_results(id), athlete_id INTEGER NOT NULL REFERENCES athletes(id), leg INTEGER NOT NULL, leg_time TEXT NOT NULL, leg_rank INTEGER, source_cumulative_time TEXT, source_passing_rank INTEGER, UNIQUE(team_race_id,leg));
CREATE TABLE individual_results (id INTEGER PRIMARY KEY, athlete_id INTEGER NOT NULL REFERENCES athletes(id), event TEXT NOT NULL, result TEXT NOT NULL, achieved_on TEXT, team_id INTEGER REFERENCES teams(id), source_url TEXT);
CREATE TABLE affiliations (id INTEGER PRIMARY KEY, athlete_id INTEGER NOT NULL REFERENCES athletes(id), team_id INTEGER NOT NULL REFERENCES teams(id), start_date TEXT, end_date TEXT, evidence TEXT, UNIQUE(athlete_id,team_id,start_date));
CREATE TABLE review_cases (id INTEGER PRIMARY KEY, subject_type TEXT NOT NULL, left_id INTEGER NOT NULL, right_id INTEGER NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','same','different','hold')), notes TEXT, decided_at TEXT, UNIQUE(subject_type,left_id,right_id), CHECK(left_id < right_id));
CREATE TABLE review_history (id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES review_cases(id), old_status TEXT, new_status TEXT NOT NULL, decided_at TEXT NOT NULL, notes TEXT);
CREATE TABLE ingestion_status (id INTEGER PRIMARY KEY, race_name TEXT NOT NULL, year INTEGER NOT NULL, state TEXT NOT NULL, source_file TEXT, records INTEGER, last_attempt_at TEXT, detail TEXT, UNIQUE(race_name,year));
CREATE TABLE source_records (id INTEGER PRIMARY KEY, performance_id INTEGER NOT NULL UNIQUE REFERENCES performances(id), source_file TEXT NOT NULL, source_row INTEGER NOT NULL, original_json TEXT NOT NULL);
'''
FIELDS = ['year','race','team_number','team','leg','athlete','leg_time','leg_rank','cumulative_time','passing_rank']

def optional_int(v):
    return int(v) if v and v != '--' else None

def seconds(v):
    parts = [int(p) for p in v.split(':')]
    if len(parts) not in (2,3) or any(x >= 60 for x in parts[1:]):
        raise ValueError('Invalid time: ' + v)
    return sum(x * 60 ** i for i,x in enumerate(reversed(parts)))

def format_seconds(v):
    h,rem=divmod(v,3600)
    m,s=divmod(rem,60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'

def load():
    result=[]
    for path in SOURCES:
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if reader.fieldnames != FIELDS:
                raise ValueError(f'Unexpected columns: {path}: {reader.fieldnames}')
            for line,row in enumerate(reader,2):
                if any(row[k] is None or not row[k].strip() for k in ('year','race','team_number','team','leg','athlete','leg_time')):
                    raise ValueError(f'Missing required value {path}:{line}')
                if int(row['leg']) not in range(1,9):
                    raise ValueError(f'Invalid leg {path}:{line}')
                seconds(row['leg_time'])
                result.append((path.name,line,row))
    keys=[(r['year'],r['race'],r['team_number'],r['leg']) for _,_,r in result]
    if len(keys)!=len(set(keys)):
        raise ValueError('Duplicate race/team_number/leg')
    return result

def build():
    records=load()
    if DB.exists(): DB.unlink()
    con=sqlite3.connect(DB)
    con.executescript(SCHEMA)
    team_ids={}; race_ids={}; names=collections.defaultdict(list); checks=[]
    try:
        for file,line,r in records:
            team=r['team'].strip(); race=(r['race'],int(r['year']))
            if team not in team_ids:
                team_ids[team]=con.execute('INSERT INTO teams(canonical_name) VALUES(?)',(team,)).lastrowid
                con.execute('INSERT INTO team_names(team_id,name) VALUES(?,?)',(team_ids[team],team))
            if race not in race_ids:
                race_ids[race]=con.execute('INSERT INTO races(name,year) VALUES(?,?)',race).lastrowid
            rid=race_ids[race]; tid=team_ids[team]; bib=int(r['team_number'])
            con.execute('INSERT OR IGNORE INTO team_race_results(race_id,team_id,team_number) VALUES(?,?,?)',(rid,tid,bib))
            tr_id=con.execute('SELECT id FROM team_race_results WHERE race_id=? AND team_number=?',(rid,bib)).fetchone()[0]
            actual_team=con.execute('SELECT team_id FROM team_race_results WHERE id=?',(tr_id,)).fetchone()[0]
            if actual_team!=tid: raise ValueError(f'Bib reused for different team: {race} {bib}')
            aid=con.execute('INSERT INTO athletes(display_name) VALUES(?)',(r['athlete'].strip(),)).lastrowid
            namekey=re.sub(r'\s+','',r['athlete'])
            names[namekey].append((aid,r['athlete'],team,int(r['year'])))
            pid=con.execute('INSERT INTO performances(race_id,team_race_id,athlete_id,leg,leg_time,leg_rank,source_cumulative_time,source_passing_rank) VALUES(?,?,?,?,?,?,?,?)',
                (rid,tr_id,aid,int(r['leg']),r['leg_time'],optional_int(r['leg_rank']),r['cumulative_time'],optional_int(r['passing_rank']))).lastrowid
            con.execute('INSERT INTO source_records(performance_id,source_file,source_row,original_json) VALUES(?,?,?,?)',(pid,file,line,json.dumps(r,ensure_ascii=False)))
            con.execute('INSERT OR IGNORE INTO affiliations(athlete_id,team_id,evidence) VALUES(?,?,?)',(aid,tid,f'{r["year"]} {r["race"]} 区間記録'))
        for (race_name,year),rid in race_ids.items():
            tr=con.execute('SELECT id FROM team_race_results WHERE race_id=?',(rid,)).fetchall()
            for (trid,) in tr:
                rows=con.execute('SELECT leg,leg_time,source_cumulative_time FROM performances WHERE team_race_id=? ORDER BY leg',(trid,)).fetchall()
                if len(rows)!=8 or [x[0] for x in rows]!=list(range(1,9)):
                    checks.append({'type':'incomplete_team','team_race_id':trid,'legs':len(rows)})
                    continue
                total=sum(seconds(x[1]) for x in rows)
                official=rows[-1][2]
                if official and seconds(official)!=total:
                    checks.append({'type':'cumulative_mismatch','team_race_id':trid,'leg_sum':format_seconds(total),'source_cumulative':official})
                # Source CSV has no separate official overall result: cumulative last leg is only provisional evidence.
                con.execute('UPDATE team_race_results SET overall_time=? WHERE id=?',(official or format_seconds(total),trid))
            count=con.execute('SELECT count(*) FROM performances WHERE race_id=?',(rid,)).fetchone()[0]
            source='results_2025.csv' if year==2025 else 'results_2026.csv'
            con.execute('INSERT INTO ingestion_status(race_name,year,state,source_file,records,detail) VALUES(?,?,?,?,?,?)',
                        (race_name,year,'imported_unverified',source,count,'CSV移行済。公式総合順位・総合記録の独立照合は未実施'))
        for key, group in sorted(names.items()):
            if len(group)<2: continue
            for i in range(len(group)):
                for j in range(i+1,len(group)):
                    a,b=group[i],group[j]
                    con.execute('INSERT INTO review_cases(subject_type,left_id,right_id,reason) VALUES(?,?,?,?)',
                                ('athlete',min(a[0],b[0]),max(a[0],b[0]),f'氏名一致（空白を除外）: {a[1]} / {b[1]}。所属・年度: {a[2]} {a[3]} / {b[2]} {b[3]}'))
        con.commit()
        counts={table:con.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in ('teams','athletes','races','team_race_results','performances','individual_results','affiliations','review_cases','ingestion_status')}
        report={'counts':counts,'by_year':dict(con.execute('SELECT year,count(*) FROM races JOIN performances ON performances.race_id=races.id GROUP BY year')),'validation_issues':checks,'notes':['選手はレコード単位で仮登録。同一人物の自動統合は行っていません。','チームは名称が完全一致するものだけ統合。改称・略称の同一判定は未実施。','総合順位は未取得。総合タイムは最終区間の通過タイムを暫定転記し、公式総合記録との照合が必要。','所属期間・学年・年齢・生年月日は推測せず空欄。','元CSVの通過情報は出典保全用に保持し、画面機能の対象にはしません。']}
        (ROOT/'migration_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    finally: con.close()
if __name__=='__main__':build()
