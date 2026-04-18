import sqlite3
c = sqlite3.connect('ai-radar.db')
info = list(c.execute('PRAGMA table_info(news)'))
print("Table columns:")
for row in info:
    print(f"  {row[1]}: {row[2]}")
    
# Check if breaking_level exists
has_breaking_level = any(row[1] == 'breaking_level' for row in info)
print(f"\nHas breaking_level: {has_breaking_level}")

# Check a sample breaking item
r = c.execute('SELECT id, title, breaking_level FROM news WHERE is_breaking=1 LIMIT 1').fetchone()
print(f"Sample breaking item: {r}")
c.close()
