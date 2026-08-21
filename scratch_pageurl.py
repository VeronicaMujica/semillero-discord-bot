"""Temporal: ver campos de una pagina (¿trae url/permalink?). Borrar luego."""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
import informes_service as S

TOKEN = None
with open(".env", encoding="utf-8") as f:
    for line in f:
        if line.startswith("CLICKUP_API_TOKEN="):
            TOKEN = line.split("=", 1)[1].strip()
            break
HEADERS = {"Authorization": TOKEN}
BASE = f"https://api.clickup.com/api/v3/workspaces/{S.TEAM_ID}"
SEM = "8cj8yrr-4431"


def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


tree = get(f"{BASE}/docs/{SEM}/pageListing")
agosto = tree[0]
semana = agosto["pages"][0]  # primera semana
print("NODO semana (pageListing):", json.dumps(semana, ensure_ascii=False)[:300])
print("\nGET pagina semana -> claves y posibles urls:")
page = get(f"{BASE}/docs/{SEM}/pages/{semana['id']}")
for k, v in page.items():
    if k != "content":
        print(f"  {k}: {v}")
print("\nURL candidata:", f"https://app.clickup.com/{S.TEAM_ID}/docs/{SEM}/{semana['id']}")
