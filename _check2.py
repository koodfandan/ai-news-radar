import urllib.request, json
r = urllib.request.urlopen('http://127.0.0.1:8080/api/news?limit=20')
d = json.loads(r.read())
for it in d['items'][:15]:
    src = it['source']
    author = it.get('author', '')
    print(f"SOURCE: {src:35s} AUTHOR: {author}")
