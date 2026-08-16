#!/usr/bin/env python3
"""Production-ready audit for the normalized FPL processed dataset.

Reads data/processed/<season>/, validates schemas, counts, duplicates,
referential integrity, missingness, ranges and basic FPL business rules.
Uses only the Python standard library and never modifies the dataset.
"""
from __future__ import annotations
import argparse, csv, json, logging, re, statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
LOG = logging.getLogger("inspect_processed_data")
SEASON_RE = re.compile(r"^\d{4}-\d{2}$")
FILES = ["players.csv","teams.csv","gameweeks.csv","fixtures.csv","player_gameweek.csv","player_season_history.csv","dataset_manifest.json"]
KEYS = {
    "players.csv": ("player_id",),
    "teams.csv": ("team_id",),
    "gameweeks.csv": ("gameweek",),
    "fixtures.csv": ("fixture_id",),
    "player_gameweek.csv": ("player_id","gameweek","fixture_id"),
    "player_season_history.csv": ("player_id","season"),
}
FALLBACK_SCHEMAS = {
"players.csv": "player_id,code,first_name,second_name,web_name,known_name,team_id,team_code,position_id,position_name,now_cost,now_cost_m,cost_change_event,cost_change_event_fall,cost_change_start,cost_change_start_fall,price_change_percent,total_points,points_per_game,form,event_points,ep_next,ep_this,selected_by_percent,transfers_in,transfers_in_event,transfers_out,transfers_out_event,value_form,value_season,minutes,starts,goals_scored,assists,clean_sheets,goals_conceded,own_goals,penalties_saved,penalties_missed,yellow_cards,red_cards,saves,bonus,bps,influence,creativity,threat,ict_index,clearances_blocks_interceptions,recoveries,tackles,defensive_contribution,expected_goals,expected_assists,expected_goal_involvements,expected_goals_conceded,expected_goals_per_90,expected_assists_per_90,expected_goal_involvements_per_90,expected_goals_conceded_per_90,saves_per_90,goals_conceded_per_90,starts_per_90,clean_sheets_per_90,defensive_contribution_per_90,chance_of_playing_next_round,chance_of_playing_this_round,status,removed,can_select,can_transact,news,news_added,team_join_date,birth_date,squad_number,selected_rank,selected_rank_type,form_rank,form_rank_type,points_per_game_rank,points_per_game_rank_type,influence_rank,influence_rank_type,creativity_rank,creativity_rank_type,threat_rank,threat_rank_type,ict_index_rank,ict_index_rank_type,now_cost_rank,now_cost_rank_type".split(","),
"teams.csv": "team_id,code,name,short_name,strength,strength_overall_home,strength_overall_away,strength_attack_home,strength_attack_away,strength_defence_home,strength_defence_away,position,played,win,draw,loss,points,form,team_division,unavailable,pulse_id".split(","),
"gameweeks.csv": "gameweek,name,deadline_time,deadline_time_epoch,release_time,release_time_epoch,average_entry_score,finished,data_checked,highest_scoring_entry,highest_score,is_previous,is_current,is_next,cup_leagues_created,h2h_ko_matches_created,ranked_count,transfers_made,most_selected,most_transferred_in,top_element,top_element_info,chip_plays,most_vice_captained,most_captained".split(","),
"fixtures.csv": "fixture_id,code,gameweek,event_name,team_h,team_a,team_h_score,team_a_score,team_h_difficulty,team_a_difficulty,finished,finished_provisional,started,minutes,provisional_start_time,kickoff_time,pulse_id".split(","),
"player_gameweek.csv": "player_id,season,gameweek,fixture_id,opponent_team,was_home,kickoff_time,minutes,total_points,goals_scored,assists,clean_sheets,goals_conceded,own_goals,penalties_saved,penalties_missed,yellow_cards,red_cards,saves,bonus,bps,influence,creativity,threat,ict_index,clearances_blocks_interceptions,recoveries,tackles,defensive_contribution,starts,expected_goals,expected_assists,expected_goal_involvements,expected_goals_conceded".split(","),
"player_season_history.csv": "player_id,season,element_code,start_cost,end_cost,total_points,minutes,goals_scored,assists,clean_sheets,goals_conceded,own_goals,penalties_saved,penalties_missed,yellow_cards,red_cards,saves,bonus,bps,influence,creativity,threat,ict_index,clearances_blocks_interceptions,recoveries,tackles,defensive_contribution,starts,expected_goals,expected_assists,expected_goal_involvements,expected_goals_conceded".split(","),
}
POSITION_NAMES={1:"Goalkeeper",2:"Defender",3:"Midfielder",4:"Forward"}


