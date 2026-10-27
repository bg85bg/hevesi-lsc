"""NEO24-Hevesi LSC – a klub összes csapatának menetrendje, eredményei és bajnoksági meccsei
az MLSZ adatbankból (adatbank.mlsz.hu). Kimenet: data/klub.json
Futtatás: python3 scripts/build.py data/klub.json"""
import re, html, json, time, subprocess, sys, datetime

def get(url):
    for _ in range(3):
        r = subprocess.run(['curl', '-sS', '-L', '--max-time', '30', url], capture_output=True)
        if r.returncode == 0 and r.stdout:
            time.sleep(0.5)
            return r.stdout.decode('utf8', 'ignore')
        time.sleep(3)
    raise SystemExit('nem érhető el: ' + url)


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def schedule_rows(t):
    for body, arena in re.findall(r'<div class="schedule[^"]*"[^>]*>(.*?)<div class="team_sorsolas_arena">(.*?)</div>', t, re.S):
        h = re.search(r'class="home_team"><a href="[^"]*/(\d+)\.html" title="([^"]*)"', body)
        a = re.search(r'class="away_team"><a href="[^"]*/(\d+)\.html" title="([^"]*)"', body)
        if not h or not a:
            continue
        res = clean(re.search(r'class=.result-cont.[^>]*>(.*?)<div class=.away_logo', body, re.S).group(1))
        dt = clean(re.search(r'class="team_sorsolas_date">(.*?)</div>', body, re.S).group(1))
        dm = re.search(r'(\d{4})\. (\d{2})\. (\d{2})\.\s*(\d{1,2}:\d{2})?', dt)
        mu = re.search(r'href="(https://adatbank\.mlsz\.hu/match/67/\d+/\d+/(\d+)/(\d+)\.html)"', body)
        sc = re.match(r'^(\d+) - (\d+)$', res)
        yield {'hid': h.group(1), 'h': html.unescape(h.group(2)).strip(), 'aid': a.group(1), 'a': html.unescape(a.group(2)).strip(),
               'date': f'{dm.group(1)}-{dm.group(2)}-{dm.group(3)}' if dm else '', 'time': (dm.group(4) if dm else '') or '',
               'venue': clean(arena), 'hg': int(sc.group(1)) if sc else None, 'ag': int(sc.group(2)) if sc else None,
               'st': 'played' if sc else ('postponed' if 'ELMARADT' in res.upper() else 'scheduled'),
               'url': mu.group(1) if mu else None, 'round': int(mu.group(2)) if mu else None, 'mid': mu.group(3) if mu else None}



TEAMS=[ # kód, név, szervező, verseny, csapat-id, bajnokság neve, meccsidő (perc), tabella?
 ('F2','Felnőtt',10,33864,329456,'Heves Vármegyei II. osztály',120,True),
 ('F3','Felnőtt II.',10,33863,329505,'Heves Vármegyei III. osztály',120,True),
 ('KUPA','Felnőtt kupa',10,33865,329482,'Heves Vármegyei Kupa',120,False),
 ('MAKL','Hevesi LSC/Maklár',10,33865,330254,'Heves Vármegyei Kupa',120,False),
 ('U21','U21',10,33866,331316,'Heves Vármegyei I. osztály U21',120,True),
 ('U17','U17',13,34395,335818,'MLSZ Regionális U17 Alap, Középkeleti csoport',110,True),
 ('U16','U16',4,34332,334845,'MLSZ Regionális U16 Alap, Északkeleti csoport',110,True),
 ('U15','U15',10,34366,335396,'MLSZ Regionális U15 Alap, Északkeleti csoport',100,True),
 ('U14R','U14 regionális',4,34331,334830,'MLSZ Regionális U14 Alap, Északkeleti csoport',100,True),
 ('U14H','U14 Heves',10,33872,331471,'Heves Vármegyei U14 Kelet',100,True),
 ('U13R','U13 regionális',4,34330,334741,'MLSZ Regionális U13, Északi csoport',90,True),
 ('U13H','U13 Heves',10,33874,331576,'Heves Vármegyei U13 Kelet',90,True),
 ('U12','U12 regionális',4,34329,334732,'MLSZ Regionális U12, Északi csoport',90,True),
 ('NOI','Női kispályás',13,34595,337945,'Női kispályás bajnokság',60,True),
]

def run(out):
    res={'at':datetime.date.today().isoformat(),'teams':{}}
    for code,name,org,comp,tid,lname,dur,tab in TEAMS:
        fx=[]
        for r in schedule_rows(get(f'https://adatbank.mlsz.hu/club/67/{org}/{comp}/1/{tid}.html')):
            fx.append({'d':r['date'],'t':r['time'],'h':r['h'],'a':r['a'],'hid':r['hid'],'aid':r['aid'],'hg':r['hg'],'ag':r['ag'],'st':r['st'],'v':r['venue'],'r':r['round']})
        lg=[]
        if tab:
            seen={};empty=0
            for rnd in range(1,41):
                new=0
                for r in schedule_rows(get(f'https://adatbank.mlsz.hu/league/67/{org}/{comp}/{rnd}.html')):
                    k=(r['hid'],r['aid']);rec={'d':r['date'],'h':r['h'],'a':r['a'],'hid':r['hid'],'aid':r['aid'],'hg':r['hg'],'ag':r['ag'],'st':r['st']}
                    o=seen.get(k)
                    if not o: new+=1
                    if not o or (o['st']!='played' and rec['st']=='played') or (o['st']=='postponed' and rec['st']=='scheduled'): seen[k]=rec
                empty=empty+1 if new==0 else 0
                if empty>=6: break
            lg=sorted(seen.values(),key=lambda x:(x['d'],x['h']))
        res['teams'][code]={'name':name,'league':lname,'tid':str(tid),'dur':dur,'table':tab,'fixtures':fx,'leagueMatches':lg}
        n=len({m['hid'] for m in lg}|{m['aid'] for m in lg})
        print(code,len(fx),'saját meccs,',sum(f['st']=='played' for f in fx),'lejátszva | bajnokság',len(lg),'meccs',n,'csapat',file=sys.stderr)
    json.dump(res,open(out,'w'),ensure_ascii=False)

if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else 'data/klub.json')
