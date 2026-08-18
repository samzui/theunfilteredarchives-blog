import re
def slugify(s):
 return re.sub(r"[^a-z0-9-]","",re.sub(r"\s+","-",s.lower())).strip("-")
