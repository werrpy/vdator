# define codecs
class CodecsParser():
  """
  Define codecs
  """
  
  def __init__(self):
    # map codec names to extension
    self.video_codecs = {
      'h264/AVC' : '.h264',
      'h265/HEVC' : '.h265',
      'MPEG1' : '.m1v',
      'MPEG2' : '.m2v',
      'VC-1' : '.vc1',
    }

    self.audio_codecs = {
      'AC3' : '.ac3',
      'DTS Master Audio' : '.dtsma',
      'DTS' : '.dts',
      'E-AC3' : 'eac3',
      'FLAC Audio' : '.flac',
      'RAW/PCM' : '.pcm',
      'TrueHD/AC3' : '.thd+ac3',
    }

    self.sub_codecs = {
      'Subtitle (PGS)' : '.sup',
      'Subtitle (DVD)' : '.sup',
    }

    self.chapter_codecs = {
      'Chapters' : '.txt',
    }
    
    # map codec names used in track title to names used in file title
    self.video_codec_title_names = {
      'MPEG-2 Video' : 'MPEG-2',
      'MPEG-4 AVC Video' : 'AVC',
      'MPEG-H HEVC Video' : 'HEVC',
    }
    
    self.audio_codec_title_names = {
      'DTS Audio' : 'DTS',
      'DTS-HD Master Audio' : 'DTS-HD.MA',
      'Dolby Digital Audio' : 'DD',
      'Dolby TrueHD Audio' : 'TrueHD',
      'FLAC Audio' : 'FLAC',
    }
    
    self.scan_type_title_names = {
      'interlaced' : 'i',
      'mbaff' : 'i',
      'progressive' : 'p',
    }

    # map of all codec names to extensions
    self.codec_ext = {**self.video_codecs, **self.audio_codecs, **self.sub_codecs, **self.chapter_codecs}

  def is_video(self, codec):
    """
    Is this a video codec?
    
    Parameters
    ----------
    codec : str
      codec
      
    Returns
    -------
    True if codec is a video codec, False otherwise.
    """
    if codec in self.video_codecs:
      return True
    return False
    
  def is_audio(self, codec):
    """
    Is this an audio codec?
    
    Parameters
    ----------
    codec : str
      codec
      
    Returns
    -------
    True if codec is an audio codec, False otherwise.
    """
    if codec in self.audio_codecs:
      return True
    return False
    
  def is_sub(self, codec):
    """
    Is this a subtitle codec?
    
    Parameters
    ----------
    codec : str
      codec
      
    Returns
    -------
    True if codec is a subtitle codec, False otherwise.
    """
    if codec in self.sub_codecs:
      return True
    return False

  def is_chapter(self, codec):
    """
    Is this a chapter codec?
    
    Parameters
    ----------
    codec : str
      codec
      
    Returns
    -------
    True if codec is a chapter codec, False otherwise.
    """
    if codec in self.chapter_codecs:
      return True
    return False
    
  def get_codec_ext(self, codec):
    """
    Get codec extension. Checks if codec is valid.
    
    Parameters
    ----------
    codec : str
      codec
      
    Returns
    -------
    str codec extension
    """
    if codec not in self.codec_ext:
      return ''
    return self.codec_ext[codec]
    
  def get_video_codec_title_name(self, codec):
    """
    Get name of video codec for title. Checks if video codec is valid.
    
    Parameters
    ----------
    codec : str
      codec
      
    Returns
    -------
    str codec title name
    """
    if codec not in self.video_codec_title_names:
      return ''
    return self.video_codec_title_names[codec]
    
  def get_audio_codec_title_name(self, codec):
    """
    Get name of audio codec for title. Checks if audio codec is valid.
    
    Parameters
    ----------
    codec : str
      codec
      
    Returns
    -------
    str codec title name
    """
    if codec not in self.audio_codec_title_names:
      return ''
    return self.audio_codec_title_names[codec]
    
  def get_scan_type_title_name(self, scan_type):
    """
    Get name of video scan type for title. Checks if scan type is valid.
    
    Parameters
    ----------
    scan_type : str
      scan type
      
    Returns
    -------
    str scan type title name
    """
    if scan_type not in self.scan_type_title_names:
      return ''
    return self.scan_type_title_names[scan_type]
    