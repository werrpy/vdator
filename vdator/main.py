from dotenv import load_dotenv
import json, os, traceback

# APIs
import discord
from discord.utils import get

# parsers
from helpers import balanced_blockquotes, split_string
from url_parser import URLParser
from bdinfo_parser import BDInfoParser
from paste_parser import PasteParser
from media_info_parser import MediaInfoParser
from codecs_parser import CodecsParser
from source_detector import SourceDetector
from reporter import Reporter, add_status_reactions
from checker import Checker

# initialize parsers
with open("data/urls.json") as f:
    urls = json.load(f)["urls"]
    url_parser = URLParser(urls)

bdinfo_parser = BDInfoParser()
paste_parser = PasteParser(bdinfo_parser)
mediainfo_parser = MediaInfoParser()

with open("data/codecs.json") as f:
    codecs = json.load(f)
    codecs_parser = CodecsParser(codecs)

source_detector = SourceDetector()
reporter = Reporter()
checker = Checker(codecs_parser, source_detector, reporter)

# load environment variables
load_dotenv()

# environment variables
IN_GAME = os.environ.get("IN_GAME").strip()
IGNORE_AFTER_LINE = os.environ.get("IGNORE_AFTER_LINE").strip()

# channels to listen in and add reactions
REVIEW_CHANNELS = [x.strip() for x in os.environ.get("REVIEW_CHANNELS").split(",")]

# channels to send full summary to if from review channel
REVIEW_REPLY_CHANNELS = [
    x.strip() for x in os.environ.get("REVIEW_REPLY_CHANNELS").split(",")
]

# channels to listen in and post full summaries
BOT_CHANNELS = [x.strip() for x in os.environ.get("BOT_CHANNELS").split(",")]

VERSION = "1.3.0"


def print_help():
    return (
        "vdator " + VERSION + " help: "
        "I take a Pastebin link with BDInfo and MediaInfo dump."
        " I ignore all input after the line `" + IGNORE_AFTER_LINE + "`."
        " I add reactions in the following review channels: `"
        + ", ".join(REVIEW_CHANNELS)
        + "`,"
        + " I reply with full summary from review channels to: `"
        + ", ".join(REVIEW_REPLY_CHANNELS)
        + "`"
        + " and post full summaries in: `"
        + ", ".join(BOT_CHANNELS)
        + "`."
        " Add a minus (-) sign in front of unused audio tracks in BDInfo."
        " I check:```"
        "Movie/TV name format\n"
        "IMDB/TMDB ids\n"
        "Filename\n"
        "Video language matches first audio language\n"
        "No muxing mode\n"
        "Uses latest mkvtoolnix\n"
        "Video and audio track names match\n"
        "DTS-HD MA 1.0/2.0 to FLAC, LPCM 1.0/2.0 to FLAC, LPCM > 2.0 to DTS-HD MA\n"
        "Commentary to AC-3 @ 224 kbps\n"
        "Commentary track people and spellcheck\n"
        "Subtitle order\n"
        "Subtitle default flag\n"
        "Should have chapters\n"
        "Chapter languages\n"
        "Chapter padding```"
    )


client = discord.Client()


@client.event
async def on_ready():
    """
    Discord client is ready
    """
    print("I'm in")
    print(client.user)
    await client.change_presence(activity=discord.Game(name=IN_GAME))


@client.event
async def on_message(message):
    """
    Discord message event

    Parameters
    ----------
    message : discord.Message class
        discord message
    """
    # only listens in bot and review channels
    if not (
        message.channel.name in BOT_CHANNELS or message.channel.name in REVIEW_CHANNELS
    ):
        return

    # help command
    if message.content == "!help":
        reply = print_help()
        await message.channel.send(reply)
        return

    # self
    if message.author == client.user:
        # add status reactions to own messages
        await add_status_reactions(message, message.content)
        return

    supported_urls = url_parser.extract_supported_urls(message.content)

    for url in supported_urls:
        paste = url_parser.get_paste(url)
        bdinfo, mediainfo, eac3to = paste_parser.parse(paste)

        reply = "<" + url + ">" + "\n"

        try:
            # parse mediainfo
            mediainfo = mediainfo_parser.parse(mediainfo)
            # setup/reset reporter
            reporter.setup()
            # setup checker
            checker.setup(bdinfo, mediainfo, eac3to, message.channel.name)
        except:
            traceback.print_exc()
            reply += reporter.print_report("fail", "vdator failed to parse")
        else:
            try:
                reply += checker.run_checks()
            except:
                traceback.print_exc()
                reply += reporter.print_report("fail", "vdator failed to parse")

        # report
        reply += reporter.display_report()

        # split into multiple messages based on reply length
        BLOCK_QUOTES = "```"
        len_limit = int(os.environ.get("DISCORD_MSG_CHAR_LIMIT")) - len(BLOCK_QUOTES)
        replies = split_string(reply, len_limit, "\n")

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
                await message.channel.send(reply)
        elif message.channel.name in REVIEW_CHANNELS:
            # add reactions in review channel
            await add_status_reactions(message, reply)

            # and send reply to
            for ch in REVIEW_REPLY_CHANNELS:
                channel = get(
                    message.guild.channels, name=ch, type=discord.ChannelType.text
                )
                for reply in replies:
                    await channel.send(reply)


token = os.environ.get("DISCORD_BOT_SECRET")
client.run(token)
