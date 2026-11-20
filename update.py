"""2026 All-Japan University Ekiden: download, parse, validate, idempotent SQLite import."""
import argparse,csv,hashlib,json,re,sqlite3,sys
from pathlib import Path
import fitz,requests
URL='https://www.iuau.jp/ev2026/58meki/58meki_result.pdf'
ROOT=Path(__file__).resolve().parent
STARTS=[195.3,253.2,310.2,367.2,424.3,481.3,538.3,595.3]

def download(url):
    r=requests.get(url,timeout=45,headers={'User-Agent':'EkidenPersonalResearch/0.1 (weekly; contact repository owner)'})
    r.raise_for_status()
    if not r.content.startswith(b'%PDF-'):raise ValueError('Not a PDF')
    return r.content

def extract(pdf):
    doc=fitz.open(stream=pdf,filetype='pdf')
    if len(doc)!=10:raise ValueError(f'Unexpected page count: {len(doc)}')
    words=doc[1].get_text('words')
    teams=sorted([w for w in words if 99<w[0]<155 and w[4].endswith(('大','選抜')) and 130<w[1]<950],key=lambda w:w[1])
    rows=[];errors=[]
    for tw in teams:
        y=tw[1];team=tw[4]
        number=[w for w in words if 90<w[0]<101 and abs(w[1]-y)<3]
        if len(number)!=1:errors.append((team,'bib'));continue
        for i,x in enumerate(STARTS):
            end=STARTS[i+1] if i<7 else 655
            name=' '.join(w[4] for w in sorted([w for w in words if x-1<=w[0]<end-5 and y-10<=w[1]<y-6],key=lambda w:w[0]))
            times=' '.join(w[4] for w in words if x+10<=w[0]<end and y+9<=w[1]<y+14)
            cumulative=' '.join(w[4] for w in words if x+10<=w[0]<end and y+.5<=w[1]<y+5)
            m=re.search(r'(\d+:\d\d(?::\d\d)?)\[(\d+|--)\]',times)
            c=re.search(r'(\d+:\d\d(?::\d\d)?)\[(\d+|--)\]',cumulative)
            if not name or not m or not c:errors.append((team,i+1,'missing'));continue
            rows.append(dict(year=2026,race='全日本大学駅伝',team_number=int(number[0][4]),team=team,leg=i+1,athlete=name,leg_time=m[1],leg_rank=m[2],cumulative_time=c[1],passing_rank=c[2]))
    keys={(r['team_number'],r['leg']) for r in rows}
    if errors or len(teams)!=27 or len(rows)!=216 or len(keys)!=216:
        raise ValueError(f'Validation failed: teams={len(teams)} rows={len(rows)} unique={len(keys)} errors={errors[:5]}')
    return rows

def import_db(rows,db):
    con=sqlite3.connect(db)
    try:
        con.execute('PRAGMA foreign_keys=ON')
        con.executescript('''CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS athletes(id INTEGER PRIMARY KEY,name TEXT NOT NULL,identity_status TEXT NOT NULL DEFAULT 'provisional');
        CREATE TABLE IF NOT EXISTS races(id INTEGER PRIMARY KEY,name TEXT NOT NULL,year INTEGER NOT NULL,source_url TEXT NOT NULL,UNIQUE(name,year));
        CREATE TABLE IF NOT EXISTS performances(id INTEGER PRIMARY KEY,race_id INTEGER NOT NULL REFERENCES races(id),athlete_id INTEGER NOT NULL REFERENCES athletes(id),team_id INTEGER NOT NULL REFERENCES teams(id),team_number INTEGER NOT NULL,leg INTEGER NOT NULL,leg_time TEXT NOT NULL,leg_rank INTEGER,cumulative_time TEXT,passing_rank INTEGER,UNIQUE(race_id,team_number,leg));''')
        con.execute('BEGIN')
        con.execute('INSERT OR IGNORE INTO races(name,year,source_url) VALUES(?,?,?)',('全日本大学駅伝',2026,URL))
        race_id=con.execute('SELECT id FROM races WHERE name=? AND year=?',('全日本大学駅伝',2026)).fetchone()[0]
        for r in rows:
            con.execute('INSERT OR IGNORE INTO teams(name) VALUES(?)',(r['team'],))
            team_id=con.execute('SELECT id FROM teams WHERE name=?',(r['team'],)).fetchone()[0]
            existing=con.execute('SELECT athlete_id FROM performances WHERE race_id=? AND team_number=? AND leg=?',(race_id,r['team_number'],r['leg'])).fetchone()
            if existing:
                athlete_id=existing[0]
                old=con.execute('SELECT name FROM athletes WHERE id=?',(athlete_id,)).fetchone()[0]
                if old!=r['athlete']:raise ValueError(f'Identity conflict: {old} vs {r["athlete"]}')
            else:
                athlete_id=con.execute('INSERT INTO athletes(name) VALUES(?)',(r['athlete'],)).lastrowid
            def rank(v):return int(v) if v!='--' else None
            con.execute('''INSERT INTO performances(race_id,athlete_id,team_id,team_number,leg,leg_time,leg_rank,cumulative_time,passing_rank)
            VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(race_id,team_number,leg) DO UPDATE SET leg_time=excluded.leg_time,leg_rank=excluded.leg_rank,cumulative_time=excluded.cumulative_time,passing_rank=excluded.passing_rank''',
            (race_id,athlete_id,team_id,r['team_number'],r['leg'],r['leg_time'],rank(r['leg_rank']),r['cumulative_time'],rank(r['passing_rank'])))
        con.commit()
        assert con.execute('SELECT count(*) FROM performances').fetchone()[0]==216
        assert con.execute('SELECT count(*) FROM athletes').fetchone()[0]==216
    except:con.rollback();raise
    finally:con.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--pdf',type=Path,help='Offline test PDF; otherwise download official PDF');p.add_argument('--out',type=Path,default=ROOT/'output');a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    content=a.pdf.read_bytes() if a.pdf else download(URL)
    rows=extract(content)
    with (a.out/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    import_db(rows,a.out/'ekiden.sqlite3')
    (a.out/'status.json').write_text(json.dumps({'result':'success','records':len(rows),'teams':27,'sha256':hashlib.sha256(content).hexdigest(),'source_url':URL},ensure_ascii=False,indent=2),encoding='utf-8')
    print('SUCCESS: 27 teams, 216 records, database updated')
if __name__=='__main__':main()
