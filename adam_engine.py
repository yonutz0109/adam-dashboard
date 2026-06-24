"""
ADAM Engine v4 — football-data.org ca sursă principală (gratuit, fără suspendare)
API-SPORTS opțional doar pentru cote.
"""
import json
import sqlite3
import urllib.request
import urllib.parse
import time
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────
# FOOTBALL-DATA.ORG — coduri competiții (gratuit, nelimitat)
# ─────────────────────────────────────────────────────────────────────────
FD_COMPETITIONS = {
    "PL":  {"name": "Premier League",       "country": "England"},
    "PD":  {"name": "La Liga",              "country": "Spain"},
    "SA":  {"name": "Serie A",              "country": "Italy"},
    "BL1": {"name": "Bundesliga",           "country": "Germany"},
    "FL1": {"name": "Ligue 1",              "country": "France"},
    "CL":  {"name": "Champions League",     "country": "Europe"},
    "EL":  {"name": "Europa League",        "country": "Europe"},
    "DED": {"name": "Eredivisie",           "country": "Netherlands"},
    "PPL": {"name": "Primeira Liga",        "country": "Portugal"},
    "ELC": {"name": "Championship",         "country": "England"},
    "BSA": {"name": "Brasileirao",          "country": "Brazil"},
}

# ─────────────────────────────────────────────────────────────────────────
# DATE STATISTICE LIGI
# ─────────────────────────────────────────────────────────────────────────
LEAGUE_STATS = {
    "Champions League":  {"o25": 62, "gg": 58, "avg": 3.02, "hw": 44, "tier": "TOP"},
    "Europa League":     {"o25": 59, "gg": 55, "avg": 2.88, "hw": 43, "tier": "TOP"},
    "Premier League":    {"o25": 64, "gg": 60, "avg": 3.10, "hw": 45, "tier": "TOP"},
    "La Liga":           {"o25": 59, "gg": 55, "avg": 2.87, "hw": 47, "tier": "TOP"},
    "Serie A":           {"o25": 57, "gg": 53, "avg": 2.78, "hw": 45, "tier": "TOP"},
    "Bundesliga":        {"o25": 67, "gg": 60, "avg": 3.22, "hw": 44, "tier": "TOP"},
    "Ligue 1":           {"o25": 59, "gg": 54, "avg": 2.85, "hw": 46, "tier": "TOP"},
    "Eredivisie":        {"o25": 66, "gg": 61, "avg": 3.18, "hw": 46, "tier": "MED"},
    "Primeira Liga":     {"o25": 56, "gg": 51, "avg": 2.72, "hw": 48, "tier": "MED"},
    "Championship":      {"o25": 55, "gg": 50, "avg": 2.65, "hw": 46, "tier": "MED"},
    "Brasileirao":       {"o25": 52, "gg": 48, "avg": 2.60, "hw": 48, "tier": "MED"},
    "Liga I":            {"o25": 50, "gg": 47, "avg": 2.55, "hw": 46, "tier": "MED"},
    "MLS":               {"o25": 60, "gg": 55, "avg": 2.90, "hw": 43, "tier": "MED"},
    "Super Lig":         {"o25": 57, "gg": 53, "avg": 2.80, "hw": 47, "tier": "MED"},
}

def league_stats(league):
    if not league:
        return None
    if league in LEAGUE_STATS:
        return LEAGUE_STATS[league]
    ll = league.lower()
    for k, v in LEAGUE_STATS.items():
        if k.lower() in ll or ll in k.lower():
            return v
    return None

# ─────────────────────────────────────────────────────────────────────────
# HTTP HELPERS
# ─────────────────────────────────────────────────────────────────────────
def fd_get(url, fd_key=""):
    req = urllib.request.Request(url)
    if fd_key:
        req.add_header("X-Auth-Token", fd_key)
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def api_sports_get(url, key):
    req = urllib.request.Request(url)
    req.add_header("x-apisports-key", key)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    errors = data.get("errors")
    if errors:
        raise RuntimeError("API-SPORTS: " + json.dumps(errors, ensure_ascii=False))
    return data

def safe_get(obj, path, default=None):
    cur = obj
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p, default)
    return cur

def score_num(x):
    if x is None: return None
    try: return int(x)
    except: return None

