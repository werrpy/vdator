from pydash import has

def balanced_blockquotes(my_string): 
  brackets = ['``````'] 
  while any(x in my_string for x in brackets): 
    for br in brackets: 
      my_string = my_string.replace(br, '') 
  return not my_string
  
def split_string(str, limit, sep="\n"):
  limit = int(limit)
  words = str.split(sep)
  
  if max(map(len, words)) > limit:
    # limit is too small, return original string
    return str
    
  res, part, others = [], words[0], words[1:]
  for word in others:
    if (len(sep) + len(word)) > (limit - len(part)):
      res.append(part)
      part = word
    else:
      part += sep + word
  if part:
    res.append(part)
    
  return res

def has_many(obj, base, keys):
  for key in keys:
    lookup = ''
    if base:
      lookup += base + '.'
    lookup += key
    if not has(obj, lookup):
      return False
  return True
