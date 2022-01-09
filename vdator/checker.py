from dotenv import load_dotenv
import logging, os, re, requests, string, traceback
from pydash import has

# APIs
from iso639 import languages as iso639_languages
from langdetect import detect as langdetect_detect, DetectorFactory
import tmdbsimple as tmdb
from imdb import IMDb
import hunspell

# parsers
import nltk

# checks
from checks.mixins import SectionId, IsCommentaryTrack
from checks.remove_until_first_codec import RemoveUntilFirstCodec
from checks import *

# load environment variables
load_dotenv()

tmdb.API_KEY = os.environ.get("TMDB_API_KEY")
ia = IMDb()
logger = logging.getLogger("imdbpy")
logger.disabled = True

# download nltk resources
ntlk_list = [
    "stopwords",
    "punkt",
    "averaged_perceptron_tagger",
    "maxent_ne_chunker",
    "words",
]
for t in ntlk_list:
    nltk.download(t)

# make language detection deterministic
DetectorFactory.seed = 0

HUNSPELL_LANG = [x.strip() for x in os.environ.get("HUNSPELL_LANG").split(",")]
MISSPELLED_IGNORE_LIST = [
    x.strip() for x in os.environ.get("MISSPELLED_IGNORE_LIST").split(",")
]


class Checker(SectionId, IsCommentaryTrack):
    def __init__(self, codecs_parser, source_detector, reporter):
        self.codecs = codecs_parser
        self.remove_until_first_codec = RemoveUntilFirstCodec(codecs_parser)
        self.source_detector = source_detector
        self.reporter = reporter
        self.hobj = hunspell.HunSpell(HUNSPELL_LANG[0], HUNSPELL_LANG[1])

    def setup(self, bdinfo, mediainfo, eac3to, channel_name):
        self.bdinfo = bdinfo
        self.mediainfo = mediainfo
        self.eac3to = eac3to
        self.channel_name = channel_name
        self.source_detector.setup(bdinfo, mediainfo)

    def run_checks(self):
        reply = ""

        # check metadata
        reply += "> **Metadata**\n"
        reply += CheckMovieNameFormat(self.reporter, self.mediainfo).run()
        reply += CheckMetadataIds(self.reporter, self.mediainfo, tmdb, ia).run()
        reply += CheckFilename(
            self.reporter,
            self.source_detector,
            self.codecs,
            self.remove_until_first_codec,
            self.mediainfo,
            self.bdinfo,
            self.channel_name,
        ).run()
        reply += CheckTracksHaveLanguage(self.reporter, self.mediainfo).run()
        reply += CheckVideoLanguageMatchesFirstAudioLanguage(
            self.reporter, self.mediainfo
        ).run()
        reply += CheckMuxingMode(self.reporter, self.mediainfo).run()
        reply += CheckMKVMerge(self.reporter, self.mediainfo).run()
        reply += CheckDefaultFlag(self.reporter, self.mediainfo).run()

        # check video
        reply += "> **Video & Audio Tracks**\n"
        reply += CheckVideoTrack(
            self.reporter,
            self.source_detector,
            self.codecs,
            self.mediainfo,
            self.bdinfo,
        ).run()

        # check audio
        reply += CheckPrintAudioTrackNames(self.reporter, self.mediainfo).run()
        reply += CheckAudioTrackConversions(
            self.reporter,
            self.source_detector,
            self.remove_until_first_codec,
            self.mediainfo,
            self.bdinfo,
            self.eac3to,
        ).run()
        # check FLAC audio using mediainfo
        reply += CheckFLACAudioTracks(
            self.reporter, self.remove_until_first_codec, self.mediainfo
        ).run()

        # TMDb and IMDb People API
        reply += CheckAudioTrackPeople(
            self.reporter, self.remove_until_first_codec, self.mediainfo, tmdb, ia
        ).run()
        reply += CheckAudioTrackSpellCheck(
            self.reporter, self.hobj, self.remove_until_first_codec, self.mediainfo
        ).run()

        # check text
        reply += CheckPrintTextTracks(self.reporter, self.mediainfo).run()
        reply += CheckTextOrder(self.reporter, self.mediainfo).run()
        try:
            reply += self.check_text_default_flag()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking text track default flag"
            )

        # check chapters
        try:
            reply += self.print_chapters()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error printing chapters")
        try:
            reply += self.has_chapers()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking if should have chapters"
            )
        try:
            reply += self.chapter_language()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking chapter language"
            )
        try:
            reply += self.chapter_padding()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking chapter padding"
            )

        return reply

    def check_text_default_flag(self):
        # english subs for foreign films should be default=yes
        reply = ""

        if len(self.mediainfo["text"]) > 0:
            first_audio_language, has_english_subs, english_subs_default_yes = (
                False,
                False,
                False,
            )

            if has(self.mediainfo, "audio.0.language"):
                first_audio_language = self.mediainfo["audio"][0]["language"].lower()

            if first_audio_language != "english":
                # text tracks with language and default keys
                text_with_properties = [
                    item
                    for item in self.mediainfo["text"]
                    if ("language" in item and "default" in item)
                ]
                for item in text_with_properties:
                    if item["language"].lower() == "english":
                        has_english_subs = True
                    if item["default"].lower() == "yes":
                        english_subs_default_yes = True
                    if has_english_subs and english_subs_default_yes:
                        break

                if has_english_subs:
                    # foreign audio and has english subs. english subs should be default=yes
                    if english_subs_default_yes:
                        reply += self.reporter.print_report(
                            "correct",
                            "Foreign film, one of the English subtitles are `default=yes`",
                        )
                    else:
                        reply += self.reporter.print_report(
                            "error",
                            "Foreign film, one of the English subtitles should be `default=yes`",
                        )

        return reply

    def print_chapters(self):
        reply = ""
        if len(self.mediainfo["menu"]) > 0:
            for i, menu in enumerate(self.mediainfo["menu"]):
                reply += f"> **Chapters {i + 1}**\n"
                numbered_chapters = True
                for ch in menu:
                    for title in ch["titles"]:
                        if not re.search(
                            r"^chapter\s\d+", title["title"], re.IGNORECASE
                        ):
                            numbered_chapters = False

                if not numbered_chapters:
                    reply += "```"
                    for ch in menu:
                        if ch["time"]:
                            reply += ch["time"] + " :"
                        for title in ch["titles"]:
                            if title["language"]:
                                reply += " lang: " + title["language"]
                            if title["title"]:
                                reply += " title: " + title["title"]
                        reply += "\n"
                    reply += "```"
                else:
                    reply += self.reporter.print_report("info", "Chapters are numbered")
                if len(menu[0]["languages"]) > 0:
                    reply += (
                        "Chapter languages: `" + ", ".join(menu[0]["languages"]) + "`\n"
                    )
        else:
            reply += self.reporter.print_report("info", "No chapters")
        return reply

    def chapter_language(self):
        reply = ""

        if "menu" in self.mediainfo and len(self.mediainfo["menu"]) > 0:
            if len(self.mediainfo["menu"]) >= 1:
                for i, chapters in enumerate(self.mediainfo["menu"]):
                    if len(chapters) >= 1:
                        # chapter numbers that have an invalid language
                        invalid_ch_lang_nums = list()
                        # chapters = list of chapters
                        # [{'time': '...', 'titles': [{'language': '...', 'title': '...'}, ...], 'languages': ['...', '...']}]
                        # {'time': '...', 'titles': [{'language': '...', 'title': '...'}, ...], 'languages': ['...', '...']}
                        ch_0 = chapters[0]
                        # concatenate all chapter titles into phrases
                        # ch_0["languages"] = ['...', '...']
                        # chapter_phrases = {'de': '...', 'en': '...'}
                        chapter_phrases = {k: "" for k in ch_0["languages"]}
                        # list of detected languages with chapter languages as keys
                        # chapter_langs = {'de': [...], 'en': [...]}
                        chapter_langs = {k: list() for k in ch_0["languages"]}

                        for ch in chapters:
                            for j, lang in enumerate(ch["languages"]):
                                if lang:
                                    try:
                                        ch_lang = iso639_languages.get(part1=lang)
                                        # store chapter language
                                        chapter_langs[lang].append(ch_lang)
                                    except KeyError:
                                        # store invalid chapter number
                                        invalid_ch_lang_nums.append(str(j + 1))
                                else:
                                    # store invalid chapter number
                                    invalid_ch_lang_nums.append(str(j + 1))

                            for title in ch["titles"]:
                                # store as key "NA" if there is no chapter language set
                                if title["language"] is None:
                                    title["language"] = "NA"
                                if title["language"] not in chapter_phrases:
                                    chapter_phrases[title["language"]] = ""
                                chapter_phrases[title["language"]] += (
                                    title["title"] + "\n"
                                )

                        if len(invalid_ch_lang_nums) > 0:
                            if len(invalid_ch_lang_nums) == len(chapters):
                                reply += self.reporter.print_report(
                                    "error",
                                    f"Chapters {i + 1}: All chapters do not have a language set",
                                )
                            elif len(invalid_ch_lang_nums) > 0:
                                reply += self.reporter.print_report(
                                    "error",
                                    f"Chapters {i + 1}: The following chapters do not have a language set: `"
                                    + ", ".join(invalid_ch_lang_nums)
                                    + "`",
                                )
                            else:
                                reply += self.reporter.print_report(
                                    "correct",
                                    f"Chapters {i + 1}: All chapters have a language set",
                                )

                        for k, chapter_phrase in chapter_phrases.items():
                            if k == "NA":
                                reply += self.reporter.print_report(
                                    "error",
                                    f"Chapters {i + 1}: No chapter language set",
                                )
                                continue
                            if chapter_phrase:
                                chapter_langs[k] = list(set(chapter_langs[k]))
                                try:
                                    detected_lang = langdetect_detect(chapter_phrase)
                                    ch_detected_lang = iso639_languages.get(
                                        part1=detected_lang
                                    )
                                    if ch_detected_lang in chapter_langs[k]:
                                        reply += self.reporter.print_report(
                                            "correct",
                                            f"Chapters {i + 1}: Language matches detected language: `"
                                            + ch_detected_lang.name
                                            + "`",
                                        )
                                    else:
                                        chapter_langs_names = ", ".join(
                                            list(
                                                set(
                                                    [
                                                        detected_lang.name
                                                        for detected_lang in chapter_langs[
                                                            k
                                                        ]
                                                    ]
                                                )
                                            )
                                        )
                                        if chapter_langs_names:
                                            reply += self.reporter.print_report(
                                                "error",
                                                f"Chapters {i + 1}: Languages: `"
                                                + chapter_langs_names
                                                + "` do not match detected language: `"
                                                + ch_detected_lang.name
                                                + "`",
                                            )
                                        else:
                                            reply += self.reporter.print_report(
                                                "error",
                                                f"Chapters {i + 1}: No chapter languages. Detected language: `"
                                                + ch_detected_lang.name
                                                + "`",
                                            )
                                except KeyError:
                                    reply += self.reporter.print_report(
                                        "warning", "Could not detect chapters language"
                                    )
            else:
                reply += self.reporter.print_report(
                    "error", "Must have at least 1 chapter menu"
                )

        return reply

    def chapter_padding(self):
        reply, padded_correctly = "", True

        if "menu" in self.mediainfo and len(self.mediainfo["menu"]) > 0:
            if len(self.mediainfo["menu"]) >= 1:
                for i, menu in enumerate(self.mediainfo["menu"]):
                    padded_correctly = True
                    num_chapters = len(menu)
                    for ch in menu:
                        for title in ch["titles"]:
                            if re.search(
                                r"^chapter\s\d+", title["title"], re.IGNORECASE
                            ):
                                # numbered chapter
                                ch_num = "".join(re.findall(r"[\d]+", title["title"]))
                                if ch_num != ch_num.zfill(len(str(num_chapters))):
                                    padded_correctly = False
                                    break
                    if padded_correctly:
                        reply += self.reporter.print_report(
                            "correct", f"Chapters {i + 1}: Properly padded"
                        )
                    else:
                        reply += self.reporter.print_report(
                            "error", f"Chapters {i + 1}: Incorrect padding"
                        )

        return reply

    def has_chapers(self):
        reply, should_have_chapters = "", False
        for log in self.eac3to:
            for l in log:
                if "chapters" in l:
                    should_have_chapters = True
        if should_have_chapters:
            if len(self.mediainfo["menu"]) > 0:
                reply += self.reporter.print_report(
                    "correct", "Has chapters (from eac3to log)"
                )
            else:
                reply += self.reporter.print_report(
                    "error", "Should have chapters (from eac3to log)"
                )
        return reply