def args():
    p=argparse.ArgumentParser(description="Audit normalized FPL processed data.")
    p.add_argument("--season",required=True,help="Season, e.g. 2026-27")
    p.add_argument("--project-root",default=None)
    p.add_argument("--input-dir",default=None)
    p.add_argument("--missingness-warning",type=float,default=20.0)
    p.add_argument("--max-examples",type=int,default=20)
    p.add_argument("--strict",action="store_true",help="Warnings cause failure")
    p.add_argument("--quiet",action="store_true")
    p.add_argument("--verbose",action="store_true")
    return p.parse_args()


def configure(a):
    logging.basicConfig(level=logging.DEBUG if a.verbose else (logging.WARNING if a.quiet else logging.INFO),format="[%(levelname)-8s] %(message)s")


def read_csv(path):
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f)
        if not r.fieldnames: raise RuntimeError("Missing CSV header")
        rows=[]; errors=[]
        for n,row in enumerate(r,2):
            if None in row: errors.append(f"line {n}: extra fields")
            rows.append({str(k):("" if v is None else v) for k,v in row.items() if k is not None})
        return list(r.fieldnames),rows,errors


def number(v):
    if not v or not v.strip(): return None
    try: return int(v) if re.fullmatch(r"[-+]?\d+",v.strip()) else float(v)
    except ValueError: return None


def load_schemas(manifest_path):
    warnings=[]
    if not manifest_path.exists():
        return FALLBACK_SCHEMAS.copy(),["dataset_manifest.json missing; fallback schemas used."]
    try: m=json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e: return FALLBACK_SCHEMAS.copy(),[f"Cannot parse dataset_manifest.json: {e}"]
    out={}
    for name in FALLBACK_SCHEMAS:
        cols=((m.get("files") or {}).get(name) or {}).get("columns")
        out[name]=cols if isinstance(cols,list) else FALLBACK_SCHEMAS[name]
    return out,warnings


def profile(fields,rows,threshold):
    result={}
    for c in fields:
        vals=[r.get(c,"") for r in rows]; non=[v for v in vals if v.strip()]
        miss=len(vals)-len(non); pct=100*miss/len(vals) if vals else 0
        nums=[float(number(v)) for v in non if number(v) is not None]
        d={"rows":len(vals),"missing":miss,"non_missing":len(non),"missing_percent":round(pct,3)}
        if nums: d["numeric"]={"min":min(nums),"max":max(nums),"mean":round(statistics.fmean(nums),6),"median":round(statistics.median(nums),6)}
        if pct>=threshold and vals: d["missingness_warning"]=True
        result[c]=d
    return result


def duplicates(rows,key,limit):
    c=Counter(tuple(r.get(k,"").strip() for k in key) for r in rows); d=[(k,n) for k,n in c.items() if n>1]; d.sort(key=lambda x:(-x[1],x[0]))
    return len(d),[{"key":dict(zip(key,k)),"count":n} for k,n in d[:limit]]


def unique(rows,field): return {r.get(field,"").strip() for r in rows if r.get(field,"").strip()}


def schema_check(actual,expected):
    return {"expected_columns":len(expected),"actual_columns":len(actual),"missing_columns":[x for x in expected if x not in actual],"extra_columns":[x for x in actual if x not in expected],"column_order_matches":actual==expected}


