from dotenv import load_dotenv
import os
import string
import re
import requests
import unicodedata
import datetime

# APIs
from iso639 import languages as iso639_languages
from langdetect import detect as langdetect_detect, DetectorFactory
import tmdbsimple as tmdb
import imdb
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

# make language detection deterministic
DetectorFactory.seed = 0

HUNSPELL_LANG = [x.strip() for x in os.environ.get("HUNSPELL_LANG").split(',')]

# used for filename
RELEASE_GROUP = os.environ.get("RELEASE_GROUP").strip()

# channels
TRAINEE_CHANNELS = [x.strip() for x in os.environ.get("TRAINEE_CHANNELS").split(',')]
INTERNAL_CHANNELS = [x.strip() for x in os.environ.get("INTERNAL_CHANNELS").split(',')]

class Checker():

  def __init__(self, bdinfo, mediainfo, codecs):
    self.bdinfo = bdinfo
    self.mediainfo = mediainfo
    self.codecs = codecs
    
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
    
    if 'video' in self.bdinfo and 'video' in self.mediainfo:
      if len(self.bdinfo['video']) != 1:
        reply += self.print_report("error", "Missing bdinfo video track\n")
        return reply
      elif len(self.mediainfo['video']) != 1:
        reply += self.print_report("error", "Missing mediainfo video track\n")
        return reply
        
      if 'title' in self.mediainfo['video'][0]:
        if self.bdinfo['video'][0] == self.mediainfo['video'][0]['title']:
          reply += self.print_report("correct", "Video track names match: ```" + self.bdinfo['video'][0] + "```")
        else:
          reply += self.print_report("error", "Video track names missmatch:\n```fix\nBDInfo: " + self.bdinfo['video'][0] + "\nMediaInfo: " + self.mediainfo['video'][0]['title'] + "```")
      else:
        reply += self.print_report("error", "Missing mediainfo video track\n")
        return reply
    else:
      reply += self.print_report("error", "Could not verify video track\n")
      
    return reply
    
  def check_movie_name(self):
    reply = ""
    
    if 'general' in self.mediainfo and len(self.mediainfo['general']) >= 1 and \
      'movie_name' in self.mediainfo['general'][0]:
      # tv show name in format "Name - S01E01"
      if re.search(r'^.+\s-\sS\d{2}E\d{2}', self.mediainfo['general'][0]['movie_name']):
        reply += self.print_report("correct", "TV show name format `Name - S01E01`: " + self.mediainfo['general'][0]['movie_name'] + "\n")
      # movie name in format "Name (Year)"
      elif re.search(r'^.+\(\d{4}\)', self.mediainfo['general'][0]['movie_name']):
        reply += self.print_report("correct", "Movie name format `Name (Year)`: " + self.mediainfo['general'][0]['movie_name'] + "\n")
      else:
        reply += self.print_report("error", "Movie name does not match format `Name (Year)`: " + self.mediainfo['general'][0]['movie_name'] + "\n")
    else:
      reply += self.print_report("error", "Missing movie name\n")
      
    return reply
    
  def check_ids(self):
    reply, name, year, imdb_movie, tmdb_movie_info, matched_imdb, matched_tmdb = "", None, None, None, None, False, False
    
    if 'general' in self.mediainfo and len(self.mediainfo['general']) >= 1 and \
      'movie_name' in self.mediainfo['general'][0]:
      movie_name = re.search(r'^(.+)\((\d{4})\)', self.mediainfo['general'][0]['movie_name'])
      if movie_name:
        name = movie_name.group(1).strip()
        year = movie_name.group(2).strip()
    
    if 'imdb' in self.mediainfo['general'][0]:
      imdb_id = ''.join(re.findall(r'[\d]+', self.mediainfo['general'][0]['imdb']))
      try:
        imdb_movie = ia.get_movie(imdb_id)
      except imdb._exceptions.IMDbParserError:
        reply += self.print_report("error", "Invalid IMDB id: `" + self.mediainfo['general'][0]['imdb'] + "`\n")
      else:
        if name == imdb_movie['title'] and year == str(imdb_movie['year']):
          reply += self.print_report("correct", "Matched IMDB name and year\n")
          matched_imdb = True
          
    if 'tmdb' in self.mediainfo['general'][0]:
      tmdb_id = ''.join(re.findall(r'[\d]+', self.mediainfo['general'][0]['tmdb']))
      tmdb_movie = tmdb.Movies(tmdb_id)
      try:
        tmdb_movie_info = tmdb_movie.info()
      except requests.exceptions.HTTPError:
        reply += self.print_report("error", "Invalid TMDB id: `" + self.mediainfo['general'][0]['tmdb'] + "`\n")
      else:
        datetime_obj = datetime.datetime.strptime(tmdb_movie_info['release_date'], '%Y-%m-%d')
        tmdb_year = str(datetime_obj.year)
        if name == tmdb_movie_info['original_title'] and year == tmdb_year:
          reply += self.print_report("correct", "Matched TMDB name and year\n")
          matched_tmdb = True
          
    if not matched_imdb and not matched_tmdb:
      if imdb_movie and 'title' in imdb_movie and 'year' in imdb_movie:
        reply += self.print_report("error", "IMDB: Name: `" + imdb_movie['title'] + "` Year: `" + str(imdb_movie['year']) + "`\n")
      if tmdb_movie_info and 'original_title' in tmdb_movie_info and tmdb_year:
        reply += self.print_report("error", "TMDB: Name: `" + tmdb_movie_info['original_title'] + "` Year: `" + tmdb_year + "`\n")
        
    return reply
    
  def check_filename(self, channel):
    reply = ""
    # construct release name
    release_name = ""
    
    if 'general' in self.mediainfo and len(self.mediainfo['general']) >= 1 and \
      'movie_name' in self.mediainfo['general'][0] and \
      'video' in self.mediainfo and len(self.mediainfo['video']) >= 1 and \
      'height' in self.mediainfo['video'][0] and \
      'scan_type' in self.mediainfo['video'][0] and len(self.mediainfo['video'][0]['scan_type']) >= 1 and \
      'format' in self.mediainfo['video'][0] and \
      'audio' in self.mediainfo and len(self.mediainfo['audio']) >= 1 and \
      'title' in self.mediainfo['audio'][0]:
      # Name.S01E01
      tv_show_name_search = re.search(r'(.+)\s-\s(S\d{2}E\d{2})', self.mediainfo['general'][0]['movie_name'])
      # Name.Year
      movie_name_search = re.search(r'(.+)\s\((\d{4})\)', self.mediainfo['general'][0]['movie_name'])
      if tv_show_name_search:
        title = self._format_filename_title(tv_show_name_search.group(1))
        season_episode = tv_show_name_search.group(2).strip()
        release_name += title + '.' + season_episode
      elif movie_name_search:
        title = self._format_filename_title(movie_name_search.group(1))
        year = movie_name_search.group(2).strip()
        release_name += title + '.' + year
      # resolution (ex. 1080p)
      height = ''.join(re.findall(r'[\d]+', self.mediainfo['video'][0]['height']))
      if height != '480':
        release_name += '.' + height
        release_name += self.codecs.get_scan_type_title_name(self.mediainfo['video'][0]['scan_type'].lower())
        # source BluRay
        release_name += '.BluRay.REMUX'
      else:
        # source DVD
        release_name += '.DVD.REMUX'
      # video format (ex. AVC)
      main_video_title = self.mediainfo['video'][0]['title'].split(' / ')
      if len(main_video_title) >= 1:
        release_name += '.' + self.codecs.get_video_codec_title_name(main_video_title[0].strip())
      main_audio_title = self.mediainfo['audio'][0]['title'].split(' / ')
      if len(main_audio_title) >= 2:
        # audio codec name for title (ex. DTS-HD.MA)
        audio_codec = main_audio_title[0].strip()
        title = self.codecs.get_audio_codec_title_name(audio_codec)
        if title:
          main_audio_title[0] = title
        else:
          reply += self.print_report("error", "No title name found for audio codec: `" + audio_codec + "`\n")
        # audio channel (ex. 5.1)
        main_audio_title[1] = main_audio_title[1].strip()
        # extract float
        main_audio_title[1] = re.search("\d+\.\d+", main_audio_title[1]).group(0)
        release_name += '.' + main_audio_title[0]
        release_name += '.' + main_audio_title[1]
      # release group
      release_name += '-'
      if channel in INTERNAL_CHANNELS:
        release_name += RELEASE_GROUP + '.mkv'
      complete_name = self.mediainfo['general'][0]['complete_name']
      if '\\' in complete_name:
        complete_name = complete_name.split('\\')[-1]
      elif '/' in complete_name:
        complete_name = complete_name.split('/')[-1]
      if channel in INTERNAL_CHANNELS and release_name == complete_name:
        reply += self.print_report("correct", "Filename: `" + complete_name + "`\n")
      elif release_name in complete_name:
        reply += self.print_report("correct", "Filename: `" + complete_name + "`\n")
      else:
        if channel not in INTERNAL_CHANNELS:
          release_name += 'GRouP.mkv'
        reply += self.print_report("error", "Filename missmatch:\n```fix\nFilename: " + complete_name + "\nExpected: " + release_name + "```")
    else:
      reply += self.print_report("error", "Cannot validate filename\n")
      
    return reply
    
  def _format_filename_title(self, title):
    title = title.strip()
    # remove diacritical marks
    title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('ASCII')
    # remove punctuation
    title = title.replace('&', 'and')
    title = ''.join([i for i in title if not i in string.punctuation])
    # force single spaces
    title = ' '.join(title.split())
    # replace spaces with dots
    title = title.replace(' ', '.')
    return title
    
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
    
  def check_video_language_matches_first_audio_language(self):
    reply = ""
    
    if 'video' not in self.mediainfo or len(self.mediainfo['video']) < 1 or \
      'language' not in self.mediainfo['video'][0]:
      reply += self.print_report("error", "Video language not set" + "\n")
      return reply
    if 'audio' not in self.mediainfo or len(self.mediainfo['audio']) < 1 or \
      'language' not in self.mediainfo['audio'][0]:
      reply += self.print_report("error", "First audio language not set" + "\n")
      return reply
    if self.mediainfo['video'][0]['language'] == self.mediainfo['audio'][0]['language']:
      reply += self.print_report("correct", "Video language matches first audio language: `" + self.mediainfo['video'][0]['language'] + "`\n")
    else:
      reply += self.print_report("error", "Video language does not match first audio language: `" + self.mediainfo['video'][0]['language'] + "` vs `" + self.mediainfo['audio'][0]['language'] + "`\n")
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
    
  def check_mkvmerge(self):
    reply = ""
    
    version_name_regex_mkvtoolnix = '"(.*)"'
    version_name_regex_mediainfo = '\'(.*)\''
    version_num_regex = '(\d+\.\d+\.\d+)'
    
    mediainfo_version_num = re.search(version_num_regex, self.mediainfo['general'][0]['writing_application'])
    if mediainfo_version_num:
      mediainfo_version_num = mediainfo_version_num.group(1)
      
    mediainfo_version_name = re.search(version_name_regex_mediainfo, self.mediainfo['general'][0]['writing_application'])
    if mediainfo_version_name:
      mediainfo_version_name = mediainfo_version_name.group(1)
    
    if not mediainfo_version_num or not mediainfo_version_name:
      reply += self.print_report("info", "Not using mkvtoolnix\n")
    else:
      r = requests.get(os.environ.get("MKVTOOLNIX_NEWS"))
      if r.status_code == 200:
        ## Version 32.0.0 "Astral Progressions" 2019-03-12
        mkvtoolnix_version_line = r.text.splitlines()[0]
        
        mkvtoolnix_version_num = re.search(version_num_regex, mkvtoolnix_version_line)
        if mkvtoolnix_version_num:
          mkvtoolnix_version_num = mkvtoolnix_version_num.group(1)
          
        mkvtoolnix_version_name = re.search(version_name_regex_mkvtoolnix, mkvtoolnix_version_line)
        if mkvtoolnix_version_name:
          mkvtoolnix_version_name = mkvtoolnix_version_name.group(1)
        
        
        if mkvtoolnix_version_num == mediainfo_version_num and mkvtoolnix_version_name == mediainfo_version_name:
          reply += self.print_report("correct", "Uses latest mkvtoolnix: `" + mediainfo_version_num + " \"" + mediainfo_version_name + "\"`\n")
        else:
          reply += self.print_report("warning", "Not using latest mkvtoolnix: `" + mediainfo_version_num + " \"" + mediainfo_version_name +
            "\"` latest is: `" + mkvtoolnix_version_num + " \"" + mkvtoolnix_version_name + "\"`\n")
    return reply
    
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
    
  def check_audio_tracks(self):
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
            reply += self._check_audio_conversion(i, "DTS-HD Master Audio", "FLAC Audio")
          elif bdinfo_audio_parts[audio_split_index] == "LPCM Audio":
            if self._is_number(bdinfo_audio_parts[audio_split_index + 1]) and float(bdinfo_audio_parts[audio_split_index + 1]) < 3:
              # LPCM 1.0 or 2.0 to FLAC
              reply += self._check_audio_conversion(i, "LPCM Audio", "FLAC Audio")
            else:
              # LPCM > 2.0 to DTS-HD MA
              reply += self._check_audio_conversion(i, "LPCM Audio", "DTS-HD Master Audio")
          else:
            if 'title' in self.mediainfo['audio'][i]:
              if title == self.mediainfo['audio'][i]['title']:
                reply += self.print_report("correct", "Audio " + self._section_id("audio", i) + ": Track names match\n")
              else:
                is_bad_audio_format = False
                if '/' in title and '/' in self.mediainfo['audio'][i]['title']:
                  bdinfo_audio_format = title.split('/')[0].strip()
                  if self.codecs.is_codec(self.mediainfo['audio'][i]['title'][0]):
                    mediainfo_audio_title = self.mediainfo['audio'][i]['title'].strip()
                  else:
                    # remove first part since its not a codec
                    mediainfo_audio_title = ' / '.join(self.mediainfo['audio'][i]['title'].split(' / ')[1:]).strip()
                  if title != mediainfo_audio_title:
                    is_bad_audio_format = True
                if is_bad_audio_format:
                  reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Bad conversion:\n```fix\nBDInfo: " + title + "\nMediaInfo: " + self.mediainfo['audio'][i]['title'] + "```")
                else:
                  reply += self.print_report("correct", "Audio " + self._section_id("audio", i) + ": Track names match\n")
            else:
              reply += self.print_report("error", "Audio " + self._section_id("audio", i) + ": Missing track name\n")
    else:
      reply += self.print_report("error", "Cannot verify audio track conversions, " +
        str(len(self.bdinfo['audio'])) + " BDInfo Audio Track(s) vs " + str(len(self.mediainfo['audio'])) +
        " MediaInfo Audio Track(s).\n")
      if len(self.bdinfo['audio']) > len(self.mediainfo['audio']):
        reply += "Did you forget to add a minus (-) sign in front of unused audio tracks in bdinfo?\n"
        
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
      reply += self.print_report("warning", "Could not verify audio " + self._section_id("audio", i) + "\n")
      return reply
      
    bdinfo_audio_parts = re.sub(r'\s+', ' ', self.bdinfo['audio'][i]).split(' / ')
    if len(bdinfo_audio_parts) <= 5:
      reply += self.print_report("warning", "Could not verify audio " + self._section_id("audio", i) + "\n")
      return reply

    mediainfo_parts = self.mediainfo['audio'][i]['title'].split(' / ')
    if len(mediainfo_parts) <= 4:
      reply += self.print_report("warning", "Could not verify audio " + self._section_id("audio", i) + "\n")
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
            reply += self.print_report("correct", "Audio " + self._section_id("audio", i) + " Matched: `" + ", ".join(matched_names) + "`\n")
          unmatched_names = set(names) - set(matched_names)
          if len(unmatched_names) > 0:
            reply += self.print_report("warning", "Audio " + self._section_id("audio", i) + " Unmatched: `" + ", ".join(unmatched_names) + "`\n")
          
    return reply
    
  def spell_check_commentary(self):
    reply = ""
    
    for i, _ in enumerate(self.mediainfo['audio']):
      # spellcheck only commentary tracks
      misspelled_words = list()
      if 'title' in self.mediainfo['audio'][i]:
        title = self.mediainfo['audio'][i]['title'].split('/')[0].strip()
        if self._is_commentary_track(title):
          # map punctuation to space
          translator = str.maketrans(string.punctuation, ' '*len(string.punctuation))
          title = title.translate(translator)
          
          # ignore names
          ignore_list = extract_names(title)
          ignore_list = [a for b in ignore_list for a in b.split()]
          
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
      reply = self.print_report("info", "No text tracks\n")
    return reply
    
  def check_text_order(self):
    reply = ""
    
    if len(self.mediainfo['text']) > 0:
      english_first = False
      has_english = False
      
      # list of subtitle languages without a title
      text_langs_without_title = list()
      for i, _ in enumerate(self.mediainfo['text']):
        if 'language' in self.mediainfo['text'][i] and 'title' not in self.mediainfo['text'][i]:
          text_langs_without_title.append(self.mediainfo['text'][i]['language'].lower())
          
      # check that English subtitles without a title are first if they exist
      if len(text_langs_without_title) > 0:
        if 'english' in text_langs_without_title:
          has_english = True
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
          reply += self.print_report("error", "Rest of the subtitles should be in alphabetical order\n")
        elif has_english:
          reply += self.print_report("error", "English subtitles should be first, rest should be in alphabetical order\n")
        else:
          reply += self.print_report("error", "Subtitles should be in alphabetical order\n")
    
    return reply
    
  def check_text_default_flag(self):
    # english subs for foreign films should be default=yes
    reply = ""
    
    if len(self.mediainfo['text']) > 0:
      first_audio_language, has_english_subs, english_subs_index = False, False, False
      
      if 'audio' in self.mediainfo and len(self.mediainfo['audio']) >= 1 and \
      'language' in self.mediainfo['audio'][0]:
        first_audio_language = self.mediainfo['audio'][0]['language'].lower()
      
      if first_audio_language != 'english':
        for i, item in enumerate(self.mediainfo['text']):
          if 'language' in item:
            if item['language'].lower() == 'english':
              has_english_subs, english_subs_index = True, i
              
        if has_english_subs:
          # foreign audio and has english subs. english subs should be default=yes
          if self.mediainfo['text'][english_subs_index]['default'].lower() == 'yes':
            reply += self.print_report("correct", "Foreign film with English subs `default=yes`\n")
          else:
            reply += self.print_report("error", "English subs on foreign film should be `default=yes`\n")
            
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
    
    if 'menu' in self.mediainfo and len(self.mediainfo['menu']) > 0:
      if len(self.mediainfo['menu']) == 1:
        for i, _ in enumerate(self.mediainfo['menu']):
          invalid_lang_list = list()
          # concatenate all chapter titles
          chapter_phrase = ""
          chapter_langs = list()
          if len(self.mediainfo['menu'][i]) > 0:
            for j, item in enumerate(self.mediainfo['menu'][i]):
              if 'language' in self.mediainfo['menu'][i][j]:
                try:
                  ch_lang = iso639_languages.get(alpha2=self.mediainfo['menu'][i][j]['language'])
                  chapter_langs.append(ch_lang)
                except KeyError:
                  invalid_lang_list.append(str(j + 1))
              else:
                invalid_lang_list.append(str(j + 1))
              if 'title' in item:
                chapter_phrase += item['title'] + "\n"
          if len(invalid_lang_list) > 0:
            if len(invalid_lang_list) == len(self.mediainfo['menu'][i]):
              reply += self.print_report("error", "All chapters do not have a language set\n")
            else:
              reply += self.print_report("error", "The following chapters do not have a language set: " + ", ".join(invalid_lang_list) + "\n")
          else:
            reply += self.print_report("correct", "All chapters have a language set\n")
          if chapter_phrase:
            chapter_langs = list(set(chapter_langs))
            try:
              lang = langdetect_detect(chapter_phrase)
              ch_lang = iso639_languages.get(alpha2=lang)
              if ch_lang in chapter_langs:
                reply += self.print_report("correct", "Chapters language matches detected language: `" + ch_lang.name + "`\n")
              else:
                chapter_langs_names = ", ".join(list(set([lang.name for lang in chapter_langs])))
                reply += self.print_report("error", "Chapters languages: `" + chapter_langs_names + "` do not match detected language: `" + ch_lang.name + "`\n")
            except KeyError:
              reply += self.print_report("warning", "Could not detect chapters language\n")
      else:
        reply += self.print_report("error", "Must have at most 1 chapter menu\n")
    else:
      reply += self.print_report("info", "No chapters\n")
      
    return reply
    
  def chapter_padding(self):
    reply, padded_correctly = "", True
    
    if 'menu' in self.mediainfo and len(self.mediainfo['menu']) > 0:
      if len(self.mediainfo['menu']) == 1:
        num_chapters = len(self.mediainfo['menu'][0])
        for i, ch in enumerate(self.mediainfo['menu'][0]):
          if re.search(r'^chapter\s\d+', ch['title'], re.IGNORECASE):
            # numbered chapter
            ch_num = ''.join(re.findall(r'[\d]+', ch['title']))
            if ch_num != ch_num.zfill(len(str(num_chapters))):
              padded_correctly = False
              break
    if padded_correctly:
      reply += self.print_report("correct", "Chapters properly padded\n")
    else:
      reply += self.print_report("error", "Incorrect chapter padding\n")
      
    return reply
    
  def has_chapers(self, eac3to):
    reply, should_have_chapters = "", False
    for log in eac3to:
      for l in log:
        if "chapters" in l:
          should_have_chapters = True
    if should_have_chapters:
      if len(self.mediainfo['menu']) > 0:
        reply += self.print_report("correct", "Has chapters\n")
      else:
        reply += self.print_report("error", "Should have chapters\n")
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
    reply = str(self.report['correct']) + " correct, "
    
    reply += str(self.report['warning']) + " warning"
    reply += "" if self.report['warning'] == 1 else "s"
    
    reply += ", " + str(self.report['error']) + " error"
    reply += "" if self.report['error'] == 1 else "s"
    
    reply += ", and " + str(self.report['info']) + " info"
    return reply
    