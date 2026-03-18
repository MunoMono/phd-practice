import requests
from xml.etree import ElementTree as ET
from app.core.database import LocalSessionLocal
from sqlalchemy import text

URL = "https://archive-media.lon1.digitaloceanspaces.com/?list-type=2&max-keys=2000"


def fetch_master_counts():
    xml = requests.get(URL, timeout=30).content
    root = ET.fromstring(xml)
    counts = {}
    for c in root.findall('.//{*}Contents'):
        key = c.find('{*}Key').text
        if '/records/' not in key:
            continue
        if '/master/' in key and key.endswith('_pdf_master__v1.pdf'):
            parts = key.split('/')
            pid = parts[parts.index('records') + 1]
            counts[pid] = counts.get(pid, 0) + 1
    return counts


def main():
    counts = fetch_master_counts()
    session = LocalSessionLocal()
    pids = [row[0] for row in session.execute(text("SELECT DISTINCT pid FROM documents WHERE pid IS NOT NULL"))]
    for pid in pids:
        cnt = counts.get(pid, 0)
        session.execute(
            text(
                "UPDATE documents SET pdf_count=:cnt, doc_metadata=jsonb_set(COALESCE(doc_metadata, '{}'::jsonb), '{ml_pdf_count}', to_jsonb(CAST(:cnt AS int)), true) WHERE pid=:pid"
            ),
            {"cnt": cnt, "pid": pid},
        )
    session.commit()
    session.close()
    print({pid: counts.get(pid, 0) for pid in pids})


if __name__ == "__main__":
    main()