def references(data,limit):
    p=unique(data.get("players.csv",[]),"player_id"); t=unique(data.get("teams.csv",[]),"team_id"); g=unique(data.get("gameweeks.csv",[]),"gameweek"); f=unique(data.get("fixtures.csv",[]),"fixture_id")
    checks={}
    checks["player_team"]=[{"player_id":r.get("player_id"),"team_id":r.get("team_id")} for r in data.get("players.csv",[]) if r.get("team_id","").strip() not in t]
    checks["fixture_teams"]=[{"fixture_id":r.get("fixture_id")} for r in data.get("fixtures.csv",[]) if r.get("team_h","").strip() not in t or r.get("team_a","").strip() not in t]
    checks["fixture_gameweek"]=[{"fixture_id":r.get("fixture_id")} for r in data.get("fixtures.csv",[]) if r.get("gameweek","").strip() not in g]
    checks["player_gameweek_players"]=[{"player_id":r.get("player_id")} for r in data.get("player_gameweek.csv",[]) if r.get("player_id","").strip() not in p]
    checks["player_gameweek_fixtures"]=[{"fixture_id":r.get("fixture_id")} for r in data.get("player_gameweek.csv",[]) if r.get("fixture_id","").strip() not in f]
    checks["player_gameweek_gameweeks"]=[{"gameweek":r.get("gameweek")} for r in data.get("player_gameweek.csv",[]) if r.get("gameweek","").strip() not in g]
    checks["season_history_players"]=[{"player_id":r.get("player_id")} for r in data.get("player_season_history.csv",[]) if r.get("player_id","").strip() not in p]
    return {k:{"invalid_count":len(v),"examples":v[:limit]} for k,v in checks.items()}


def business(data,season,limit):
    p=data.get("players.csv",[]); t=data.get("teams.csv",[]); g=data.get("gameweeks.csv",[]); f=data.get("fixtures.csv",[]); pg=data.get("player_gameweek",data.get("player_gameweek.csv",[])); h=data.get("player_season_history.csv",[])
    errors=[]; warnings=[]
    if len(t)!=20: warnings.append(f"Expected 20 teams; found {len(t)}.")
    if len(p)<500: warnings.append(f"Player count unexpectedly low: {len(p)}.")
    if len(g)!=38: warnings.append(f"Expected 38 gameweeks; found {len(g)}.")
    if len(f)!=380: warnings.append(f"Expected 380 fixtures for a complete season; found {len(f)}.")
    pos=Counter(); bad=[]
    for r in p:
        try: x=int(r.get("position_id","")); pos[x]+=1; bad.append(r.get("player_id")) if x not in POSITION_NAMES else None
        except ValueError: bad.append(r.get("player_id"))
    if bad: errors.append(f"{len(bad)} players have invalid position_id values.")
    badcost=[]
    for r in p:
        try:
            x=int(r.get("now_cost",""));
            if not 1<=x<=200: badcost.append(r.get("player_id"))
        except ValueError: badcost.append(r.get("player_id"))
    if badcost: errors.append(f"{len(badcost)} players have invalid now_cost values.")
    fgw=Counter(r.get("gameweek","").strip() for r in f if r.get("gameweek","").strip()); anomalies=[{"gameweek":k,"fixtures":v} for k,v in sorted(fgw.items(),key=lambda x:int(x[0]) if x[0].isdigit() else x[0]) if v!=10]
    if anomalies: warnings.append(f"{len(anomalies)} gameweeks do not contain exactly 10 fixtures.")
    same=[r.get("fixture_id") for r in f if r.get("team_h","").strip()==r.get("team_a","").strip()]
    if same: errors.append(f"{len(same)} fixtures have identical home/away teams.")
    diffbad=[]
    for r in f:
        for c in ("team_h_difficulty","team_a_difficulty"):
            try:
                x=int(r.get(c,""));
                if not 1<=x<=5: diffbad.append(r.get("fixture_id"))
            except ValueError: diffbad.append(r.get("fixture_id"))
    if diffbad: errors.append(f"{len(diffbad)} fixture difficulty values are outside 1-5.")
    current=[r for r in pg if r.get("season","").strip()==season]
    if not current: warnings.append("player_gameweek.csv has 0 current-season rows; this is EXPECTED before the first completed gameweek.")
    hs=Counter(r.get("season","").strip() for r in h if r.get("season","").strip())
    if season in hs: warnings.append(f"player_season_history.csv contains {hs[season]} rows for current season {season}; verify this is intentional.")
    badmin=[]; badpts=[]
    for r in pg:
        if r.get("minutes","").strip():
            try:
                x=int(r["minutes"]); badmin.append(r.get("player_id")) if not 0<=x<=120 else None
            except ValueError: badmin.append(r.get("player_id"))
        if r.get("total_points","").strip():
            try:
                x=int(r["total_points"]); badpts.append(r.get("player_id")) if x<-20 else None
            except ValueError: badpts.append(r.get("player_id"))
    if badmin: errors.append(f"{len(badmin)} player-gameweek rows have invalid minutes.")
    if badpts: errors.append(f"{len(badpts)} player-gameweek rows have implausibly low total_points.")
    return {"errors":errors,"warnings":warnings,"position_counts":{POSITION_NAMES.get(k,f"Unknown({k})"):v for k,v in sorted(pos.items())},"status_counts":dict(Counter(r.get("status","").strip() or "<empty>" for r in p)),"fixture_counts_by_gameweek":dict(sorted(fgw.items(),key=lambda x:int(x[0]) if x[0].isdigit() else x[0])),"fixture_gameweek_anomalies":anomalies[:limit],"historical_season_counts":dict(sorted(hs.items())),"current_season_player_gameweek_rows":len(current),"historical_player_season_rows":len(h),"invalid_positions_examples":bad[:limit],"invalid_cost_examples":badcost[:limit],"invalid_minutes_examples":badmin[:limit],"invalid_points_examples":badpts[:limit]}


