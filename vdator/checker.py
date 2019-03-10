from dotenv import load_dotenv
import os
import string
import re
from iso639 import languages as iso639_languages

# APIs
import tmdbsimple as tmdb
from imdb import IMDb
import hunspell

# parsers
from paste_parser import BDInfoType
import nltk
import nltk_people
from nltk_people import extract_names, ie_preprocess
from nltk.tokenize.api import StringTokenizer

# load environment variables
load_dotenv()

tmdb.API_KEY = os.environ.get("TMDB_API_KEY")
ia = IMDb()

HUNSPELL_LANG = [x.strip() for x in os.environ.get("HUNSPELL_LANG").split(',')]

class Checker():

  def __init__(self, bdinfo, mediainfo):
    self.bdinfo = bdinfo
    self.mediainfo = mediainfo
    
    self.report =	{
      "correct": 0,
      "warning": 0,
      "error": 0,
      "info": 0
    }
    
    self.hobj = hunspell.HunSpell(HUNSPELL_LANG[0], HUNSPELL_LANG[1])
    
  def print_report(self, type, content, record=True):
    if record:
      self.report[type.lower()] += 1
    return "[" + type.upper() + "] " + content
    
  def check_video_track(self):
    reply = ""
    
    if 'video' in self.bdinfo and 'video' in self.mediainfo and \
      len(self.bdinfo['video']) >= 1 and len(self.mediainfo['video']) >= 1 and \
      'title' in self.mediainfo['video'][0]:
        if self.bdinfo['video'][0] == self.mediainfo['video'][0]['title']:
          reply += self.print_report("correct", "Video track names match: ```" + self.bdinfo['video'][0] + "```")
        else:
          reply += self.print_report("error", "Video track names missmatch:\n```fix\nBDInfo: " + self.bdinfo['video'][0] + "\nMediaInfo: " + self.mediainfo['video'][0]['title'] + "```")
    else:
      reply += self.print_report("error", "Could not verify video track\n")
      
    return reply
    
  def check_movie_name(self):
    reply = ""
    
    # movie name in format "Name (Year)"    
    if 'general' in self.mediainfo and len(self.mediainfo['general']) >= 1 and \
      'movie_name' in self.mediainfo['general'][0]:
      if re.search(r'^.+\(\d{4}\)', self.mediainfo['general'][0]['movie_name']):
        reply += self.print_report("correct", "Movie name format `Name (Year)`: " + self.mediainfo['general'][0]['movie_name'] + "\n")
      else:
        reply += self.print_report("error", "Movie name does not match format `Name (Year)`: " + self.mediainfo['general'][0]['movie_name'] + "\n")
    else:
      reply += self.print_report("error", "Missing movie name\n")
      
    return reply
    
  def check_tracks_have_language(self):
    reply, is_valid = "", True
    
    n_reply, n_is_valid = self._check_tracks_have_language_section('video')
    reply += n_reply
    is_valid &= n_is_valid
    n_reply, n_is_valid = self._check_tracks_have_language_section('audio')
    reply += n_reply
    is_valid &= n_is_valid
    n_reply, n_is_valid = self._check_tracks_have_language_section('text')
    reply += n_reply
    is_valid &= n_is_valid
    
    if is_valid:
      reply += self.print_report("correct", "All tracks have a language chosen\n")
    
    return reply
    
  def _check_tracks_have_language_section(self, section):
    reply, is_valid = "", True
    for i, _ in enumerate(self.mediainfo[section]):
      if 'language' not in self.mediainfo[section][i]:
        reply += self.print_report("error", section.capitalize() + " " + self._section_id(section, i) + ": Does not have a language chosen\n")
        is_valid = False
    return reply, is_valid
    
  def check_muxing_mode(self):
    reply, is_valid = "", True
    
    n_reply, n_is_valid = self._check_muxing_mode_section('general')
    reply += n_reply
    is_valid &= n_is_valid
    n_reply, n_is_valid = self._check_muxing_mode_section('video')
    reply += n_reply
    is_valid &= n_is_valid
    n_reply, n_is_valid = self._check_muxing_mode_section('audio')
    reply += n_reply
    is_valid &= n_is_valid
    n_reply, n_is_valid = self._check_muxing_mode_section('text')
    reply += n_reply
    is_valid &= n_is_valid
    
    if is_valid:
      reply += self.print_report("correct", "All tracks do not have a muxing mode\n")
    
    return reply
    
  def _check_muxing_mode_section(self, section):
    reply, is_valid = "", True
    for i, _ in enumerate(self.mediainfo[section]):
      if "muxing_mode" in self.mediainfo[section][i]:
        reply += self.print_report("error", section.capitalize() + " #" + self.mediainfo[section][i]['id'] + " has muxing mode: " + self.mediainfo[section][i]["muxing_mode"] + "\n")
        is_valid = False
    return reply, is_valid
    
  def print_audio_track_names(self):
    reply = ""
    if len(self.mediainfo['audio']) > 0:
      reply += "Audio Track Names:\n"
      reply += "```"
      for i, _ in enumerate(self.mediainfo['audio']):
        reply += self._section_id("audio", i) + ": "
        if 'title' in self.mediainfo['audio'][i]:
          reply += self.mediainfo['audio'][i]['title'] + "\n"
      reply += "```"
    else:
      reply = self.print_report("error", "No audio tracks\n")
    return reply
    
  def check_audio_track_conversions(self):
    reply = ""
    
    if len(self.bdinfo['audio']) == len(self.mediainfo['audio']):
      for i, title in enumerate(self.bdinfo['audio']):
        bdinfo_audio_parts = re.sub(r'\s+', ' ', title).split(' / ')
        
        # determine where to split based on bdinfo type
        audio_split_index = 1 if self.bdinfo['type'] == BDInfoType.QUICK_SUMMARY else 0
        
        if self.bdinfo['type'] == BDInfoType.QUICK_SUMMARY:
          # quick summary strip language
          if '/' in title:
            title = title.split('/', 1)[1].strip()
        
        # check audio commentary
        is_commentary, commentary_reply = self._check_commentary(i)
        
        if is_commentary:
          reply += commentary_reply
        elif len(bdinfo_audio_parts) >= 3:
          if bdinfo_audio_parts[audio_split_index] == "DTS-HD Master Audio" and \
            self._is_number(bdinfo_audio_parts[audio_split_index + 1]) and float(bdinfo_audio_parts[audio_split_index + 1]) < 3:
            # DTS-HD MA 1.0 or 2.0 to FLAC
            reply += self._check_audio_conversion(i, "DTS-HD MA", "FLAC Audio")
          elif bdinfo_audio_parts[audio_split_index] == "LPCM Audio":
            if self._is_number(bdinfo_audio_parts[audio_split_index + 1]) and float(bdinfo_audio_parts[audio_split_index + 1]) < 3:
              # LPCM 1.0 or 2.0 to FLAC
              reply += self._check_audio_conversion(i, "LPCM Audio", "FLAC Audio")
            else:
              # LPCM > 2.0 to DTS-HD MA
              reply += self._check_audio_conversion(i, "LPCM Audio", "DTS-HD MA")
          else:
            if 'title' in self.mediainfo['audio'][i]:
              if title in self.mediainfo['audio'][i]['title']:
                reply += self.print_report("correct", "Audio " + self._section_id("audio", i) + ": Track names match\n")
              else:
                is_bad_audio_format = False
                if '/' in title and '/' in self.mediainfo['audio'][i]['title']:
                  bdinfo_audio_format = title.split('/')[0]
                  mediainfo_audio_format = self.mediainfo['audio'][i]['title'].split('/')[0]
                  if bdinfo_audio_format != mediainfo_audio_format:
                    is_bad_audio_format = True
                if is_bad_audio_format:
                  reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Bad conversion:\n```fix\nBDInfo: " + title + "\nMediaInfo: " + self.mediainfo['audio'][i]['title'] + "```")
                else:
                  reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Track names mismatch:\n```fix\nBDInfo: " + title + "\nMediaInfo: " + self.mediainfo['audio'][i]['title'] + "```")
            else:
              reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Missing track name\n")
    else:
      reply += self.print_report("error", "Cannot verify audio track conversions, " +
        str(len(self.bdinfo['audio'])) + " BDInfo Audio Track(s) vs " + str(len(self.mediainfo['audio'])) +
        " MediaInfo Audio Track(s).\nDid you forget to add a minus (-) sign in front of unused audio tracks in bdinfo?\n")
      
    return reply
    
  def _check_commentary(self, i):
    reply, is_commentary = "", False
    
    if self._is_commentary_track(self.mediainfo['audio'][i]['title'].lower()):
      is_commentary = True
      # determine slashes and where to split based on bdinfo type
      slash_count = 2 if self.bdinfo['type'] == BDInfoType.QUICK_SUMMARY else 1
      if self.bdinfo['audio'][i].count("/") >= slash_count:
        bdinfo_audio_format = self.bdinfo['audio'][i].split("/")[slash_count - 1].strip()
        
        if bdinfo_audio_format == 'Dolby Digital Audio':
          if 'format' in self.mediainfo['audio'][i]:
            if self.mediainfo['audio'][i]['format'] == 'AC-3':
              reply += self.print_report("correct", "Audio " + self._section_id("audio", i) + ": Commentary already AC-3\n")
            else:
              reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Commentary should be AC-3 instead of " + self.mediainfo['audio'][i]['format'] + "\n")
          else:
            reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Commentary does not have a format\n")
            
          return is_commentary, reply
      else:
        reply += self.print_report("warning", "Audio #" + self._section_id("audio", i) + ": Cannot verify commentary audio conversion\n")
        return is_commentary, reply
          
      if 'format' in self.mediainfo['audio'][i] and self.mediainfo['audio'][i]['format'] == 'AC-3':
        if 'bit_rate' in self.mediainfo['audio'][i]:
          if '224' in self.mediainfo['audio'][i]['bit_rate']:
            reply += self.print_report("correct", "Audio " + self._section_id("audio", i) + ": Commentary converted to AC-3 @ 224 kbps\n")
          else:
            reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Commentary AC-3 bitrate should be 224 kbps instead of " + self.mediainfo['audio'][i]['bit_rate'] + "\n")
        else:
          reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Commentary AC-3 does not have a bitrate\n")
      else:
        reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Commentary should be converted to AC-3\n")
          
    return is_commentary, reply
    
  def _check_audio_conversion(self, i, audio_from, audio_to):
    reply = ""
    
    # verify audio track titles
    if ' / ' not in self.bdinfo['audio'][i] or \
      'title' not in self.mediainfo['audio'][i] or ' / ' not in self.mediainfo['audio'][i]['title']:
      reply += self.print_report("warning", "Could not verify audio " + self._section_id("audio", i))
      return reply
      
    bdinfo_audio_parts = re.sub(r'\s+', ' ', self.bdinfo['audio'][i]).split(' / ')
    if len(bdinfo_audio_parts) <= 5:
      reply += self.print_report("warning", "Could not verify audio " + self._section_id("audio", i))
      return reply

    mediainfo_parts = self.mediainfo['audio'][i]['title'].split(' / ')
    if len(mediainfo_parts) <= 4:
      reply += self.print_report("warning", "Could not verify audio " + self._section_id("audio", i))
      return reply

    # verify audio conversions
    if mediainfo_parts[0] == audio_to:
      if (mediainfo_parts[1] != bdinfo_audio_parts[2]):
        reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Channel Mismatch, " + audio_from + " " + mediainfo_parts[1] + " and " + audio_to + bdinfo_audio_parts[2] + "\n")

      bdbitrate = bdinfo_audio_parts[4].strip()
      mbitrate = mediainfo_parts[3].strip()

      if bdbitrate == mbitrate:
        reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": " + audio_from + " " + bdinfo_audio_parts[2] + " to " + audio_to + " " + mediainfo_parts[1] + " same bitrate: " + str(bdbitrate) + "\n")
      else:
        reply += self.print_report("correct", "Audio " + self._section_id("audio", i) + ": " + audio_from + " " + bdinfo_audio_parts[2] + " to " + audio_to + " " + mediainfo_parts[1] + " (" + str(bdbitrate) + " to " + str(mbitrate) + ")\n")
    else:
      reply += self.print_report("error", "Audio " + self._section_id("audio", i) + " should be converted to " + audio_to + "\n")
      
    return reply
    
  def check_people(self):
    reply = ""
    
    for i, _ in enumerate(self.mediainfo['audio']):
      if 'title' in self.mediainfo['audio'][i]:
        title = self.mediainfo['audio'][i]['title']
        # check names only on commentary tracks
        if self._is_commentary_track(title):
          matched_names = list()
          names = extract_names(title)
          search = tmdb.Search()
          for n in names:
            # TMDB API
            resp = search.person(query=n)
            for s in search.results:
              if n == s['name']:
                matched_names.append(n)
            # IMDb API
            for person in ia.search_person(n):
              if n == person['name']:
                matched_names.append(n)
          matched_names = set(matched_names)
          if len(matched_names) > 0:
            reply += self.print_report("correct", "Audio " + self._section_id("audio", i) + " Matched: " + ", ".join(matched_names) + "\n")
          unmatched_names = set(names) - set(matched_names)
          if len(unmatched_names) > 0:
            reply += self.print_report("warning", "Audio " + self._section_id("audio", i) + " Unmatched: " + ", ".join(unmatched_names) + "\n")
          
    return reply
    
  def spell_check_commentary(self):
    reply = ""
    
    for i, _ in enumerate(self.mediainfo['audio']):
      # spellcheck only commentary tracks
      misspelled_words = list()
      if 'title' in self.mediainfo['audio'][i]:
        title = self.mediainfo['audio'][i]['title']
        if self._is_commentary_track(title):
          # ignore names and punctuation
          ignore_list = extract_names(title)
          ignore_list = [a for b in ignore_list for a in b.split()]
          ignore_list.extend(list(string.punctuation))
          
          # tokenize
          tokens = nltk.word_tokenize(title)
          tokens = [t for t in tokens if t not in ignore_list]
          
          for t in tokens:
            if not self.hobj.spell(t):
              # t is misspelled
              misspelled_words.append(t)
        misspelled_words = set(misspelled_words)
        if len(misspelled_words) > 0:
          reply += self.print_report("error", "Audio " + self._section_id("audio", i) + " Misspelled: " + ", ".join(misspelled_words) + "\n")
        
    return reply
    
  def print_text_tracks(self):
    reply = ""
    if len(self.mediainfo['text']) > 0:
      reply += "Text Tracks:\n"
      reply += "```"
      for i, _ in enumerate(self.mediainfo['text']):
        reply += self._section_id("text", i) + ":"
        if 'default' in self.mediainfo['text'][i]:
          reply += " default:" + self.mediainfo['text'][i]['default']
        if 'forced' in self.mediainfo['text'][i]:
          reply += " forced:" + self.mediainfo['text'][i]['forced']
        if 'language' in self.mediainfo['text'][i]:
          reply += " language:" + self.mediainfo['text'][i]['language']
        if 'title' in self.mediainfo['text'][i]:
          reply += " title: " + self.mediainfo['text'][i]['title']
        reply += "\n"
      reply += "```"
    else:
      reply = self.print_report("info", "No text tracks\n", False)
    return reply
    
  def text_order(self):
    reply = ""
    
    if len(self.mediainfo['text']) > 0:
      english_first = False
      
      # list of subtitle languages without a title
      text_langs_without_title = list()
      for i, _ in enumerate(self.mediainfo['text']):
        if 'language' in self.mediainfo['text'][i] and 'title' not in self.mediainfo['text'][i]:
          text_langs_without_title.append(self.mediainfo['text'][i]['language'].lower())
          
      # check that English subtitles without a title are first if they exist
      if len(text_langs_without_title) > 0:
        if 'english' in text_langs_without_title:
          if text_langs_without_title[0] == 'english':
            reply += self.print_report("correct", "English subtitles are first\n")
            english_first = True
          else:
            reply += self.print_report("error", "English subtitles should be first\n")
            
      # check if all other languages are in alphabetical order
      text_langs_without_title_and_english = [x for x in text_langs_without_title if x != 'english']
      if text_langs_without_title_and_english == sorted(text_langs_without_title_and_english):
        reply += self.print_report("correct", "Rest of the subtitles are in alphabetical order\n")
      else:
        if english_first:
          reply += self.print_report("error", "English subtitles are first, but rest should be in alphabetical order\n")
        else:
          reply += self.print_report("error", "English subtitles should be first, rest should be in alphabetical order\n")
    
    return reply
    
  def print_chapters(self):
    reply = ""
    if len(self.mediainfo['menu']) > 0:
      reply += "```"
      if len(self.mediainfo['menu'][0]) > 0:
        for ch in self.mediainfo['menu'][0]:
          if 'time' in ch:
            reply += ch['time']
          if 'language' in ch:
            reply += " " + ch['language']
          if 'title' in ch:
            reply += " " + ch['title']
          reply += "\n"
      reply += "```\n"
    return reply
    
  def chapter_language(self):
    reply = ""
    if len(self.mediainfo['menu']) > 0:
      for i, _ in enumerate(self.mediainfo['menu']):
        invalid_lang_list = list()
        if len(self.mediainfo['menu'][i]) > 0:
          for j, _ in enumerate(self.mediainfo['menu'][i]):
            if 'language' in self.mediainfo['menu'][i][j]:
              try:
                iso639_languages.get(alpha2=self.mediainfo['menu'][i][j]['language'])
              except KeyError:
                invalid_lang_list.append(str(j + 1))
            else:
              invalid_lang_list.append(str(j + 1))
        if len(invalid_lang_list) > 0:
          if len(invalid_lang_list) == len(self.mediainfo['menu'][i]):
            reply += self.print_report("error", "Chapters " + str(i) + ": All chapters are do not have a language set\n")
          else:
            reply += self.print_report("error", "Chapters " + str(i) + ": The following chapters do not have a language set: " + ", ".join(invalid_lang_list) + "\n")
        else:
          reply += self.print_report("correct", "Chapters " + str(i) + ": All chapters have a language set\n")
    else:
      reply += self.print_report("info", "No chapters\n")
    return reply
    
  def _is_commentary_track(self, title):
    return "commentary" in title.lower()
    
  def _section_id(self, section, i):
    reply = ""
    if 'id' in self.mediainfo[section.lower()][i]:
      reply += "#" + self.mediainfo[section.lower()][i]['id']
    else:
      reply += str(i)
    return reply
    
  def _is_number(self, s):
    try:
      float(s)
      return True
    except ValueError:
      return False
    
  def get_report(self):
    return self.report
    
  def display_report(self):
    reply = str(self.report['correct']) + " correct, " + str(self.report['warning']) + " warning"
    reply += "" if self.report['error'] == 1 else "s"
    reply += ", " + str(self.report['error']) + " error"
    reply += "" if self.report['error'] == 1 else "s"
    reply += ", and " + str(self.report['info']) + " info"
    return reply
    