"""
Experimental REST API

> python3 api.py
POST http://127.0.0.1:5000/text
    Body, raw
    [INSERT TEXT HERE]
    
{"reply":"..."}
"""

import json, os, traceback
from urllib.parse import unquote
from flask import Flask, jsonify, request
from discord_markdown.discord_markdown import convert_to_html

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
with open('data/urls.json') as f:
  urls = json.load(f)['urls']
  url_parser = URLParser(urls)

bdinfo_parser = BDInfoParser()
paste_parser = PasteParser(bdinfo_parser)
mediainfo_parser = MediaInfoParser()

with open('data/codecs.json') as f:
  codecs = json.load(f)
  codecs_parser = CodecsParser(codecs)

source_detector = SourceDetector()
reporter = Reporter()
checker = Checker(codecs_parser, source_detector, reporter)

app = Flask(__name__)

@app.route('/text', methods=['POST'])
def parse_text():
    '''
    POST http://127.0.0.1:5000/text
    Body, raw
    [INSERT TEXT HERE]
    '''

    reply = ""

    try:
        text = request.get_data().decode("utf-8")
        bdinfo, mediainfo, eac3to = paste_parser.parse(text)
    except:
        traceback.print_exc()
        reply += reporter.print_report("fail", "Failed to get paste")
    else:
        try:
            # parse mediainfo
            mediainfo = mediainfo_parser.parse(mediainfo)
        except:
            traceback.print_exc()
            reply += reporter.print_report("fail", "Mediainfo parser failed")
        else:
            # setup/reset reporter
            reporter.setup()
            try:
                # setup checker
                checker.setup(bdinfo, mediainfo, eac3to, 'remux-bot')
            except:
                traceback.print_exc()
                reply += reporter.print_report(
                    "fail", "vdator failed to setup checker"
                )
            else:
                try:
                    reply += checker.run_checks()
                except:
                    traceback.print_exc()
                    reply += reporter.print_report(
                        "fail", "vdator failed to parse"
                    )
    # report
    reply += "> **Report**\n"
    reply += reporter.display_report()
    
    # prevent infinite loop with 2 multi-line code blocks
    # https://github.com/bitjockey42/discord-markdown/issues/6
    reply_to_convert = reply.replace("```","===")
    reply_html = convert_to_html(reply_to_convert)
    
    data = {
        'discord_reply': reply,
        'html_reply': reply_html
    }

    return jsonify(data)


app.run()
