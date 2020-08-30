from enum import Enum

class MediaInfoParser():

  class MediaInfoSection(Enum):
    GENERAL = 1
    VIDEO = 2
    AUDIO = 3
    TEXT = 4
    MENU = 5

  def format_key(self, key):
    # format keys into abc_def_ghi
    return key.strip()\
      .replace(" ", "_")\
      .replace("/", "_")\
      .replace("(", "")\
      .replace(")", "")\
      .replace("*", "_")\
      .replace(",", "")\
      .lower()

  def parse(self, text):
    mediainfo = dict()
    mediainfo['general'] = list()
    mediainfo['video'] = list()
    mediainfo['audio'] = list()
    mediainfo['text'] = list()
    mediainfo['menu'] = list()

    # starts at 0 on first loop
    index_general = index_video = index_audio = index_text = index_menu = -1

    sect = None

    for l in text:
      # skip blank lines
      if not l.strip():
        continue
      # determine current section of mediainfo
      section_word = l.strip().split()[0].strip().lower()
      if section_word == "general":
        index_general += 1
        sect = self.MediaInfoSection.GENERAL
        mediainfo['general'].append(dict())
        continue
      elif section_word == "video":
        index_video += 1
        sect = self.MediaInfoSection.VIDEO
        mediainfo['video'].append(dict())
        continue
      elif section_word == "audio":
        index_audio += 1
        sect = self.MediaInfoSection.AUDIO
        mediainfo['audio'].append(dict())
        continue
      elif section_word == "text":
        index_text += 1
        sect = self.MediaInfoSection.TEXT
        mediainfo['text'].append(dict())
        continue
      elif section_word == "menu":
        index_menu += 1
        sect = self.MediaInfoSection.MENU
        mediainfo['menu'].append(list())
        continue

      if sect == self.MediaInfoSection.GENERAL:
        curr = l.split(' : ', 1)
        if len(curr) < 2:
          continue
        curr[0] = self.format_key(curr[0])
        mediainfo['general'][index_general][curr[0]] = curr[1]
      elif sect == self.MediaInfoSection.VIDEO:
        curr = l.split(' : ', 1)
        if len(curr) < 2:
          continue
        curr[0] = self.format_key(curr[0])
        mediainfo['video'][index_video][curr[0]] = curr[1]
      elif sect == self.MediaInfoSection.AUDIO:
        curr = l.split(' : ', 1)
        if len(curr) < 2:
          continue
        curr[0] = self.format_key(curr[0])
        mediainfo['audio'][index_audio][curr[0]] = curr[1]
      elif sect == self.MediaInfoSection.TEXT:
        curr = l.split(' : ', 1)
        if len(curr) < 2:
          continue
        curr[0] = self.format_key(curr[0])
        mediainfo['text'][index_text][curr[0]] = curr[1]
      elif sect == self.MediaInfoSection.MENU:
        curr = l.split(' : ', 1)
        chapter = dict()
        if len(curr) >= 1:
          curr[0] = curr[0].strip()
          chapter['time'] = curr[0]
        if len(curr) >= 2:
          if ':' in curr[1]:
            curr2 = curr[1].split(':', 1)
            chapter['language'] = curr2[0].strip()
            chapter['title'] = curr2[1]
          else:
            chapter['title'] = curr[1]
        mediainfo['menu'][index_menu].append(chapter)

    return mediainfo
