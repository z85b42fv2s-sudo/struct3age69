import json

with open('normativa/regulation_cache.json', encoding='utf-8') as f:
    docs = json.load(f)

matches = [d for d in docs if 'pali' in d['text'].lower() and 'staffe' in d['text'].lower()]
print(f'Found {len(matches)} pages with "pali" + "staffe"')

for d in matches[:10]:
    print(f"\nPage {d['page']} of {d['file']}")
    # Find the relevant snippet
    text = d['text'].lower()
    idx = text.find('pali')
    if idx > 0:
        snippet = d['text'][max(0, idx-50):min(len(d['text']), idx+200)]
        print(f"Snippet: ...{snippet}...")
