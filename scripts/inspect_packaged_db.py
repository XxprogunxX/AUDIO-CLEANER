import sqlite3, os

db_path = r'C:\Users\javie\AppData\Roaming\AudioDuplicateDetector\music_fingerprints.db'
if not os.path.exists(db_path):
    print("DB not found:", db_path)
    import sys; sys.exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM tracks')
count = cur.fetchone()[0]
print(f'Total tracks in DB: {count}')

# Check for the test exe scan results
cur.execute("SELECT filepath, format, sha256, audio_hash FROM tracks WHERE filepath LIKE '%audioclean_exe_test2%' LIMIT 10")
rows = cur.fetchall()
print(f'Rows from exe test2 folder: {len(rows)}')
for r in rows:
    sha = r[2][:16] if r[2] else 'NULL'
    ahash = r[3][:16] if r[3] else 'NULL'
    print(f'  {os.path.basename(r[0])} | {r[1]} | sha256={sha}... | audio_hash={ahash}...')

# Also check last 5 added rows
cur.execute("SELECT filepath, format, sha256, audio_hash, last_scanned FROM tracks ORDER BY last_scanned DESC LIMIT 5")
rows2 = cur.fetchall()
print(f'\nMost recently scanned tracks:')
for r in rows2:
    sha = r[2][:16] if r[2] else 'NULL'
    ahash = r[3][:16] if r[3] else 'NULL'
    print(f'  {os.path.basename(r[0])} | {r[1]} | sha256={sha}... | scanned={r[4]}')

conn.close()
