"""Export public read-only JSON from the stage-1 SQLite DB.
Usage (repository root): python export_public.py
"""
import json, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/'ekiden_v2.sqlite3'
OUT=ROOT/'public_data'

def main():
    if not DB.is_file(): raise SystemExit('ekiden_v2.sqlite3 が見つかりません。リポジトリ直下で実行してください。')
    OUT.mkdir(exist_ok=True)
    con=sqlite3.connect(f'file:{DB}?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    try:
        required={'teams','athletes','races','performances','team_race_results'}
        present={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required <= present: raise ValueError('移行用データベースのテーブルが不足しています')
        athletes=[dict(r) for r in con.execute('SELECT id,display_name AS name,identity_status FROM athletes ORDER BY id')]
        teams=[dict(r) for r in con.execute('SELECT id,canonical_name AS name,category FROM teams ORDER BY id')]
        races=[dict(r) for r in con.execute('SELECT id,name,year,event_date,source_url FROM races ORDER BY year DESC,id')]
        performances=[dict(r) for r in con.execute('''
            SELECT p.id,p.athlete_id,p.leg,p.leg_time,p.leg_rank,
                   tr.team_id,tr.team_number,tr.id AS team_race_id,
                   r.id AS race_id,r.year,r.name AS race
            FROM performances p JOIN team_race_results tr ON tr.id=p.team_race_id
            JOIN races r ON r.id=p.race_id
            ORDER BY r.year DESC,tr.team_number,p.leg''')]
        team_results=[dict(r) for r in con.execute('''
            SELECT tr.id,tr.race_id,tr.team_id,tr.team_number,tr.overall_time,tr.overall_rank,
                   r.name AS race,r.year FROM team_race_results tr
            JOIN races r ON r.id=tr.race_id ORDER BY r.year DESC,tr.team_number''')]
        if len(performances)!=432: raise ValueError(f'想定外の区間記録数: {len(performances)}')
        for name, data in [('athletes',athletes),('teams',teams),('races',races),('performances',performances),('team_results',team_results)]:
            (OUT/f'{name}.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        print(f'公開用JSON生成完了: 選手{len(athletes)}件 / チーム{len(teams)}件 / 大会{len(races)}件 / 区間記録{len(performances)}件 / チーム大会記録{len(team_results)}件')
    finally: con.close()
if __name__=='__main__':main()