# ─────────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────────
def init_db(db_file):
    con = sqlite3.connect(db_file)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches(
            fixture_id TEXT, sport TEXT, date TEXT, league TEXT,
            home_id TEXT, away_id TEXT, home_name TEXT, away_name TEXT,
            status TEXT, gh INTEGER, ga INTEGER,
            c1 TEXT, cx TEXT, c2 TEXT,
            ai INTEGER, selection TEXT, risk TEXT, verdict TEXT,
            PRIMARY KEY(fixture_id, sport)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_home ON matches(sport, home_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_away ON matches(sport, away_id)")
    con.commit()
    con.close()

def save_rows(db_file, rows, sport):
    con = sqlite3.connect(db_file)
    cur = con.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO matches(fixture_id,sport,date,league,home_id,away_id,
                home_name,away_name,status,gh,ga,c1,cx,c2,ai,selection,risk,verdict)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(fixture_id,sport) DO UPDATE SET
                status=excluded.status,gh=excluded.gh,ga=excluded.ga,
                c1=excluded.c1,cx=excluded.cx,c2=excluded.c2,
                ai=excluded.ai,selection=excluded.selection,
                risk=excluded.risk,verdict=excluded.verdict
        """, (r["FixtureID"], sport, r["Data"], r["Liga"], r["HomeID"], r["AwayID"],
              r["HomeName"], r["AwayName"], r["Status"], r["GH"], r["GA"],
              r["Cota1"], r["CotaX"], r["Cota2"], r["AIConfidence"],
              r["SelectieFinala"], r["RiscFinal"], r["Verdict"]))
    con.commit()
    con.close()

def db_team_history(db_file, team_id, team_name, last=5):
    """Formă din DB local — ultimele N meciuri ale echipei."""
    con = sqlite3.connect(db_file)
    cur = con.cursor()
    cur.execute("""
        SELECT home_id,away_id,home_name,away_name,gh,ga FROM matches
        WHERE sport='football' AND (home_id=? OR away_id=? OR home_name=? OR away_name=?)
        AND gh IS NOT NULL AND ga IS NOT NULL
        ORDER BY date DESC LIMIT ?
    """, (str(team_id), str(team_id), team_name, team_name, last))
    rows = cur.fetchall()
    con.close()
    return rows

def db_h2h(db_file, home_name, away_name, last=5):
    """Head-to-head din DB local."""
    con = sqlite3.connect(db_file)
    cur = con.cursor()
    cur.execute("""
        SELECT home_name,away_name,gh,ga FROM matches
        WHERE sport='football'
        AND ((home_name=? AND away_name=?) OR (home_name=? AND away_name=?))
        AND gh IS NOT NULL AND ga IS NOT NULL
        ORDER BY date DESC LIMIT ?
    """, (home_name, away_name, away_name, home_name, last))
    rows = cur.fetchall()
    con.close()
    return rows

def db_over_history(db_file, team_id, team_name, last=10):
    """Procentaj Over 2.5 din ultimele N meciuri ale echipei."""
    rows = db_team_history(db_file, team_id, team_name, last)
    if not rows:
        return None, 0, 0
    over_count = total = 0
    for hid, aid, hn, an, gh, ga in rows:
        if gh is None or ga is None:
            continue
        total += 1
        if int(gh) + int(ga) >= 3:
            over_count += 1
    pct = round(over_count / total * 100) if total else 0
    return pct, over_count, total

def winrate_stats(db_file, sport):
    con = sqlite3.connect(db_file)
    cur = con.cursor()
    cur.execute("""
        SELECT selection,gh,ga FROM matches
        WHERE sport=? AND gh IS NOT NULL AND ga IS NOT NULL
        ORDER BY date DESC LIMIT 500
    """, (sport,))
    rows = cur.fetchall()
    con.close()
    total = wins = 0
    for sel, gh, ga in rows:
        pick = str(sel or "")
        hit = None
        if "Peste 1.5" in pick or "Over 1.5" in pick:
            hit = (int(gh) + int(ga)) >= 2
        elif "Peste 2.5" in pick or "Over 2.5" in pick:
            hit = (int(gh) + int(ga)) >= 3
        if hit is not None:
            total += 1
            if hit:
                wins += 1
    rate = round(wins / total * 100, 1) if total else 0
    return wins, total, rate

def learning_adjustment(db_file, sport):
    wins, total, rate = winrate_stats(db_file, sport)
    if total < 10:
        return 0, "learning: date insuficiente"
    if rate >= 62:
        return 2, f"learning +2 | WR {rate}%"
    if rate < 48:
        return -3, f"learning -3 | WR {rate}%"
    return 0, f"learning neutru | WR {rate}%"

# ─────────────────────────────────────────────────────────────────────────
# FOOTBALL-DATA.ORG — fetch meciuri + formă + h2h + clasament
# ─────────────────────────────────────────────────────────────────────────
_fd_team_form_cache = {}
_fd_h2h_cache = {}
_fd_standings_cache = {}

def fd_team_form(fd_key, team_id, last=5):
    """Ultimele N meciuri ale echipei de pe football-data.org."""
    if team_id in _fd_team_form_cache:
        return _fd_team_form_cache[team_id]
    try:
        url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED&limit=10"
        data = fd_get(url, fd_key)
        matches = sorted(data.get("matches", []),
                        key=lambda m: m.get("utcDate",""), reverse=True)[:last]
        wins = draws = losses = gf = ga = over25 = gg = cnt = 0
        for m in matches:
            ft = safe_get(m, ["score","fullTime"], {})
            h = score_num(ft.get("home"))
            a = score_num(ft.get("away"))
            if h is None or a is None:
                continue
            hid = safe_get(m, ["homeTeam","id"])
            if str(hid) == str(team_id):
                mygf, myga = h, a
            else:
                mygf, myga = a, h
            cnt += 1
            gf += mygf; ga += myga
            if mygf > myga: wins += 1
            elif mygf == myga: draws += 1
            else: losses += 1
            if mygf + myga >= 3: over25 += 1
            if mygf >= 1 and myga >= 1: gg += 1

        if cnt == 0:
            result = (50, "FD: no data", 0, 0)
        else:
            avg_gf = gf / cnt
            avg_ga = ga / cnt
            score = 50 + wins*6 + draws*2 - losses + int((avg_gf - avg_ga)*7)
            if avg_gf >= 2.0: score += 4
            elif avg_gf >= 1.5: score += 2
            if avg_ga >= 2.0: score -= 3
            score = max(35, min(95, score))
            note = f"FD {cnt}m W{wins}D{draws}L{losses} avg{avg_gf:.1f}-{avg_ga:.1f} O25:{over25}/{cnt}"
            result = (score, note, round(over25/cnt*100) if cnt else 0, cnt)
    except Exception as e:
        result = (50, f"FD err: {str(e)[:30]}", 0, 0)

    _fd_team_form_cache[team_id] = result
    return result

def fd_h2h(fd_key, match_id, last=5):
    """Head-to-head direct din football-data.org."""
    cache_key = str(match_id)
    if cache_key in _fd_h2h_cache:
        return _fd_h2h_cache[cache_key]
    try:
        url = f"https://api.football-data.org/v4/matches/{match_id}/head2head?limit={last}"
        data = fd_get(url, fd_key)
        matches = data.get("matches", [])
        h_wins = a_wins = draws = total_goals = cnt = over25 = 0
        home_id = safe_get(data, ["aggregates","homeTeam","id"])
        for m in matches:
            ft = safe_get(m, ["score","fullTime"], {})
            h = score_num(ft.get("home"))
            a = score_num(ft.get("away"))
            if h is None or a is None:
                continue
            cnt += 1
            total_goals += h + a
            if h + a >= 3: over25 += 1
            winner = safe_get(m, ["score","winner"])
            if winner == "HOME_TEAM": h_wins += 1
            elif winner == "AWAY_TEAM": a_wins += 1
            else: draws += 1
        if cnt == 0:
            result = None
        else:
            avg_goals = round(total_goals / cnt, 1)
            o25_pct = round(over25 / cnt * 100)
            result = {
                "cnt": cnt, "h_wins": h_wins, "a_wins": a_wins,
                "draws": draws, "avg_goals": avg_goals, "o25_pct": o25_pct
            }
    except Exception:
        result = None
    _fd_h2h_cache[cache_key] = result
    return result

def fd_standings(fd_key, competition_code):
    """Clasament din football-data.org — cache per competiție."""
    if competition_code in _fd_standings_cache:
        return _fd_standings_cache[competition_code]
    try:
        url = f"https://api.football-data.org/v4/competitions/{competition_code}/standings"
        data = fd_get(url, fd_key)
        table = []
        for s in data.get("standings", []):
            if s.get("type") == "TOTAL":
                table = s.get("table", [])
                break
        if not table and data.get("standings"):
            table = data["standings"][0].get("table", [])
        standings = {}
        for entry in table:
            tid = safe_get(entry, ["team","id"])
            if tid:
                standings[tid] = {
                    "position": entry.get("position"),
                    "points": entry.get("points"),
                    "won": entry.get("won"),
                    "draw": entry.get("draw"),
                    "lost": entry.get("lost"),
                    "goalsFor": entry.get("goalsFor"),
                    "goalsAgainst": entry.get("goalsAgainst"),
                    "goalDiff": entry.get("goalDifference"),
                    "form": entry.get("form",""),
                }
        _fd_standings_cache[competition_code] = standings
    except Exception:
        _fd_standings_cache[competition_code] = {}
    return _fd_standings_cache[competition_code]

# ─────────────────────────────────────────────────────────────────────────
# MOTOR DE CALCUL v4
# ─────────────────────────────────────────────────────────────────────────
def live_flag(status, elapsed, gh, ga):
    gh = gh or 0; ga = ga or 0
    s = str(status).upper()
    if any(x in s for x in ["1H","2H","HT","LIVE","IN_PLAY"]):
        if elapsed and elapsed >= 70 and gh == 0 and ga == 0:
            return "EVITA LIVE"
        if elapsed and elapsed >= 55 and gh < ga:
            return "COMEBACK ALERT"
        return "LIVE OK"
    return "-"

def suspicious_odds(c1, cx, c2):
    try:
        h = float(c1); a = float(c2); d = float(cx) if cx not in ["-","",None] else 3.5
        return "DA" if h > 7 or d > 8 or a > 7 else "-"
    except: return "-"

def calc_score(sport, league, hname, aname, c1, cx, c2,
               hf, af, h_over_pct, a_over_pct,
               h_standing, a_standing, h2h, live, susp, learn_adj=0):
    """
    Motor v4: probabilitate cote + formă FD + clasament + h2h + over history.
    """
    lstats = league_stats(league)
    has_odds = c1 not in ["-","",None] and c2 not in ["-","",None]

    # ── Fără cote ──
    if not has_odds:
        tier = lstats["tier"] if lstats else "LOW"
        if tier == "LOW" or lstats is None:
            return 45, "EVITA", "EVITA", "AVOID", "-", "Ligă mică fără cote"
        base_nc = 65 if lstats["o25"] >= 62 else 60
        sel_nc = "Peste 2.5 goluri" if lstats["o25"] >= 62 else "Peste 1.5 goluri"
        return max(40, min(75, base_nc+learn_adj)), sel_nc, sel_nc, "NO ODDS", "-", f"Fără cote | O25:{lstats['o25']}%"

    # ── Cu cote ──
    try:
        o1 = float(c1); o2 = float(c2)
        ox = float(cx) if cx not in ["-","",None] else None
    except:
        return 50,"EVITA","EVITA","AVOID","-","Cote invalide"

    rp1 = 1.0/o1; rp2 = 1.0/o2; rpx = (1.0/ox) if ox else 0.0
    tot = rp1+rp2+rpx
    p_home = rp1/tot; p_away = rp2/tot; p_draw = rpx/tot if ox else 0.0

    fav_is_home = (p_home >= p_away)
    fav_name = hname if fav_is_home else aname
    fav_prob = p_home if fav_is_home else p_away
    fav_odd = o1 if fav_is_home else o2

    # ── Ajustare formă ──
    fav_prob_adj = fav_prob
    form_known = not (hf == 50 and af == 50)
    if form_known:
        diff = (hf-af)/100.0 if fav_is_home else (af-hf)/100.0
        fav_prob_adj = min(0.93, max(0.28, fav_prob + diff*0.08))

    # ── Ajustare clasament ──
    standing_note = ""
    if h_standing and a_standing:
        hp = h_standing.get("position", 10)
        ap = a_standing.get("position", 10)
        hgd = h_standing.get("goalDiff", 0) or 0
        agd = a_standing.get("goalDiff", 0) or 0
        pos_diff = ap - hp  # pozitiv = gazda e mai sus
        if pos_diff >= 8:
            fav_prob_adj = min(0.93, fav_prob_adj + 0.04)
        elif pos_diff <= -8:
            fav_prob_adj = max(0.28, fav_prob_adj - 0.04)
        hform = h_standing.get("form","")
        if hform.count("W") >= 4:
            fav_prob_adj = min(0.93, fav_prob_adj + 0.02)
        standing_note = f"Poz H:{hp}/A:{ap} GD:{hgd:+d}/{agd:+d}"

    # ── Ajustare H2H ──
    h2h_note = ""
    if h2h:
        h2h_fav_wins = h2h["h_wins"] if fav_is_home else h2h["a_wins"]
        h2h_rate = h2h_fav_wins / h2h["cnt"] if h2h["cnt"] else 0
        if h2h_rate >= 0.6:
            fav_prob_adj = min(0.93, fav_prob_adj + 0.03)
        elif h2h_rate <= 0.25:
            fav_prob_adj = max(0.28, fav_prob_adj - 0.03)
        h2h_note = f"H2H {h2h['cnt']}m: {h2h['h_wins']}-{h2h['draws']}-{h2h['a_wins']} avg:{h2h['avg_goals']} O25:{h2h['o25_pct']}%"

    # ── AI confidence ──
    ai = int(30 + fav_prob_adj*60)
    ai = max(40, min(95, ai+learn_adj))
    if susp == "DA": ai = max(40, ai-8)
    if live in ["EVITA LIVE","RITM MIC","PACE MIC"]: ai = max(40, ai-15)
    elif live == "COMEBACK ALERT": ai = max(40, ai-6)

    # ── Over probability compusă ──
    o25_league = (lstats["o25"]/100.0) if lstats else 0.50
    gg_league = (lstats["gg"]/100.0) if lstats else 0.48
    # Ajustare din istoricul Over per echipă
    h_over = (h_over_pct/100.0) if h_over_pct is not None else o25_league
    a_over = (a_over_pct/100.0) if a_over_pct is not None else o25_league
    h2h_over = (h2h["o25_pct"]/100.0) if h2h else o25_league
    over_prob = round((o25_league + h_over + a_over + h2h_over) / 4, 2)

    # ── Selecție ──
    if live in ["EVITA LIVE","RITM MIC","PACE MIC"]:
        sel = pariu = "EVITA LIVE"
    elif fav_prob_adj >= 0.72:
        sel = pariu = f"{fav_name} câștigă"
    elif fav_prob_adj >= 0.60 and over_prob >= 0.57:
        sel = pariu = "Peste 2.5 goluri"
    elif fav_prob_adj >= 0.55 and gg_league >= 0.53:
        sel = pariu = "GG (ambele marchează)"
    elif fav_prob_adj >= 0.50:
        sel = pariu = "Peste 1.5 goluri"
    elif p_draw >= 0.28 and fav_prob_adj >= 0.43:
        sel = pariu = "1X" if fav_is_home else "X2"
    else:
        sel = pariu = "EVITA (meci incert)"

    # ── Scor estimat ajustat per meci ──
    predicted = predicted_score(fav_prob_adj, fav_is_home, over_prob, hf, af, h2h)

    # ── Value bet ──
    edge = round((fav_prob_adj-fav_prob)/fav_prob*100, 1)
    ev = round(fav_odd*fav_prob_adj, 2)
    if "EVITA" in pariu: verdict = "AVOID"
    elif edge >= 5 and fav_prob_adj >= 0.55: verdict = "VALUE"
    elif fav_prob_adj >= 0.48: verdict = "OK"
    else: verdict = "AVOID"

    vs_str = f"EV:{ev} edge:{edge:+.1f}% p:{fav_prob_adj:.0%}"

    parts = [f"p:{fav_prob:.0%}→{fav_prob_adj:.0%}"]
    if form_known: parts.append(f"H{hf}/A{af}")
    if standing_note: parts.append(standing_note)
    if h2h_note: parts.append(h2h_note)
    if over_prob != o25_league: parts.append(f"Over%:{over_prob:.0%}")
    motiv = " | ".join(parts)

    return ai, sel, pariu, verdict, vs_str, motiv, predicted

def predicted_score(fav_prob, fav_is_home, over_prob, hf, af, h2h):
    """Scor estimat ajustat per meci — bazat pe probabilitate + over history + formă."""
    # Goluri medii estimate
    if over_prob >= 0.65:
        total_est = 3.2
    elif over_prob >= 0.55:
        total_est = 2.7
    elif over_prob >= 0.45:
        total_est = 2.2
    else:
        total_est = 1.8

    # H2H ajustare
    if h2h and h2h.get("avg_goals"):
        total_est = round((total_est + h2h["avg_goals"]) / 2, 1)

    # Distribuție goluri între echipe
    if fav_is_home:
        fav_goals = round(total_est * fav_prob * 1.1)
        und_goals = round(total_est * (1-fav_prob) * 0.9)
        hg, ag = fav_goals, und_goals
    else:
        und_goals = round(total_est * (1-fav_prob) * 0.9)
        fav_goals = round(total_est * fav_prob * 1.1)
        hg, ag = und_goals, fav_goals

    # Limităm la scoruri realiste
    hg = max(0, min(5, hg))
    ag = max(0, min(4, ag))

    # Alternativă mai probabilă
    if hg == ag:
        alt = f"{hg+1}-{ag}"
    elif hg > ag:
        alt = f"{hg}-{ag+1}"
    else:
        alt = f"{hg+1}-{ag}"

    return f"{hg}-{ag} / {alt}"

def final_risk(ai, susp, live):
    if live in ["EVITA LIVE","RITM MIC","PACE MIC"] or susp == "DA":
        return "HIGH"
    if ai >= 72: return "LOW-MED"
    if ai >= 60: return "MED"
    return "HIGH"

# ─────────────────────────────────────────────────────────────────────────
# COTE — API-SPORTS (opțional, doar dacă cheia e validă)
# ─────────────────────────────────────────────────────────────────────────
def fetch_odds_optional(api_key, date_str, progress=None):
    """Cote din API-SPORTS — opțional, nu blochează dacă lipsește/e suspendat."""
    if not api_key:
        return {}
    try:
        if progress: progress("Cote: API-SPORTS...")
        url = f"https://v3.football.api-sports.io/odds?date={date_str}&page=1"
        payload = api_sports_get(url, api_key)
        odds = {}
        for item in payload.get("response", []):
            fid = str(safe_get(item, ["fixture","id"], ""))
            h = d = a = "-"
            for bm in item.get("bookmakers", []):
                for bet in bm.get("bets", []):
                    if bet.get("name") in ["Match Winner","Winner"]:
                        for v in bet.get("values", []):
                            n = str(v.get("value",""))
                            odd = str(v.get("odd","-"))
                            if n in ["Home","1"]: h = odd
                            elif n in ["Draw","X"]: d = odd
                            elif n in ["Away","2"]: a = odd
                        break
            if fid:
                odds[fid] = (h, d, a)
        return odds
    except Exception as e:
        if progress: progress(f"Cote indisponibile ({str(e)[:30]})")
        return {}

# ─────────────────────────────────────────────────────────────────────────
# FETCH PRINCIPAL — football-data.org
# ─────────────────────────────────────────────────────────────────────────
def fetch_football_data(db_file, fd_key, date_str, api_sports_key="", progress=None):
    """
    Aduce meciuri din football-data.org (gratuit) pentru toate competițiile.
    Cote din API-SPORTS dacă e disponibil.
    """
    _fd_team_form_cache.clear()
    _fd_h2h_cache.clear()
    _fd_standings_cache.clear()

    learn_adj, learn_note = learning_adjustment(db_file, "football")

    # Cote opționale
    odds_map = fetch_odds_optional(api_sports_key, date_str, progress)

    all_rows = []
    all_meta = {"total": 0, "competitions": 0, "odds": len(odds_map)}

    for comp_code, comp_info in FD_COMPETITIONS.items():
        try:
            if progress: progress(f"FD: meciuri {comp_info['name']}...")
            url = f"https://api.football-data.org/v4/competitions/{comp_code}/matches?dateFrom={date_str}&dateTo={date_str}"
            data = fd_get(url, fd_key)
            matches = data.get("matches", [])
            if not matches:
                continue

            all_meta["total"] += len(matches)
            all_meta["competitions"] += 1

            # Clasament (1 request per competiție)
            standings = fd_standings(fd_key, comp_code)
            time.sleep(0.15)

            for m in matches:
                try:
                    fid = str(m.get("id",""))
                    date_raw = m.get("utcDate","")
                    status_obj = m.get("status","SCHEDULED")
                    status = str(status_obj)
                    elapsed = m.get("minute", 0) or 0

                    home_obj = m.get("homeTeam", {})
                    away_obj = m.get("awayTeam", {})
                    hname = home_obj.get("name","") or home_obj.get("shortName","")
                    aname = away_obj.get("name","") or away_obj.get("shortName","")
                    hid = home_obj.get("id","")
                    aid = away_obj.get("id","")
                    if not hname or not aname:
                        continue

                    score_obj = m.get("score",{})
                    ft = score_obj.get("fullTime",{})
                    gh = score_num(ft.get("home"))
                    ga = score_num(ft.get("away"))

                    # Cote
                    c1, cx, c2 = odds_map.get(fid, ("-","-","-"))

                    # Formă echipe (football-data.org)
                    hf_data = fd_team_form(fd_key, hid)
                    af_data = fd_team_form(fd_key, aid)
                    hf, hnote = hf_data[0], hf_data[1]
                    af, anote = af_data[0], af_data[1]
                    h_over_pct = hf_data[2] if len(hf_data) > 2 else None
                    a_over_pct = af_data[2] if len(af_data) > 2 else None
                    time.sleep(0.1)

                    # H2H
                    h2h = fd_h2h(fd_key, fid)

                    # Clasament
                    h_stand = standings.get(hid)
                    a_stand = standings.get(aid)

                    # Live flag
                    lf = live_flag(status, elapsed, gh, ga)
                    susp = suspicious_odds(c1, cx, c2)

                    # Calcul AI
                    result = calc_score(
                        "football", comp_info["name"], hname, aname,
                        c1, cx, c2, hf, af, h_over_pct, a_over_pct,
                        h_stand, a_stand, h2h, lf, susp, learn_adj
                    )
                    ai, sel, pariu, verdict, vs_str, motiv, predicted = result
                    risk = final_risk(ai, susp, lf)

                    try:
                        dt = datetime.fromisoformat(date_raw.replace("Z","+00:00"))
                        ora = dt.strftime("%d.%m %H:%M")
                    except:
                        ora = date_raw[:16].replace("T"," ")

                    if lf not in ["-","LIVE OK"]:
                        motiv += f" | {lf}"

                    # Info extra pentru detalii
                    extra_info = []
                    if h_stand:
                        extra_info.append(f"Clasament: {hname} poz.{h_stand['position']} ({h_stand['points']}pts)")
                    if a_stand:
                        extra_info.append(f"{aname} poz.{a_stand['position']} ({a_stand['points']}pts)")
                    if h2h:
                        extra_info.append(f"H2H: {h2h['h_wins']}-{h2h['draws']}-{h2h['a_wins']} în {h2h['cnt']} meciuri, avg {h2h['avg_goals']} goluri")
                    if h_over_pct is not None:
                        extra_info.append(f"Over 2.5 recent: {hname} {h_over_pct}% | {aname} {a_over_pct}%")

                    row = {
                        "Data": date_str, "Sport": "Fotbal", "Ora": ora,
                        "Meci": f"{hname} vs {aname}", "Liga": comp_info["name"],
                        "Status": "NEINCEPUT" if status in ["SCHEDULED","TIMED"] else f"{status} {gh}-{ga}",
                        "ADAM": ai, "AIConfidence": ai, "SelectieFinala": sel, "PariuExact": pariu,
                        "ScorCorect": predicted, "RiscFinal": risk, "Verdict": verdict,
                        "Cota1": c1, "CotaX": cx, "Cota2": c2, "ValueScore": vs_str,
                        "FormHome": hf, "FormAway": af, "LiveFlag": lf, "Motiv": motiv,
                        "FixtureID": fid, "HomeID": str(hid), "AwayID": str(aid),
                        "HomeName": hname, "AwayName": aname, "GH": gh, "GA": ga,
                        "CoteSuspecte": susp,
                        "NoteAI": f"H {hnote} / A {anote} / {learn_note}",
                        "ExtraInfo": " || ".join(extra_info),
                    }
                    all_rows.append(row)
                except Exception:
                    continue

        except Exception as e:
            if progress: progress(f"FD {comp_code}: eroare ({str(e)[:40]})")
            continue

    all_rows.sort(key=lambda r: r["AIConfidence"], reverse=True)
    return all_rows, all_meta


def fetch_dashboard(db_file, api_sports_key, odds_key, sport, date_str, show_all, fd_key="", progress=None):
    init_db(db_file)

    if sport == "football":
        if fd_key:
            rows, meta = fetch_football_data(db_file, fd_key, date_str, api_sports_key, progress)
        elif api_sports_key:
            rows, meta = fetch_api_sports_fallback(db_file, api_sports_key, date_str, progress)
        else:
            raise RuntimeError("Trebuie cel puțin o cheie API: football-data.org (recomandat) sau API-SPORTS.")
    else:
        raise RuntimeError("Momentan doar fotbal prin football-data.org. Handbal/Baschet/Tenis — în curând.")

    save_rows(db_file, rows, sport)
    meta["shown"] = len(rows)
    return rows, meta


def fetch_api_sports_fallback(db_file, api_key, date_str, progress=None):
    """Fallback minimal pe API-SPORTS dacă nu e fd_key."""
    if progress: progress("API-SPORTS: meciuri fotbal...")
    learn_adj, learn_note = learning_adjustment(db_file, "football")
    url = f"https://v3.football.api-sports.io/fixtures?date={date_str}&timezone=Europe/Bucharest"
    payload = api_sports_get(url, api_key)
    items = payload.get("response", [])
    rows = []
    for fx in items:
        try:
            league = safe_get(fx, ["league","name"], "")
            fid = str(safe_get(fx, ["fixture","id"],""))
            date_raw = safe_get(fx, ["fixture","date"],"")
            status = safe_get(fx, ["fixture","status","short"],"NS")
            elapsed = safe_get(fx, ["fixture","status","elapsed"],0) or 0
            gh = score_num(safe_get(fx, ["goals","home"]))
            ga = score_num(safe_get(fx, ["goals","away"]))
            hname = safe_get(fx, ["teams","home","name"],"")
            aname = safe_get(fx, ["teams","away","name"],"")
            hid = str(safe_get(fx, ["teams","home","id"],""))
            aid = str(safe_get(fx, ["teams","away","id"],""))
            if not hname or not aname: continue
            lf = live_flag(status, elapsed, gh, ga)
            result = calc_score("football", league, hname, aname,
                               "-","-","-", 50, 50, None, None,
                               None, None, None, lf, "-", learn_adj)
            ai, sel, pariu, verdict, vs_str, motiv, predicted = result
            try:
                dt = datetime.fromisoformat(date_raw.replace("Z","+00:00"))
                ora = dt.strftime("%d.%m %H:%M")
            except:
                ora = date_raw[:16].replace("T"," ")
            rows.append({
                "Data": date_str, "Sport": "Fotbal", "Ora": ora,
                "Meci": f"{hname} vs {aname}", "Liga": league,
                "Status": "NEINCEPUT" if status in ["NS"] else f"{status} {elapsed}' {gh}-{ga}",
                "ADAM": ai, "AIConfidence": ai, "SelectieFinala": sel, "PariuExact": pariu,
                "ScorCorect": predicted, "RiscFinal": "MED", "Verdict": verdict,
                "Cota1": "-", "CotaX": "-", "Cota2": "-", "ValueScore": vs_str,
                "FormHome": 50, "FormAway": 50, "LiveFlag": lf, "Motiv": motiv,
                "FixtureID": fid, "HomeID": hid, "AwayID": aid,
                "HomeName": hname, "AwayName": aname, "GH": gh, "GA": ga,
                "CoteSuspecte": "-", "NoteAI": learn_note, "ExtraInfo": "",
            })
        except Exception:
            continue
    rows.sort(key=lambda r: r["AIConfidence"], reverse=True)
    return rows, {"total": len(items), "shown": len(rows), "odds": 0}
