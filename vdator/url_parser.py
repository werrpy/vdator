from urllib.parse import urlparse
import re, requests

class URLParser():
  def __init__(self):
    self.urls_regex = "(?P<url>https?://[^\s]+)"
    
    self.urls = {
        'pastebin.com': {
            # regex to get paste's unique identifier
            'slug_regex': 'https://pastebin.com/(.*)',
            # regex to check if it's already a raw url
            'raw_regex': 'https://pastebin.com/raw/(.*)',
            # link to raw text using the unique identifier
            'raw_url': 'https://pastebin.com/raw/{}'
        },
        'hastebin.com': {
            'slug_regex': 'https://hastebin.com/(.*)',
            'raw_regex': 'https://hastebin.com/raw/(.*)',
            'raw_url': 'https://hastebin.com/raw/{}'
        },
        'ghostbin.co': {
            'slug_regex': 'https://ghostbin.co/paste/(.*)',
            'raw_regex': 'https://ghostbin.co/paste/(.*)/raw',
            'raw_url': 'https://ghostbin.co/paste/{}/raw'
        }
    }

  def extract_supported_urls(self, text):
    # list of urls
    urls = re.findall(self.urls_regex, text)
    raw_urls = list()
    for url in urls:
      o = urlparse(url)
      # check if url is supported
      if o.hostname in self.urls:
        raw_url = self.get_raw_url(url, o.hostname, o.path)
        raw_urls.append(raw_url)
    return raw_urls
    
  def get_raw_url(self, url, hostname, path):
    # get url to raw content
    raw_url = url
    
    # check if its not already a raw url
    is_already_raw_url = re.search(self.urls[hostname]['raw_regex'], url)
    
    if not is_already_raw_url:
      slug = re.search(self.urls[hostname]['slug_regex'], url)
      if slug:
        raw_url = self.urls[hostname]['raw_url'].format(slug.group(1))
        
    return raw_url
    
  def get_paste(self, raw_url):
    r = requests.get(raw_url)
    return r.text
    
  def get_urls(self):
    return self.urls
  
