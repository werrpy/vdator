from dotenv import load_dotenv
import os
import re

# APIs
import discord
from discord import Emoji
from discord.utils import get

# parsers
from paste_parser import PasteParser
from media_info_parser import MediaInfoParser
from checker import Checker

# load environment variables
load_dotenv()

# environment variables
IGNORE_AFTER_LINE = os.environ.get("IGNORE_AFTER_LINE").strip()
REVIEW_CHANNELS = [x.strip() for x in os.environ.get("REVIEW_CHANNELS").split(',')]
REVIEW_REPLY_CHANNELS = [x.strip() for x in os.environ.get("REVIEW_REPLY_CHANNELS").split(',')]
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
    "Video track names\n" \
    "Movie name format\n" \
    "Video and audio track names\n" \
    "DTS-HD MA 1.0/2.0 to FLAC, LPCM 1.0/2.0 to FLAC, LPCM > 2.0 to DTS-HD MA\n" \
    "Commentary to AC-3 @ 224 kbps\n" \
    "Text muxing mode\n" \
    "Commentary track people and spellcheck```"

async def add_status_reactions(client, message, content):
  # ignore help
  if re.match(r'vdator (\d+\.)(\d+\.)(\d+) help', content):
    return
  
  # add status reactions to message based on content
  if "WARNING" not in content and "ERROR" not in content:
    await client.add_reaction(message, '✅')
  else:
    if "WARNING" in content:
      await client.add_reaction(message, '⚠')
    if "ERROR" in content:
      await client.add_reaction(message, '❌')
    
client = discord.Client()

@client.event
async def on_ready():
  print("I'm in")
  print(client.user)

@client.event
async def on_message(message):
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

  if "pastebin.com" in message.content:
    # extract url from message
    url = re.search("(?P<url>https?://[^\s]+)", message.content).group("url")
    paste_parser = PasteParser()
    bdinfo, mediainfo = paste_parser.paste(url)
    reply = "<" + url + ">" + "\n"

    try:
      # parse mediainfo
      mediainfo_parser = MediaInfoParser()
      mediainfo = mediainfo_parser.parse(mediainfo)
      checker = Checker(bdinfo, mediainfo)
      
      # check metadata
      reply += checker.check_video_track()
      reply += checker.check_movie_name()
      
      # check audio
      reply += checker.print_audio_track_names()
      reply += checker.check_audio_track_conversions()
      
      # check muxing mode
      reply += checker.check_muxing_mode()
      
      # TMDB and IMDb People API
      reply += checker.check_people()
      reply += checker.spell_check_commentary()
      
      # report
      reply += checker.display_report()
    except:
      reply += "\n[ERROR] vdator failed to parse\n"
    
    # limit reply length
    reply = reply[:int(os.environ.get("DISCORD_MSG_CHAR_LIMIT"))]
    
    if message.channel.name in BOT_CHANNELS:
      # reply in bot channel
      await client.send_message(message.channel, reply)
    elif message.channel.name in REVIEW_CHANNELS:
      # add reactions in review channel
      await add_status_reactions(client, message, reply)
        
      # and send reply to
      for ch in REVIEW_REPLY_CHANNELS:
        channel = get(message.server.channels, name=ch, type=discord.ChannelType.text)
        await client.send_message(channel, reply)
      
token = os.environ.get("DISCORD_BOT_SECRET")
client.run(token)
