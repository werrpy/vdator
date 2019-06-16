from urllib.parse import urlparse
import requests
import re

class URLParser():
  def __init__(self):
    self.urls_regex = "(?P<url>https?://[^\s]+)"
    
    self.urls = dict()
    self.add_url('pastebin.com', 'https://pastebin.com/raw')
    
  def add_url(self, hostname, regex, baseraw):
    """
    Add a url
    
    Parameters
    ----------
    hostname : str
      url hostname (i.e. pastebin.com)
      
    baseraw : str
      base url to raw content
    """
    
    # base url to raw content (i.e. https://pastebin.com/raw)
    self.urls[hostname] = baseraw

  def extract_supported_urls(self, text):
    # list of urls
    urls = re.findall(self.urls_regex, message.content)
    raw_urls = list()
    for url in urls:
      o = urlparse(url)
      # check if url is supported
      if o.hostname in self.urls:
        # get url to raw content
        raw_url = self.urls[o.hostname] + o.path
        raw_urls.append(raw_url)
    return raw_urls
    
  def get_paste(self, raw_url):
    r = requests.get(raw_url)
    return r.text
    
  def get_urls(self):
    return self.urls
  