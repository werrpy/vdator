from dotenv import load_dotenv
import os
import re
import traceback

# APIs
import discord
from discord import Emoji
from discord.utils import get

# parsers
from helpers import balanced_blockquotes, split_string
from url_parser import URLParser
from paste_parser import PasteParser
from media_info_parser import MediaInfoParser
from codecs_parser import CodecsParser
from checker import Checker

# load environment variables
load_dotenv()

# environment variables
IN_GAME = os.environ.get("IN_GAME").strip()
IGNORE_AFTER_LINE = os.environ.get("IGNORE_AFTER_LINE").strip()

# channels to listen in and add reactions
REVIEW_CHANNELS = [x.strip() for x in os.environ.get("REVIEW_CHANNELS").split(',')]

# channels to send full summary to if from review channel
REVIEW_REPLY_CHANNELS = [x.strip() for x in os.environ.get("REVIEW_REPLY_CHANNELS").split(',')]

# channels to listen in and post full summaries
BOT_CHANNELS = [x.strip() for x in os.environ.get("BOT_CHANNELS").split(',')]

VERSION = os.environ.get("VERSION").strip()

def print_help():
  return "vdator " + VERSION + " help: " \
    "I take a Pastebin link with BDInfo and MediaInfo dump." \
    " I ignore all input after the line `" + IGNORE_AFTER_LINE + "`." \
    " I add reactions in the following review channels: `" + ", ".join(REVIEW_CHANNELS) + "`," + \
    " I reply with full summary from review channels to: `" + ", ".join(REVIEW_REPLY_CHANNELS) + "`" + \
    " and post full summaries in: `" + ", ".join(BOT_CHANNELS) + "`." \
    " Add a minus (-) sign in front of unused audio tracks in BDInfo." \
    " I check:```" \
    "Movie/TV name format\n" \
    "IMDB/TMDB ids\n" \
    "Filename\n" \
    "Video language matches first audio language\n" \
    "No muxing mode\n" \
    "Uses latest mkvtoolnix\n" \
    "Video and audio track names match\n" \
    "DTS-HD MA 1.0/2.0 to FLAC, LPCM 1.0/2.0 to FLAC, LPCM > 2.0 to DTS-HD MA\n" \
    "Commentary to AC-3 @ 224 kbps\n" \
    "Commentary track people and spellcheck\n" \
    "Subtitle order\n" \
    "Should have chapters\n" \
    "Chapter languages\n" \
    "Chapter padding```"

async def add_status_reactions(client, message, content):
  # add status reactions to message based on content
  report_re = re.search(r'(\d+)\scorrect,\s(\d+)\swarnings?,\s(\d+)\serrors?,\sand\s(\d+)\sinfo', content)
  if report_re:
    report = {
      "correct": int(report_re.group(1)),
      "warning": int(report_re.group(2)),
      "error": int(report_re.group(3)),
      "info": int(report_re.group(4))
    }
    
    if report['warning'] == 0 and report['error'] == 0:
      await client.add_reaction(message, '✅')
    else:
      if report['warning'] != 0:
        await client.add_reaction(message, '⚠')
      if report['error'] != 0:
        await client.add_reaction(message, '❌')
      
client = discord.Client()

@client.event
async def on_ready():
  print("I'm in")
  print(client.user)
  await client.change_presence(game=discord.Game(name=IN_GAME))

@client.event
async def on_message(message):
  url_parser = URLParser()
  
  # only listens in bot and review channels
  if not (message.channel.name in BOT_CHANNELS or message.channel.name in REVIEW_CHANNELS):
    return
    
  # help command
  if message.content == "!help":
    reply = print_help()
    await client.send_message(message.channel, reply)
    return
  
  # self
  if message.author == client.user:
    # add status reactions to own messages
    await add_status_reactions(client, message, message.content)
    return
    
  supported_urls = url_parser.extract_supported_urls(message.content)
  
  for url in supported_urls:
    paste_parser = PasteParser()
    paste = url_parser.get_paste(url)
    bdinfo, mediainfo, eac3to = paste_parser.parse(paste)
    
    reply = "<" + url + ">" + "\n"

    try:
      # parse mediainfo
      mediainfo_parser = MediaInfoParser()
      mediainfo = mediainfo_parser.parse(mediainfo)
      codecs = CodecsParser()
      checker = Checker(bdinfo, mediainfo, codecs)
      
      # check metadata
      reply += checker.check_movie_name()
      reply += checker.check_ids()
      
      reply += checker.check_filename(message.channel.name)
      reply += checker.check_tracks_have_language()
      reply += checker.check_video_language_matches_first_audio_language()
      reply += checker.check_muxing_mode()
      reply += checker.check_mkvmerge()
      
      # check video
      reply += checker.check_video_track()
      
      # check audio
      reply += checker.print_audio_track_names()
      reply += checker.check_audio_tracks()
      
      # TMDB and IMDb People API
      reply += checker.check_people()
      reply += checker.spell_check_commentary()
      
      # check text
      reply += checker.print_text_tracks()
      reply += checker.check_text_order()
      reply += checker.check_text_default_flag()
      
      # check chapters
      reply += checker.has_chapers(eac3to)
      reply += checker.chapter_language()
      reply += checker.chapter_padding()
      
      # report
      reply += checker.display_report()
    except:
      traceback.print_exc()
      reply += "\n[ERROR] vdator failed to parse\n"
    
    # split into multiple messages based on reply length
    BLOCK_QUOTES = "```"
    len_block_quotes = len(BLOCK_QUOTES)
    replies = split_string(reply, int(os.environ.get("DISCORD_MSG_CHAR_LIMIT")) - len_block_quotes, "\n")
    
    # preserve blockquotes
    for i, r in enumerate(replies):
      if i == len(replies) - 1:
        break
      if not balanced_blockquotes(r):
        replies[i] += BLOCK_QUOTES
        replies[i + 1] = BLOCK_QUOTES + replies[i + 1]
        
    if message.channel.name in BOT_CHANNELS:
      # reply in bot channel
      for reply in replies:
        await client.send_message(message.channel, reply)
    elif message.channel.name in REVIEW_CHANNELS:
      # add reactions in review channel
      await add_status_reactions(client, message, reply)
        
      # and send reply to
      for ch in REVIEW_REPLY_CHANNELS:
        channel = get(message.server.channels, name=ch, type=discord.ChannelType.text)
        for reply in replies:
          await client.send_message(channel, reply)
      
token = os.environ.get("DISCORD_BOT_SECRET")
client.run(token)
