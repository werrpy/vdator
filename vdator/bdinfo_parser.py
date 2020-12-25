class BDInfoParser():

  def format_track_name(self, name):
    # remove multiple and trailing spaces
    name = ' '.join(name.split()).strip()

    # remove dialog normalization
    if 'DN' in name.upper():
      name = name.rpartition(' / ')[0]

    return name

  def format_video_track_name(self, name):
    # remove 3d
    name = name.replace(" / Left Eye", "")
    name = name.replace(" / Right Eye", "")

    name = self.format_track_name(name)

    # force decimal instead of comma in fps
    name2 = name.split('/')
    name2[3] = name2[3].replace(',', '.')
    name = "/".join(name2)

    return name
