"""Csapatom-adatok szinkronja a Supabase-be (a GitHub Action futtatja a build.py után).
- Csapatkeretek az MLSZ adatbankból: új játékosokat felvesz (mlsz_id alapján), a meglévőket nem írja felül,
  csak az MLSZ-statisztikájukat frissíti.
- Lejátszott meccsek hivatalos jegyzőkönyvei (kezdők, cserék, gólok, lapok) a match_reports táblába.
Kell hozzá: SUPABASE_URL és SUPABASE_SECRET_KEY környezeti változó. Ha nincs kulcs, nem csinál semmit."""
import os, re, sys, json, html, datetime, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import get, clean, TEAMS

URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
KEY = os.environ.get('SUPABASE_SECRET_KEY', '')
SQUAD_OF = {'F2': 'FELNOTT', 'KUPA': 'FELNOTT', 'MAKL': 'FELNOTT', 'U14R': 'U14', 'U14H': 'U14', 'U13R': 'U13', 'U13H': 'U13'}
PRIO = ['U12', 'U13', 'U14', 'U15', 'U16', 'U17', 'U21', 'FELNOTT', 'F3', 'NOI']   # több keretben: a legfiatalabb nyer
sq = lambda c: SQUAD_OF.get(c, c)
NOW = ''


def api(method, path, body=None, prefer=None):
    h = {'apikey': KEY, 'Content-Type': 'application/json'}
    if KEY.startswith('eyJ'):
        h['Authorization'] = 'Bearer ' + KEY
    if prefer:
        h['Prefer'] = prefer
    req = urllib.request.Request(URL + '/rest/v1/' + path, method=method, headers=h,
                                 data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read().decode()
        return json.loads(t) if t else None


def lineup(url, team):
    t = get(url)
    for side in ('left_team', 'right_team'):
        i = t.find(f'id="{side}"')
        j = t.find('id="right_team"') if side == 'left_team' else t.find('class="matchHeader"', i + 10)
        blk = t[i: j if j > 0 else len(t)]
        if f'/{team}.html' not in blk[:1500]:
            continue
        k = blk.find('class="replacement"')

        def rows(s):
            r = []
            for row in re.findall(r'<tr class="template-tr-selectable">(.*?)</tr>', s, re.S):
                r.append({'pid': re.search(r'player/(\d+)\.html', row).group(1),
                          'num': clean(re.search(r'class="playerNum">(.*?)</span>', row).group(1)),
                          'name': clean(re.search(r'class="match_players_name">(.*?)</td>', row, re.S).group(1)),
                          'ev': re.findall(r'event_([a-z_]+)\.png\)">(\d+)', row)})
            return r
        return {'start': rows(blk[:k] if k > 0 else blk), 'subs': rows(blk[k:]) if k > 0 else []}
    return None



def player_stats(pid):
    t = get(f'https://adatbank.mlsz.hu/player/{pid}.html')
    t2 = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S)
    L = [l.strip() for l in html.unescape(re.sub(r'<[^>]+>', '\n', t2)).split('\n') if l.strip()]
    seasons, i = [], 0
    while i < len(L):
        m = re.match(r'^(\d{4}/\d{4}) - (.+)$', L[i])
        if not m:
            i += 1
            continue
        s = {'season': m.group(1), 'club': m.group(2), 'comps': []}
        k = i
        while k < len(L) and L[k] != 'iros':
            k += 1
        j = k + 9
        while j < len(L) and not re.match(r'^\d{4}/\d{4} - ', L[j]):
            if not re.match(r'^-?\d+$', L[j]) and j + 1 < len(L) and re.match(r'^\(\d+\.\)$', L[j + 1]):
                nums = L[j + 2:j + 10]
                if len(nums) == 8 and all(re.match(r'^\d+$', x) for x in nums):
                    n = list(map(int, nums))
                    s['comps'].append({'name': L[j], 'rank': L[j + 1].strip('().'), 'app': n[0], 'start': n[1], 'sub': n[2], 'bench': n[3],
                                       'goals': n[4], 'og': n[5], 'yellow': n[6], 'red': n[7]})
                    j += 10
                    continue
            j += 1
        if s['comps']:
            seasons.append(s)
        i = j
    return seasons



