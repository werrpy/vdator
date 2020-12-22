from enum import Enum

class MediaInfoParser():

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
    mediainfo = {
      'general' : list(),
      'video' : list(),
      'audio' : list(),
      'text' : list(),
      'menu' : list()
    }

    # starts at 0 on first loop
    section_index = {
      'general' : -1,
      'video' : -1,
      'audio' : -1,
      'text' : -1,
      'menu' : -1
    }

    sect = None

    # skip blank lines
    text_list = list(filter(None, text))

    for l in text_list:
      # new section of mediainfo
      section_word = l.strip().split()[0].strip().lower()
      if section_word in ['general', 'video', 'audio', 'text', 'menu']:
        # track current section
        sect = section_word
        # increment index
        section_index[section_word] += 1
        if section_word == 'menu':
          # store new list for chapters
          mediainfo[section_word].append(list())
        else:
          # store new dictionary
          mediainfo[section_word].append(dict())
        continue

      # split mediainfo data line
      curr = l.split(' : ', 1)

      if sect in ['general', 'video', 'audio', 'text'] and len(curr) >= 2:
        # assign section to dictionary
        mediainfo[sect][section_index[sect]][self.format_key(curr[0])] = curr[1]
      elif sect == 'menu':
        # parse chapters
        chapter = dict()
        if len(curr) >= 1:
          curr[0] = curr[0].strip()
          chapter['time'] = curr[0]
        if len(curr) >= 2:
          if ':' in curr[1]:
            # chapter has a language
            curr2 = curr[1].split(':', 1)
            chapter['language'] = curr2[0].strip()
            chapter['title'] = curr2[1]
          else:
            # no language, just store title
            chapter['title'] = curr[1]
        mediainfo['menu'][section_index[sect]].append(chapter)

    return mediainfo
