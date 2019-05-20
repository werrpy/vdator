from dotenv import load_dotenv
import os
from enum import Enum
from urllib.parse import urlparse
import requests
import re

# load environment variables
load_dotenv()

# environment variables
IGNORE_AFTER_LINE = os.environ.get("IGNORE_AFTER_LINE").strip()
IGNORE_AFTER_LINE_METHOD = os.environ.get("IGNORE_AFTER_LINE_METHOD").strip()
IGNORE_UNTIL_BLANK_LINE_PREFIXES = [x.strip() for x in os.environ.get("IGNORE_UNTIL_BLANK_LINE_PREFIXES").split(',')]

class BDInfoType(Enum):
  QUICK_SUMMARY = 1
  PLAYLIST_REPORT = 2

class PasteParser():

  class Section(Enum):
    QUICK_SUMMARY = 1
    MEDIAINFO = 2
    PLAYLIST_REPORT = 3
    
  class Section2(Enum):
    PLAYLIST_VIDEO = 1
    PLAYLIST_AUDIO = 2
    PLAYLIST_SUBTITLES = 3
    
  class Section3(Enum):
    PLAYLIST_INNER_VIDEO = 1
    PLAYLIST_INNER_AUDIO = 2

  def _get_paste(self, url):
    o = urlparse(url)
    link = "https://pastebin.com/raw" + o.path
    r = requests.get(link)
    return r.text

  def _parse_paste(self, text):
    bdinfo = dict()
    bdinfo['video'] = list()
    bdinfo['audio'] = list()
    bdinfo['subtitle'] = list()
    mediainfo = list()

    sect = None
    sect2 = None
    sect3 = None

    # parse bdinfo
    lines = text.splitlines()
    ignore_next_lines = False
    for l in lines:
      # break after ignore line
      if self._isIgnoreAfterLine(l):
        break
        
      if not l.strip():
        # don't ignore input after blank line
        ignore_next_lines = False
        # skip blank lines
        continue

      if ignore_next_lines:
        continue
        
      l3 = l.strip().lower()
      for x in IGNORE_UNTIL_BLANK_LINE_PREFIXES:
        if l3.startswith(x):
          ignore_next_lines = True
          break
      else:
        l2 = l.strip().lower()

        # determine current section
        if l2.startswith("quick summary"):
          sect = self.Section.QUICK_SUMMARY
          bdinfo['type'] = BDInfoType.QUICK_SUMMARY
        elif l2 == "general":
          sect = self.Section.MEDIAINFO
        elif l2.startswith("playlist report"):
          sect = self.Section.PLAYLIST_REPORT
          bdinfo['type'] = BDInfoType.PLAYLIST_REPORT

        if sect == self.Section.QUICK_SUMMARY:
          if l2.startswith("video:"):
            bdinfo['video'].append(self._format_track_name(l.split(':', 1)[1]))
          elif l2.startswith("audio:"):
            audio_name = l.split(':', 1)[1].strip()
            if "ac3 embedded" in audio_name.lower():
              audio_parts = re.split("\(ac3 embedded:", audio_name, flags=re.IGNORECASE)
              bdinfo['audio'].append(self._format_track_name(audio_parts[0]))
              bdinfo['audio'].append(self._format_track_name("Compatibility Track / Dolby Digital Audio / " + audio_parts[1].strip().rstrip(")")))
            else:
              if "(" in l:
                l = l.split("(")[0]
              l = l.strip()
              bdinfo['audio'].append(self._format_track_name(l.split(':', 1)[1]))
          elif l2.startswith("subtitle:"):
            bdinfo['subtitle'].append(self._format_track_name(l.split(':', 1)[1]))
            
        elif sect == self.Section.PLAYLIST_REPORT:
        
          if l2.startswith("video:"):
            sect2 = self.Section2.PLAYLIST_VIDEO
          elif l2.startswith("audio:"):
            sect2 = self.Section2.PLAYLIST_AUDIO
          elif l2.startswith("subtitles:"):
            sect2 = self.Section2.PLAYLIST_SUBTITLES
              
          if l2.startswith("-----"):
            if sect2 == self.Section2.PLAYLIST_VIDEO:
              sect3 = self.Section3.PLAYLIST_INNER_VIDEO
            elif sect2 == self.Section2.PLAYLIST_AUDIO:
              sect3 = self.Section3.PLAYLIST_INNER_AUDIO
          else:
            # skip tracks that start with minus sign
            if l.startswith("-"):
              continue
              
            if sect2 == self.Section2.PLAYLIST_VIDEO and sect3 == self.Section3.PLAYLIST_INNER_VIDEO:
              # format video track name with slashes
              try:
                parts = l.split()
                kbps_i = parts.index("kbps")
                before = " ".join(parts[:kbps_i - 1]).strip()
                after = " ".join(parts[kbps_i + 1:]).strip()
                l = before + " / " + parts[kbps_i - 1] + " " + parts[kbps_i] + " / " + after
                bdinfo['video'].append(self._format_track_name(l))
              except ValueError:
                continue
                
            elif sect2 == self.Section2.PLAYLIST_AUDIO and sect3 == self.Section3.PLAYLIST_INNER_AUDIO:              
              name = self._name_from_parts(l)
              bdinfo['audio'].append(self._format_track_name(name))
              
              if "ac3 embedded" in l.lower():
                audio_parts = re.split("\(ac3 embedded:", l, flags=re.IGNORECASE)
                compat_track = "Compatibility Track / Dolby Digital Audio / " + "/".join(audio_parts[1].split("/")[:-1]).strip()
                bdinfo['audio'].append(self._format_track_name(compat_track))
                
        elif sect == self.Section.MEDIAINFO:
          mediainfo.append(l)
    
    return bdinfo, mediainfo
    
  def _name_from_parts(self, l):
    l2 = l
    if "(" in l:
      l2 = l.split("(")[0]
    l2 = l2.strip()
    l_parts = l2.split(" / ")
    l_parts0 = l_parts[0].strip().split()
    l_parts1 = " / ".join(l_parts[1:]).strip()
    name = " ".join(l_parts0[:-4]) + " / " + l_parts0[-1] + " / " + l_parts1
    return name
    
  def _format_track_name(self, name):
    # remove multiple and trailing spaces
    return ' '.join(name.split()).strip()
    
  def _isIgnoreAfterLine(self, l):
    if IGNORE_AFTER_LINE_METHOD == "equals":
      if IGNORE_AFTER_LINE == l:
        return True
    elif IGNORE_AFTER_LINE_METHOD == "contains":
      if IGNORE_AFTER_LINE in l:
        return True
    return False

  def paste(self, url):
    self.url = url
    
    data = self._get_paste(self.url)
    bdinfo, mediainfo = self._parse_paste(data)
    return bdinfo, mediainfo
  