def player_info(pid):
    t = get(f'https://adatbank.mlsz.hu/player/{pid}.html')
    m = re.search(r'<title>(.*?) -', t)
    name = clean(m.group(1)).title() if m else ''
    b = re.search(r'Születési idő\s*</[^>]+>\s*<[^>]+>\s*(\d{4})\. (\d{2})\. (\d{2})\.', t)
    if not b:
        L = [l.strip() for l in html.unescape(re.sub(r'<[^>]+>', '\n', t)).split('\n') if l.strip()]
        for i, l in enumerate(L):
            if l == 'Születési idő' and i + 1 < len(L):
                b = re.match(r'(\d{4})\. (\d{2})\. (\d{2})\.', L[i + 1])
                break
    return name, (f'{b.group(1)}-{b.group(2)}-{b.group(3)}' if b else None)


def main():
    if not URL or not KEY:
        print('Nincs SUPABASE_SECRET_KEY – a Csapatom-szinkron kimarad.', file=sys.stderr)
        return
    today = datetime.date.today().isoformat()
    global NOW
    NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # 1) csapatkeretek
    roster = {}
    for code, name, org, comp, tid, lname, dur, tab in TEAMS:
        t = get(f'https://adatbank.mlsz.hu/club/67/{org}/{comp}/1/{tid}.html')
        for pid in set(re.findall(r'adatbank\.mlsz\.hu/player/(\d+)\.html', t)):
            roster.setdefault(pid, set()).add(sq(code))
    have = {p['mlsz_id']: p for p in api('GET', 'players?select=id,mlsz_id,squad&mlsz_id=not.is.null') or []}
    new, upd = [], 0
    for pid, sqs in roster.items():
        squad = min(sqs, key=lambda s: PRIO.index(s) if s in PRIO else 99)
        stats = {'id': pid, 'updated': today, 'seasons': [{k: v for k, v in s.items()} for s in player_stats(pid)]}
        if pid in have:
            api('PATCH', 'players?mlsz_id=eq.' + pid, {'mlsz': stats, 'updated_at': NOW})
            upd += 1
        else:
            nm, birth = player_info(pid)
            if nm:
                new.append({'squad': squad, 'name': nm, 'birth': birth, 'mlsz_id': pid, 'mlsz': stats})
    if new:
        api('POST', 'players?on_conflict=mlsz_id', new, 'resolution=ignore-duplicates')
    print(f'Játékosok: {len(new)} új, {upd} frissített statisztika', file=sys.stderr)
    # 2) jegyzőkönyvek
    F = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'klub.json')))
    done = {r['key'] for r in api('GET', 'match_reports?select=key&status=eq.played') or []}
    rows = []
    for code, name, org, comp, tid, lname, dur, tab in TEAMS:
        seen = {}
        for f in sorted(F['teams'].get(code, {}).get('fixtures', []), key=lambda f: (f['d'], f.get('t') or '')):
            # tornanapon (női csapat) egy napra több meccs is jut: a második kulcsa 'kód|dátum#2'
            seen[f['d']] = seen.get(f['d'], 0) + 1
            key = f'{code}|{f["d"]}' + (f'#{seen[f["d"]]}' if seen[f['d']] > 1 else '')
            if f.get('st') != 'played' or not f.get('u') or key in done:
                continue
            lu = lineup(f['u'], tid)
            if not lu:
                continue
            conv = lambda arr: [{'id': x['pid'], 'num': x['num'], 'n': x['name'].title(),
                                 'g': sum(1 for e, _ in x['ev'] if e == 'goal'), 'y': sum(1 for e, _ in x['ev'] if 'yellow' in e),
                                 'r': sum(1 for e, _ in x['ev'] if 'red' in e), 'sw': [int(m) for e, m in x['ev'] if e == 'swap']} for x in arr]
            rows.append({'key': key, 'squad': sq(code), 'mlsz_id': f['u'].rsplit('/', 1)[-1].split('.')[0], 'url': f['u'],
                         'status': 'played', 'start': conv(lu['start']), 'subs': conv(lu['subs']), 'updated_at': NOW})
    bad = 0
    for n in range(0, len(rows), 50):
        try:
            api('POST', 'match_reports?on_conflict=key', rows[n:n + 50], 'resolution=merge-duplicates')
        except urllib.error.HTTPError as e:
            bad += len(rows[n:n + 50])
            print('Jegyzőkönyv-mentési hiba:', e.code, e.read().decode()[:300], file=sys.stderr)
    print(f'Jegyzőkönyvek: {len(rows) - bad} új' + (f', {bad} hibás' if bad else ''), file=sys.stderr)


if __name__ == '__main__':
    main()
