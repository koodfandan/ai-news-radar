import urllib.request, json
r = urllib.request.urlopen('http://127.0.0.1:8080/api/news?limit=10')
d = json.loads(r.read())
for it in d['items'][:8]:
    print(f"SOURCE: {it['source']}")
    t = it['title'] or ''
    print(f"TITLE: {t[:120]}")
    tz = it.get('title_zh') or ''
    print(f"TITLE_ZH: {tz[:120]}")
    sz = it.get('summary_zh') or ''
    print(f"SUMMARY_ZH: {sz[:120]}")
    c = it.get('content') or ''
    print(f"CONTENT: {c[:120]}")
    print('---')