def main():
    a=args(); configure(a)
    if not SEASON_RE.fullmatch(a.season): raise RuntimeError("Invalid season format; use YYYY-YY.")
    root=Path(a.project_root).expanduser().resolve() if a.project_root else Path(__file__).resolve().parents[1]
    inp=Path(a.input_dir).expanduser().resolve() if a.input_dir else root/"data"/"processed"/a.season
    report={"schema_version":"1.0.0","inspector_version":VERSION,"season":a.season,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"project_root":str(root),"input_directory":str(inp),"status":"PASS","files":{},"schema_checks":{},"duplicates":{},"references":{},"business_rules":{},"manifest_check":{},"errors":[],"warnings":[]}
    if not inp.exists(): report["status"]="FAIL"; report["errors"].append(f"Processed directory does not exist: {inp}"); return finish(root,a.season,report,1)
    schemas,sw=load_schemas(inp/"dataset_manifest.json"); report["warnings"].extend(sw); data={}; counts={}
    manifest=None
    if (inp/"dataset_manifest.json").exists():
        try: manifest=json.loads((inp/"dataset_manifest.json").read_text(encoding="utf-8")); report["manifest"]=manifest
        except Exception as e: report["errors"].append(f"Cannot parse dataset_manifest.json: {e}")
    else: report["warnings"].append("dataset_manifest.json is missing.")
    for name in FILES:
        path=inp/name
        if not path.exists():
            report["files"][name]={"exists":False};
            if name!="dataset_manifest.json": report["errors"].append(f"Missing required file: {name}")
            continue
        if name=="dataset_manifest.json": report["files"][name]={"exists":True,"size_bytes":path.stat().st_size}; continue
        try: fields,rows,csv_errors=read_csv(path)
        except Exception as e: report["errors"].append(f"Cannot read {name}: {e}"); continue
        data[name]=rows; counts[name]=len(rows); sc=schema_check(fields,schemas[name]); report["schema_checks"][name]=sc
        report["files"][name]={"exists":True,"size_bytes":path.stat().st_size,"rows":len(rows),"columns":len(fields),"read_errors":csv_errors,"column_profile":profile(fields,rows,a.missingness_warning)}
        report["errors"].extend(f"{name}: {e}" for e in csv_errors)
        if sc["missing_columns"] or sc["extra_columns"]: report["errors"].append(f"{name}: schema mismatch.")
        if rows:
            for c,x in report["files"][name]["column_profile"].items():
                if x.get("missingness_warning"): report["warnings"].append(f"{name}.{c}: {x['missing_percent']:.1f}% missing.")
    for name,key in KEYS.items():
        if name not in data: continue
        n,ex=duplicates(data[name],key,a.max_examples); report["duplicates"][name]={"key":list(key),"duplicate_key_count":n,"examples":ex}
        if n: report["errors"].append(f"{name}: {n} duplicate key(s).")
    report["references"]=references(data,a.max_examples)
    for k,x in report["references"].items():
        if x["invalid_count"]: report["errors"].append(f"{k}: {x['invalid_count']} invalid reference(s).")
    report["business_rules"]=business(data,a.season,a.max_examples); report["errors"].extend(report["business_rules"]["errors"]); report["warnings"].extend(report["business_rules"]["warnings"])
    expected=(manifest or {}).get("counts",{}) if isinstance(manifest,dict) else {}; mism=[]
    mapping={"teams.csv":"teams","players.csv":"players","gameweeks.csv":"gameweeks","fixtures.csv":"fixtures","player_gameweek.csv":"player_gameweek_rows","player_season_history.csv":"player_season_history_rows"}
    for fn,mk in mapping.items():
        if mk in expected and counts.get(fn)!=expected[mk]: mism.append({"file":fn,"manifest_count":expected[mk],"actual_count":counts.get(fn,0)})
    report["manifest_check"]={"available":manifest is not None,"mismatches":mism}
    if mism: report["errors"].append("CSV row counts do not match dataset_manifest.json.")
    report["summary"]={"teams":counts.get("teams.csv",0),"players":counts.get("players.csv",0),"gameweeks":counts.get("gameweeks.csv",0),"fixtures":counts.get("fixtures.csv",0),"player_gameweek_rows":counts.get("player_gameweek.csv",0),"player_season_history_rows":counts.get("player_season_history.csv",0)}
    if report["errors"]: report["status"]="FAIL"
    elif a.strict and report["warnings"]: report["status"]="FAIL"; report["errors"].append(f"Strict mode converted {len(report['warnings'])} warning(s) to failure.")
    return finish(root,a.season,report,0 if report["status"]=="PASS" else 1)


