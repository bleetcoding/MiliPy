import json, re, sys

path = sys.argv[1]
text = re.sub(r"\x1b\[[0-9;]*m", "", open(path).read())
d = json.loads(text)
for a in d["assets"]:
    print(a["name"], a["size"], a["state"])
