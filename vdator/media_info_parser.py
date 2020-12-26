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
    mediainfo_sections = ['general', 'video', 'audio', 'text', 'menu']
    # dictionary of lists for mediainfo data
    mediainfo = dict((k, list()) for k in mediainfo_sections)
    # starts at 0 on first loop
    section_index = dict((k, -1) for k in mediainfo_sections)
    # current mediainfo section
    curr_sect = None

    # skip blank lines
    text_list = list(filter(None, text))

    for l in text_list:
      # new section of mediainfo
      section_word = l.strip().split()[0].strip().lower()
      if section_word in mediainfo_sections:
        # track current section
        curr_sect = section_word
        # increment index
        section_index[section_word] += 1
        # store new list for chapters, and new dictionary for other sections
        mediainfo[section_word].append(list() if section_word == 'menu' else dict())
        continue

      # split mediainfo data line
      curr = l.split(' : ', 1)

      if curr_sect in ['general', 'video', 'audio', 'text'] and len(curr) >= 2:
        # assign section to dictionary
        mediainfo[curr_sect][section_index[curr_sect]][self.format_key(curr[0])] = curr[1]
      elif curr_sect == 'menu':
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
        mediainfo['menu'][section_index[curr_sect]].append(chapter)

    return mediainfo