def finish(root,season,report,code):
    out=root/"data"/"validation"/season; out.mkdir(parents=True,exist_ok=True)
    jp=out/f"processed_inspection_report_{season}.json"; tp=out/f"processed_inspection_report_{season}.txt"
    jp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    s=report.get("summary",{}); lines=["="*72,"FPL PROCESSED DATASET INSPECTION REPORT","="*72,f"Version : {report['inspector_version']}",f"Season  : {report['season']}",f"Status  : {report['status']}",f"Input   : {report['input_directory']}","","COUNTS","-"*72]
    for k in ("teams","players","gameweeks","fixtures","player_gameweek_rows","player_season_history_rows"): lines.append(f"{k:<28}: {s.get(k,0)}")
    lines += ["","DUPLICATES","-"*72]+[f"{n:<30}: {x['duplicate_key_count']}" for n,x in report.get("duplicates",{}).items()]
    lines += ["","REFERENTIAL INTEGRITY","-"*72]+[f"{n:<35}: {x['invalid_count']}" for n,x in report.get("references",{}).items()]
    br=report.get("business_rules",{}); lines += ["","BUSINESS / DATA QUALITY","-"*72,f"Current-season player-GW rows : {br.get('current_season_player_gameweek_rows',0)}",f"Historical player-season rows : {br.get('historical_player_season_rows',0)}",f"Position distribution         : {br.get('position_counts',{})}",f"Player status distribution    : {br.get('status_counts',{})}",f"Historical seasons            : {br.get('historical_season_counts',{})}","","ERRORS","-"*72]
    lines += [f"- {x}" for x in report["errors"]] or ["- None"]; lines += ["","WARNINGS","-"*72]; lines += [f"- {x}" for x in report["warnings"]] or ["- None"]; lines += ["","="*72,f"RESULT: {report['status']}","="*72]
    tp.write_text("\n".join(lines)+"\n",encoding="utf-8")
    LOG.info("Inspection complete: %s",report["status"]); LOG.info("JSON report : %s",jp); LOG.info("Text report : %s",tp); LOG.info("Errors=%d Warnings=%d",len(report["errors"]),len(report["warnings"]))
    return code

if __name__=="__main__":
    try: raise SystemExit(main())
    except KeyboardInterrupt: raise SystemExit(130)
    except Exception as e: LOG.error("INSPECTION FAILED: %s",e); raise SystemExit(2)
