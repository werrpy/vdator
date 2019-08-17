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
IGNORE_UNTIL_BLANK_LINE_PREFIXES = [x.strip() for x in os.getenv("IGNORE_UNTIL_BLANK_LINE_PREFIXES", "").strip().split(',')]

class BDInfoType(Enum):
  QUICK_SUMMARY = 1
  PLAYLIST_REPORT = 2

class PasteParser():

  class Section(Enum):
    QUICK_SUMMARY = 1
    MEDIAINFO = 2
    PLAYLIST_REPORT = 3
    EAC3TO_LOG = 4
    
  class Section2(Enum):
    PLAYLIST_VIDEO = 1
    PLAYLIST_AUDIO = 2
    PLAYLIST_SUBTITLES = 3
    
  class Section3(Enum):
    PLAYLIST_INNER_VIDEO = 1
    PLAYLIST_INNER_AUDIO = 2

  def parse(self, text):
    bdinfo = dict()
    bdinfo['video'] = list()
    bdinfo['audio'] = list()
    bdinfo['subtitle'] = list()
    mediainfo = list()
    eac3to = list()
    eac3to_index = -1

    sect = None
    sect2 = None
    sect3 = None

    # parse bdinfo
    lines = text.splitlines()
    ignore_next_lines, did_first_mediainfo, did_first_bdinfo = False, False, False
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
        
      if IGNORE_UNTIL_BLANK_LINE_PREFIXES and IGNORE_UNTIL_BLANK_LINE_PREFIXES[0] != '':
        l3 = l.strip().lower()
        for x in IGNORE_UNTIL_BLANK_LINE_PREFIXES:
          if l3.startswith(x):
            ignore_next_lines = True
            break
          
      l2 = l.strip().lower()

      # determine current section
      # limit to first bdinfo and mediainfo
      if l2.startswith("quick summary"):
        if did_first_bdinfo:
          sect = None
        else:
          sect = self.Section.QUICK_SUMMARY
          bdinfo['type'] = BDInfoType.QUICK_SUMMARY
          did_first_bdinfo = True
      elif l2.startswith("playlist report"):
        if did_first_bdinfo:
          sect = None
        else:
          sect = self.Section.PLAYLIST_REPORT
          bdinfo['type'] = BDInfoType.PLAYLIST_REPORT
          did_first_bdinfo = True
      elif l2.startswith("eac3to v"):
        sect = self.Section.EAC3TO_LOG
        eac3to.append(list())
        eac3to_index += 1
      elif l2.startswith("general"):
        if did_first_mediainfo:
          sect = None
        else:
          sect = self.Section.MEDIAINFO
          did_first_mediainfo = True

      if sect == self.Section.QUICK_SUMMARY:
        if l2.startswith("video:"):
          track_name = l.split(':', 1)[1]
          track_name = self._format_video_track_name(track_name)
          bdinfo['video'].append(track_name)
        elif l2.startswith("audio:"):
          audio_name = l.split(':', 1)[1].strip()
          if "ac3 embedded" in audio_name.lower():
            audio_parts = re.split("\(ac3 embedded:", audio_name, flags=re.IGNORECASE)
            bdinfo['audio'].append(self._format_track_name(audio_parts[0]))
            compat_track = "Compatibility Track / Dolby Digital Audio / " + audio_parts[1].strip().rstrip(")")
            bdinfo['audio'].append(self._format_track_name(compat_track))
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
              track_name = before + " / " + parts[kbps_i - 1] + " " + parts[kbps_i] + " / " + after
              track_name = self._format_video_track_name(track_name)
              bdinfo['video'].append(track_name)
            except ValueError:
              continue
              
          elif sect2 == self.Section2.PLAYLIST_AUDIO and sect3 == self.Section3.PLAYLIST_INNER_AUDIO:              
            name = self._name_from_parts(l)
            bdinfo['audio'].append(self._format_track_name(name))
            
            if "ac3 embedded" in l.lower():
              audio_parts = re.split("\(ac3 embedded:", l, flags=re.IGNORECASE)
              compat_track = "Compatibility Track / Dolby Digital Audio / " + "/".join(audio_parts[1].split("/")[:-1]).strip().rstrip(")")
              bdinfo['audio'].append(self._format_track_name(compat_track))
              
      elif sect == self.Section.MEDIAINFO:
        mediainfo.append(l)
        
      elif sect == self.Section.EAC3TO_LOG:
        if l.startswith("Done."):
          sect = None
        else:
          eac3to[eac3to_index].append(l)
    
    return bdinfo, mediainfo, eac3to
    
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
    
  def _format_video_track_name(self, name):
    track_name = self._remove_3d(name)
    track_name = self._format_track_name(track_name)
    track_name = self._video_fps_force_decimal(track_name)
    return track_name
    
  def _format_track_name(self, name):
    # remove multiple and trailing spaces
    track_name = ' '.join(name.split()).strip()
    # remove dialog normalization text
    track_name = self._remove_dialog_normalization(track_name)
    return track_name
    
  def _remove_dialog_normalization(self, name):
    if 'DN' in name.upper():
      return name.rpartition(' / ')[0]
    return name
    
  def _remove_3d(self, name):
    name = name.replace(" / Left Eye", "")
    name = name.replace(" / Right Eye", "")
    return name
    
  def _video_fps_force_decimal(self, name):
    # bdinfo force decimal instead of comma in fps
    new_name = name.split('/')
    new_name[3] = new_name[3].replace(',', '.')
    new_name = "/".join(new_name)
    return new_name
    
  def _isIgnoreAfterLine(self, l):
    if IGNORE_AFTER_LINE_METHOD == "equals":
      if IGNORE_AFTER_LINE == l:
        return True
    elif IGNORE_AFTER_LINE_METHOD == "contains":
      if IGNORE_AFTER_LINE in l:
        return True
    return False
    