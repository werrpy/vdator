from dotenv import load_dotenv
import datetime, logging, os, re, requests, string, traceback, unidecode
from pydash import has

# APIs
from iso639 import languages as iso639_languages
from langdetect import detect as langdetect_detect, DetectorFactory
import tmdbsimple as tmdb
import imdb
from imdb import IMDb
import hunspell

# parsers
from helpers import has_many, is_float, show_diff
import nltk, nltk_people
from nltk_people import extract_names

# load environment variables
load_dotenv()

tmdb.API_KEY = os.environ.get("TMDB_API_KEY")
ia = IMDb()
logger = logging.getLogger("imdbpy")
logger.disabled = True

# make language detection deterministic
DetectorFactory.seed = 0

HUNSPELL_LANG = [x.strip() for x in os.environ.get("HUNSPELL_LANG").split(",")]
MISSPELLED_IGNORE_LIST = [
    x.strip() for x in os.environ.get("MISSPELLED_IGNORE_LIST").split(",")
]

# used for filename
RELEASE_GROUP = os.environ.get("RELEASE_GROUP").strip()

# channels
TRAINEE_CHANNELS = [x.strip() for x in os.environ.get("TRAINEE_CHANNELS").split(",")]
INTERNAL_CHANNELS = [x.strip() for x in os.environ.get("INTERNAL_CHANNELS").split(",")]

# filename cuts
CUTS = [None] + [x.strip() for x in os.environ.get("FILENAME_CUTS").split(",")]

# how many years off the movie year can be. (default: 1)
MOVIE_YEAR_OFFSET = int(os.environ.get("MOVIE_YEAR_OFFSET", "1").strip())


class Checker:
    def __init__(self, codecs_parser, source_detector, reporter):
        self.codecs = codecs_parser
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
        try:
            reply += self.check_movie_name_format()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error parsing movie name")
        try:
            reply += self.check_ids()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error parsing IMDb/TMDb ids")

        try:
            reply += self.check_filename()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error checking filename")
        try:
            reply += self.check_tracks_have_language()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error checking filename")
        try:
            reply += self.check_video_language_matches_first_audio_language()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail",
                "Error checking that video language matches first audio language",
            )
        try:
            reply += self.check_muxing_mode()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error checking muxing mode")
        try:
            reply += self.check_mkvmerge(os.environ.get("MKVMERGE_VERSION"))
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking mkvtoolnix version"
            )
        try:
            reply += self.check_default_flag()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error checking default flag")

        # check video
        reply += "> **Video & Audio Tracks**\n"
        try:
            reply += self.check_video_track()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking video track name"
            )

        # check audio
        try:
            reply += self.print_audio_track_names()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error printing audio track names"
            )
        try:
            reply += self.check_audio_tracks()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error checking audio tracks")
        # check FLAC audio using mediainfo
        try:
            reply += self.check_flac_audio_tracks()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking FLAC audio tracks"
            )

        # TMDb and IMDb People API
        try:
            reply += self.check_people()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking IMDb/TMDb people"
            )
        try:
            reply += self.spell_check_track_name()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error spell checking track names"
            )

        # check text
        try:
            reply += self.print_text_tracks()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report("fail", "Error printing text tracks")
        try:
            reply += self.check_text_order()
        except:
            traceback.print_exc()
            reply += self.reporter.print_report(
                "fail", "Error checking text track order"
            )
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

    def check_video_track(self):
        reply = ""

        if (
            has_many(
                self.mediainfo,
                "video.0",
                [
                    "format",
                    "format_version",
                    "bit_rate",
                    "height",
                    "scan_type",
                    "frame_rate",
                    "display_aspect_ratio",
                    "title",
                ],
            )
            and self.source_detector.is_dvd()
        ):
            # dvd video title from mediainfo
            video_title = self._dvd_video_title_from_mediainfo()
            mediainfo_title = self.mediainfo["video"][0]["title"]

            if mediainfo_title == video_title:
                reply += self.reporter.print_report(
                    "correct",
                    "Video track names match: ```" + mediainfo_title + "```",
                    new_line=False,
                )
            else:
                reply += self.reporter.print_report(
                    "error",
                    "Video track names missmatch:\n```fix\nExpected: "
                    + video_title
                    + "\nMediaInfo: "
                    + mediainfo_title
                    + "```",
                    new_line=False,
                )
                reply += show_diff(mediainfo_title, video_title)

        elif has(self.bdinfo, "video") and has(self.mediainfo, "video"):
            if len(self.bdinfo["video"]) < 1:
                reply += self.reporter.print_report(
                    "error", "Missing bdinfo video track"
                )
                return reply
            elif len(self.mediainfo["video"]) < 1:
                reply += self.reporter.print_report(
                    "error", "Missing mediainfo video track"
                )
                return reply

            if has(self.mediainfo, "video.0.title") and has(self.bdinfo, "video.0"):
                mediainfo_video_title = self.mediainfo["video"][0]["title"]
                bdinfo_video_title = self.bdinfo["video"][0]

                # 1080i @ 25fps is actually progressive
                reply += self._actually_progressive()

                bitrate_search = re.search(r"(\d+\.\d+)\skbps", mediainfo_video_title)
                if bitrate_search:
                    # if mediainfo has a decimal kbps bitrate, use it in the bdinfo for comparison
                    percise_bitrate = bitrate_search.group(1)
                    percise_kbps = percise_bitrate + " kbps"
                    bdinfo_video_title = re.sub(
                        r"(\d+)\skbps", percise_kbps, bdinfo_video_title
                    )
                if self.source_detector.is_dv() and mediainfo_video_title.startswith(
                    bdinfo_video_title
                ):
                    # if source is dolby vision, only check that the first part of mediainfo video title
                    # matches bdinfo video title. Up to BT.2020, i.e. Dolby Vision FEL is not checked
                    reply += self.reporter.print_report(
                        "correct",
                        "Video track names match: ```" + mediainfo_video_title + "```",
                        new_line=False,
                    )
                elif bdinfo_video_title == mediainfo_video_title:
                    reply += self.reporter.print_report(
                        "correct",
                        "Video track names match: ```" + bdinfo_video_title + "```",
                        new_line=False,
                    )
                else:
                    reply += self.reporter.print_report(
                        "error",
                        "Video track names missmatch:\n```fix\nBDInfo: "
                        + bdinfo_video_title
                        + "\nMediaInfo: "
                        + mediainfo_video_title
                        + "```",
                        new_line=False,
                    )
                    reply += show_diff(mediainfo_video_title, bdinfo_video_title)
            else:
                reply += self.reporter.print_report(
                    "error", "Missing mediainfo video track"
                )
                return reply
        else:
            reply += self.reporter.print_report("error", "Could not verify video track")

        return reply

    def _dvd_video_title_from_mediainfo(self):
        # dictionary existence already checked

        video_title = ""
        # MPEG-
        video_title += self.mediainfo["video"][0]["format"].split()[0] + "-"

        # 1
        video_title += "".join(
            re.findall(r"[\d]+", self.mediainfo["video"][0]["format_version"])
        )
        video_title += " Video / "

        # bitrate
        video_title += (
            "".join(re.findall(r"[\d]+", self.mediainfo["video"][0]["bit_rate"]))
            + " kbps"
        )
        video_title += " / "

        # height
        video_title += "".join(
            re.findall(r"[\d]+", self.mediainfo["video"][0]["height"])
        )

        # scan type
        (scan_type, _) = self.codecs.get_scan_type_title_name(
            self.mediainfo["video"][0]["scan_type"].lower(), 0
        )
        video_title += scan_type
        video_title += " / "

        # fps
        video_fps = float(
            "".join(re.findall(r"\d+\.\d+", self.mediainfo["video"][0]["frame_rate"]))
        )
        if video_fps.is_integer():
            video_fps = int(video_fps)
        video_title += str(video_fps) + " fps / "

        # aspect ratio
        video_title += self.mediainfo["video"][0]["display_aspect_ratio"]

        return video_title

    def _actually_progressive(self):
        # dictionary existence already checked

        reply = ""

        bdinfo_video_title = self.bdinfo["video"][0]
        bdinfo_video_parts = bdinfo_video_title.split(" / ")

        if len(bdinfo_video_parts) >= 3:
            scan_type = bdinfo_video_parts[2].strip()[-1].lower()
            video_fps = float(
                "".join(
                    re.findall(r"\d*\.\d+|\d+", bdinfo_video_parts[3].strip().lower())
                )
            )
            (_, actually_progressive) = self.codecs.get_scan_type_title_name(
                scan_type, video_fps
            )
            if actually_progressive:
                reply += self.reporter.print_report(
                    "info", "Note: 1080i @ 25fps is actually progressive"
                )

        return reply

    def check_movie_name_format(self):
        reply = ""

        # is it a movie or tv show?
        is_movie = self._is_movie()

        if has(self.mediainfo, "general.0.movie_name"):
            if is_movie:
                # movie name in format "Name (Year)"
                if re.search(
                    r"^.+\(\d{4}\)$", self.mediainfo["general"][0]["movie_name"]
                ):
                    reply += self.reporter.print_report(
                        "correct",
                        "Movie name format `Name (Year)`: `"
                        + self.mediainfo["general"][0]["movie_name"]
                        + "`",
                    )
                else:
                    reply += self.reporter.print_report(
                        "error",
                        "Movie name does not match format `Name (Year)`: `"
                        + self.mediainfo["general"][0]["movie_name"]
                        + "`",
                    )
                    reply += self._movie_name_extra_space(
                        self.mediainfo["general"][0]["movie_name"]
                    )
            else:
                # tv show name in format "Name - S01E01" or "Name - S01E01E02"
                if re.search(
                    r"^.+\s-\sS\d{2}(E\d{2})+.*$",
                    self.mediainfo["general"][0]["movie_name"],
                ):
                    reply += self.reporter.print_report(
                        "correct",
                        "TV show name format `Name - S01E01`: `"
                        + self.mediainfo["general"][0]["movie_name"]
                        + "`",
                    )
                else:
                    reply += self.reporter.print_report(
                        "error",
                        "TV show name does not match format `Name - S01E01`: `"
                        + self.mediainfo["general"][0]["movie_name"]
                        + "`",
                    )
                    reply += self._movie_name_extra_space(
                        self.mediainfo["general"][0]["movie_name"]
                    )
        else:
            reply += self.reporter.print_report("error", "Missing movie name")

        return reply

    def _movie_name_extra_space(self, movie_name):
        reply = ""

        if movie_name.startswith(" "):
            reply += self.reporter.print_report(
                "error", "Movie name starts with an extra space!"
            )

        if movie_name.endswith(" "):
            reply += self.reporter.print_report(
                "error", "Movie name ends with an extra space!"
            )

        return reply

    # returns True if its a movie, False if tv show
    def _is_movie(self):
        # is it a movie or tv show? assume movie
        is_movie = True
        determined_movie_or_tv = False

        if has(self.mediainfo, "general.0.tmdb"):
            if self.mediainfo["general"][0]["tmdb"].startswith("movie/"):
                is_movie = True
                determined_movie_or_tv = True
            elif self.mediainfo["general"][0]["tmdb"].startswith("tv/"):
                is_movie = False
                determined_movie_or_tv = True

        if not determined_movie_or_tv:
            if has(self.mediainfo, "general.0.movie_name"):
                # tv show name in format "Name - S01E01" or "Name - S01E01E02"
                is_tv = re.search(
                    r"^.+\s-\sS\d{2}(E\d{2})+.*$",
                    self.mediainfo["general"][0]["movie_name"],
                )
                if is_tv:
                    is_movie = not (is_tv)
        return is_movie

    def check_ids(self):
        reply = ""

        imdb_movie, tmdb_info, tmdb_year = None, None, None

        movie_data = {"name": None, "year": None}

        matched = {
            "imdb_title": False,
            "imdb_year": False,
            "tmdb_title": False,
            "tmdb_year": False,
            # matched movie title/year with either imdb or tmdb
            "title": False,
            "year": False,
            "title_replied": False,
            "year_replied": False,
        }

        # is it a movie or tv show?
        is_movie = self._is_movie()

        # extract movie name and year or tv show name
        if has(self.mediainfo, "general.0.movie_name"):
            if is_movie:
                # movie
                movie_name = re.search(
                    r"^(.+)\((\d{4})\)", self.mediainfo["general"][0]["movie_name"]
                )
                if movie_name:
                    movie_data["name"] = movie_name.group(1).strip()
                    movie_data["year"] = movie_name.group(2).strip()
            else:
                # tv show
                tv_show_name = re.search(
                    r"^(.+)\s-\s.+\s-\s.+", self.mediainfo["general"][0]["movie_name"]
                )
                if tv_show_name:
                    movie_data["name"] = tv_show_name.group(1).strip()

        if has(self.mediainfo, "general.0.imdb"):
            imdb_id = "".join(
                re.findall(r"[\d]+", self.mediainfo["general"][0]["imdb"])
            )
            try:
                imdb_movie = ia.get_movie(imdb_id)
            except imdb._exceptions.IMDbParserError:
                reply += self.reporter.print_report(
                    "error",
                    "Invalid IMDb id: `" + self.mediainfo["general"][0]["imdb"] + "`",
                )
            except:
                # imdb._exceptions.IMDbDataAccessError
                reply += self.reporter.print_report(
                    "info",
                    "Failed to get IMDb movie data for id: `"
                    + self.mediainfo["general"][0]["imdb"]
                    + "`",
                )
            else:
                # force single space in movie name
                imdb_movie["title"] = re.sub(r"\s+", " ", imdb_movie["title"])
                matched["imdb_title"] = movie_data["name"] == imdb_movie["title"]
                if is_movie:
                    matched["imdb_year"] = self._year_range(
                        imdb_movie["year"], movie_data["year"]
                    )

        if has(self.mediainfo, "general.0.tmdb"):
            tmdb_id = "".join(
                re.findall(r"[\d]+", self.mediainfo["general"][0]["tmdb"])
            )
            # movie or tv show
            tmdb_data = tmdb.Movies(tmdb_id) if is_movie else tmdb.TV(tmdb_id)

            try:
                tmdb_info = tmdb_data.info()
                # force single space in movie name
                if "title" in tmdb_info:
                    tmdb_info["title"] = re.sub(r"\s+", " ", tmdb_info["title"])
            except:
                reply += self.reporter.print_report(
                    "info",
                    "Failed to get TMDb data for id: `"
                    + self.mediainfo["general"][0]["tmdb"]
                    + "`",
                )
            else:
                if is_movie:
                    # movie
                    if "release_date" in tmdb_info and tmdb_info["release_date"]:
                        datetime_obj = datetime.datetime.strptime(
                            tmdb_info["release_date"], "%Y-%m-%d"
                        )
                        tmdb_year = str(datetime_obj.year)
                    # tmdb_info["original_title"] is original title
                    # tmdb_info["title"] is the translated title in whatever language you're requesting
                    matched["tmdb_title"] = (
                        "title" in tmdb_info
                        and movie_data["name"] == tmdb_info["title"]
                    )
                    matched["tmdb_year"] = tmdb_year and self._year_range(
                        tmdb_year, movie_data["year"]
                    )
                else:
                    # tv show
                    matched["tmdb_title"] = (
                        "title" in tmdb_info
                        and movie_data["name"] == tmdb_info["title"]
                    )

        # matched title/year with either imdb or tmdb
        matched["title"] = matched["imdb_title"] or matched["tmdb_title"]
        matched["year"] = matched["imdb_year"] or matched["tmdb_year"]

        if has(self.mediainfo, "general.0.imdb") or has(
            self.mediainfo, "general.0.tmdb"
        ):
            if is_movie:
                # movie
                if matched["title"] and matched["year"]:
                    reply += self.reporter.print_report(
                        "correct", "Matched movie name and year with IMDb/TMDb"
                    )
                else:
                    if matched["title"]:
                        reply += self.reporter.print_report(
                            "correct", "Matched movie name with IMDb/TMDb"
                        )
                    else:
                        if imdb_movie and "title" in imdb_movie and imdb_movie["title"]:
                            reply += self.reporter.print_report(
                                "error", "IMDb: Name: `" + imdb_movie["title"] + "`"
                            )
                            if movie_data["name"]:
                                reply += show_diff(
                                    movie_data["name"], imdb_movie["title"]
                                )
                            matched["title_replied"] = True
                        # tmdb_info["original_title"] is original title
                        # tmdb_info["title"] is the translated title in whatever language you're requesting
                        if tmdb_info and "title" in tmdb_info and tmdb_info["title"]:
                            reply += self.reporter.print_report(
                                "error", "TMDb: Name: `" + tmdb_info["title"] + "`"
                            )
                            if movie_data["name"]:
                                reply += show_diff(
                                    movie_data["name"], tmdb_info["title"]
                                )
                            matched["title_replied"] = True
                        if not matched["title_replied"]:
                            reply += self.reporter.print_report(
                                "error", "Failed to match movie name with IMDb/TMDb"
                            )

                    if matched["year"]:
                        reply += self.reporter.print_report(
                            "correct", "Matched movie year with IMDb/TMDb"
                        )
                    else:
                        if imdb_movie and "year" in imdb_movie:
                            reply += self.reporter.print_report(
                                "error", "IMDb: Year: `" + str(imdb_movie["year"]) + "`"
                            )
                            matched["year_replied"] = True
                        if tmdb_year:
                            reply += self.reporter.print_report(
                                "error", "TMDb: Year: `" + str(tmdb_year) + "`"
                            )
                            matched["year_replied"] = True
                        if not matched["year_replied"]:
                            reply += self.reporter.print_report(
                                "error", "Failed to match movie year with IMDb/TMDb"
                            )
            else:
                # tv show
                if matched["title"]:
                    reply += self.reporter.print_report(
                        "correct", "Matched tv show name with IMDb/TMDb"
                    )
                else:
                    if imdb_movie and "title" in imdb_movie:
                        reply += self.reporter.print_report(
                            "error", "IMDb: Name: `" + imdb_movie["title"] + "`"
                        )
                        matched["title_replied"] = True
                    if tmdb_info and "name" in tmdb_info:
                        reply += self.reporter.print_report(
                            "error", "TMDb: Name: `" + tmdb_info["name"] + "`"
                        )
                        matched["title_replied"] = True
                    if not matched["title_replied"]:
                        reply += self.reporter.print_report(
                            "error", "Failed to match tv show name with IMDb/TMDb"
                        )

        return reply

    def _year_range(self, year, test_year, offset=MOVIE_YEAR_OFFSET):
        # self._year_range(year, test_year)
        # example: with offset = 1, and year = 2004, test_year can be between 2003 and 2005 inclusive
        # 2002 in range(2004 - 1, (2004 + 1) + 1) False
        # 2003 in range(2004 - 1, (2004 + 1) + 1) True
        # 2004 in range(2004 - 1, (2004 + 1) + 1) True
        # 2005 in range(2004 - 1, (2004 + 1) + 1) True
        # 2006 in range(2004 - 1, (2004 + 1) + 1) False
        year = int(year)
        test_year = int(test_year)
        return test_year in range(year - offset, (year + offset) + 1)

    def _construct_release_name(self, reply, cut=None, hybird=False, repack=False):
        release_name = ""

        if not self.source_detector.is_dvd():
            # scan type must come from bdinfo
            bdinfo_video_parts = self.bdinfo["video"][0].split(" / ")
            scan_type = bdinfo_video_parts[2].strip()[-1].lower()

        if has_many(self.mediainfo, "video.0", ["height", "title"]) and has(
            self.mediainfo, "audio.0.title"
        ):
            # Name.S01E01 or Name.S01E01E02
            tv_show_name_search = re.search(
                r"(.+)\s-\s(S\d{2}(E\d{2})+)",
                self.mediainfo["general"][0]["movie_name"],
            )
            # Name.Year
            movie_name_search = re.search(
                r"(.+)\s\((\d{4})\)", self.mediainfo["general"][0]["movie_name"]
            )
            if tv_show_name_search:
                title = self._format_filename_title(tv_show_name_search.group(1))
                season_episode = tv_show_name_search.group(2).strip()
                release_name += title + "." + season_episode
            elif movie_name_search:
                title = self._format_filename_title(movie_name_search.group(1))
                year = movie_name_search.group(2).strip()
                release_name += title + "." + year
            else:
                release_name += self._format_filename_title(
                    self.mediainfo["general"][0]["movie_name"]
                )

            # with or without hybrid
            if hybird:
                release_name += ".Hybrid"

            # with or without repack
            if repack:
                release_name += ".REPACK"

            # check cuts here
            if cut is not None:
                release_name += "." + cut

            # resolution (ex. 1080p)
            height = "".join(re.findall(r"[\d]+", self.mediainfo["video"][0]["height"]))

            if self.source_detector.is_dvd():
                # source DVD
                if "standard" in self.mediainfo["video"][0]:
                    release_name += "." + self.mediainfo["video"][0]["standard"]
                release_name += ".DVD.REMUX"
            elif self.source_detector.is_uhd():
                # source UHD BluRay
                release_name += "." + height
                release_name += scan_type
                release_name += ".UHD.BluRay.REMUX"
                # Dolby Vision (DV)
                if self.source_detector.is_dv():
                    release_name += ".DV"
                # SDR/HDR
                if self.mediainfo["video"][0]["color_primaries"] == "BT.2020":
                    release_name += ".HDR"
                else:
                    release_name += ".SDR"
            else:
                # source HD BluRay
                release_name += "." + height
                release_name += scan_type
                release_name += ".BluRay.REMUX"

            # video format (ex. AVC)
            main_video_title = self.mediainfo["video"][0]["title"].split(" / ")
            if len(main_video_title) >= 1:
                release_name += "." + self.codecs.get_video_codec_title_name(
                    main_video_title[0].strip()
                )

            main_audio_title = self.mediainfo["audio"][0]["title"]
            (
                main_audio_title,
                _,
                _,
            ) = self._remove_until_first_codec(main_audio_title)
            main_audio_title_parts = main_audio_title.split(" / ")

            audio_codec_title, main_audio_channels = None, None

            # get main audio codec
            if len(main_audio_title) > 0:
                main_audio_codec = main_audio_title_parts[0]
                if self.codecs.is_audio_title(main_audio_codec):
                    audio_codec_title = self.codecs.get_audio_codec_title_name(
                        main_audio_codec
                    )

            # get main audio channels
            if len(main_audio_title) > 1:
                main_audio_channels = main_audio_title_parts[1]
                search_channel_atmos = re.search(
                    r"(\d.\d)\+\d+\sobjects", main_audio_channels
                )
                if search_channel_atmos:
                    main_audio_channels = search_channel_atmos.group(1)

            if (
                audio_codec_title
                and main_audio_channels
                and is_float(main_audio_channels)
            ):
                # have main audio codec and channels
                if audio_codec_title == "TrueHD.Atmos":
                    # atmos channel
                    release_name += ".TrueHD." + main_audio_channels + ".Atmos"
                else:
                    release_name += "." + audio_codec_title + "." + main_audio_channels

            # release group
            release_name += "-"
            if self.channel_name in INTERNAL_CHANNELS:
                release_name += RELEASE_GROUP + ".mkv"

        return release_name

    def _partial_match(self, possible_names, name):
        for n in possible_names:
            if n in name:
                return True
        return False

    def check_filename(self):
        reply = ""

        if has_many(self.mediainfo, "general.0", ["movie_name", "complete_name"]):
            complete_name = self.mediainfo["general"][0]["complete_name"]
            if "\\" in complete_name:
                complete_name = complete_name.split("\\")[-1]
            elif "/" in complete_name:
                complete_name = complete_name.split("/")[-1]

            # possible release names
            complete_name_lc = complete_name.lower()
            possible_release_names = [
                self._construct_release_name(
                    reply,
                    cut,
                    hybird=("hybrid" in complete_name_lc),
                    repack=("repack" in complete_name_lc),
                )
                for cut in CUTS
            ]

            if (
                self.channel_name in INTERNAL_CHANNELS
                and complete_name in possible_release_names
            ):
                reply += self.reporter.print_report(
                    "correct", "Filename: `" + complete_name + "`"
                )
            elif self._partial_match(possible_release_names, complete_name):
                reply += self.reporter.print_report(
                    "correct", "Filename: `" + complete_name + "`"
                )
            else:
                expected_release_name = possible_release_names[0]

                # pick the expected release name with the proper cut
                for i, cut in enumerate(CUTS[1:]):
                    if cut in complete_name:
                        expected_release_name = possible_release_names[i + 1]

                if self.channel_name not in INTERNAL_CHANNELS:
                    expected_release_name += "GRouP.mkv"

                reply += self.reporter.print_report(
                    "error",
                    "Filename missmatch:\n```fix\nFilename: "
                    + complete_name
                    + "\nExpected: "
                    + expected_release_name
                    + "```",
                    new_line=False,
                )
                reply += show_diff(complete_name, expected_release_name)
        else:
            reply += self.reporter.print_report("error", "Cannot validate filename")

        return reply

    def _format_filename_title(self, title):
        title = title.strip()
        # remove accents
        title = unidecode.unidecode(title)
        # remove punctuation
        title = title.replace("&", "and")
        title = "".join([i for i in title if not i in string.punctuation or i == "."])
        title = title.replace(":", ".")
        # replace spaces with dots
        title = title.replace(" ", ".")
        # force single dots
        title = re.sub(r"\.+", ".", title)
        return title

    def check_tracks_have_language(self):
        reply, is_valid = "", True

        for section in ["video", "audio", "text"]:
            for i, _ in enumerate(self.mediainfo[section]):
                if "language" not in self.mediainfo[section][i]:
                    reply += self.reporter.print_report(
                        "error",
                        section.capitalize()
                        + " "
                        + self._section_id(section, i)
                        + ": Does not have a language chosen",
                    )
                    is_valid = False

        if is_valid:
            reply += self.reporter.print_report(
                "correct", "All tracks have a language chosen"
            )

        return reply

    def check_video_language_matches_first_audio_language(self):
        reply = ""

        if not has(self.mediainfo, "video.0.language"):
            reply += self.reporter.print_report("error", "Video language not set")
            return reply
        if not has(self.mediainfo, "audio.0.language"):
            reply += self.reporter.print_report("error", "First audio language not set")
            return reply
        if (
            self.mediainfo["video"][0]["language"]
            == self.mediainfo["audio"][0]["language"]
        ):
            reply += self.reporter.print_report(
                "correct",
                "Video language matches first audio language: `"
                + self.mediainfo["video"][0]["language"]
                + "`",
            )
        else:
            reply += self.reporter.print_report(
                "error",
                "Video language does not match first audio language: `"
                + self.mediainfo["video"][0]["language"]
                + "` vs `"
                + self.mediainfo["audio"][0]["language"]
                + "`",
            )
        return reply

    def check_muxing_mode(self):
        reply, is_valid = "", True

        for section in ["general", "video", "audio", "text"]:
            for i, _ in enumerate(self.mediainfo[section]):
                if "muxing_mode" in self.mediainfo[section][i]:
                    reply += self.reporter.print_report(
                        "error",
                        section.capitalize()
                        + " #"
                        + self.mediainfo[section][i]["id"]
                        + " has muxing mode: `"
                        + self.mediainfo[section][i]["muxing_mode"]
                        + "`",
                    )
                    is_valid = False

        if is_valid:
            reply += self.reporter.print_report(
                "correct", "All tracks do not have a muxing mode"
            )

        return reply

    # force_version = "Version 57.0.0 \"Till The End\" 2021-05-22"
    def check_mkvmerge(self, force_version=None):
        reply = ""

        version_name_regex_mkvtoolnix = r'"(.*)"'
        version_name_regex_mediainfo = r"\'(.*)\'"
        version_num_regex = r"(\d+\.\d+\.\d+)"

        if not has(self.mediainfo, "general.0.writing_application"):
            reply += self.reporter.print_report("info", "Not using mkvtoolnix")
            return reply

        mediainfo_version_num = re.search(
            version_num_regex, self.mediainfo["general"][0]["writing_application"]
        )
        if mediainfo_version_num:
            mediainfo_version_num = mediainfo_version_num.group(1)

        mediainfo_version_name = re.search(
            version_name_regex_mediainfo,
            self.mediainfo["general"][0]["writing_application"],
        )
        if mediainfo_version_name:
            mediainfo_version_name = mediainfo_version_name.group(1)

        if not mediainfo_version_num or not mediainfo_version_name:
            reply += self.reporter.print_report("info", "Not using mkvtoolnix")
            return reply

        try:
            r = requests.get(os.environ.get("MKVTOOLNIX_NEWS"))
            if r.status_code == 200:
                ## Version 32.0.0 "Astral Progressions" 2019-03-12
                mkvtoolnix_version_line = r.text.splitlines()[0]
                if force_version:
                    mkvtoolnix_version_line = force_version

                mkvtoolnix_version_num = re.search(
                    version_num_regex, mkvtoolnix_version_line
                )
                if mkvtoolnix_version_num:
                    mkvtoolnix_version_num = mkvtoolnix_version_num.group(1)

                mkvtoolnix_version_name = re.search(
                    version_name_regex_mkvtoolnix, mkvtoolnix_version_line
                )
                if mkvtoolnix_version_name:
                    mkvtoolnix_version_name = mkvtoolnix_version_name.group(1)

                if (
                    mkvtoolnix_version_num == mediainfo_version_num
                    and mkvtoolnix_version_name == mediainfo_version_name
                ):
                    reply += self.reporter.print_report(
                        "correct",
                        "Uses latest mkvtoolnix: `"
                        + mediainfo_version_num
                        + ' "'
                        + mediainfo_version_name
                        + '"`',
                    )
                else:
                    reply += self.reporter.print_report(
                        "warning",
                        "Not using latest mkvtoolnix: `"
                        + mediainfo_version_num
                        + ' "'
                        + mediainfo_version_name
                        + '"` latest is: `'
                        + mkvtoolnix_version_num
                        + ' "'
                        + mkvtoolnix_version_name
                        + '"`',
                    )
        except:
            reply += self.reporter.print_report(
                "info", "Could not fetch latest mkvtoolnix version"
            )
            return reply

        return reply

    def check_default_flag(self):
        # only one track of each type should be default=yes
        reply, default_yes_error = "", False
        track_types = ["audio", "text"]

        for track_type in track_types:
            default_yes_count = 0
            for track in self.mediainfo[track_type]:
                if "default" in track and track["default"].lower() == "yes":
                    default_yes_count += 1
            if default_yes_count > 1:
                reply += self.reporter.print_report(
                    "error",
                    "Only 1 {} track should be `default=yes`".format(track_type),
                )
                default_yes_error = True

        if not default_yes_error:
            reply += self.reporter.print_report(
                "correct",
                "Only 1 track of each type is `default=yes`",
            )
        return reply

    def print_audio_track_names(self):
        reply = ""
        if len(self.mediainfo["audio"]) > 0:
            reply += "Audio Track Names:\n"
            reply += "```"
            for i, _ in enumerate(self.mediainfo["audio"]):
                reply += self._section_id("audio", i) + ": "
                if "title" in self.mediainfo["audio"][i]:
                    reply += self.mediainfo["audio"][i]["title"] + "\n"
            reply += "```"
        else:
            reply = self.reporter.print_report("error", "No audio tracks")
        return reply

    def check_audio_tracks(self):
        reply = ""

        if self.source_detector.is_dvd():
            # no audio track conversions for dvds
            reply += self.reporter.print_report(
                "info", "No audio track conversions to check for DVDs"
            )
            return reply
        else:
            len_bdinfo = len(self.bdinfo["audio"])
            len_mediainfo = len(self.mediainfo["audio"])
            min_len = min(len_bdinfo, len_mediainfo)
            max_len = max(len_bdinfo, len_mediainfo)
            diff_len = abs(max_len - min_len)

            for i in range(0, min_len):
                # audio = dict{'name':'...', 'language':'...'}
                bdinfo_audio_title = re.sub(
                    r"\s+", " ", self.bdinfo["audio"][i]["name"]
                )
                bdinfo_audio_parts = bdinfo_audio_title.split(" / ")
                bdinfo_audio_parts_converted = bdinfo_audio_parts.copy()

                # check audio commentary
                (is_commentary, commentary_reply) = self._check_commentary(i)

                if is_commentary:
                    reply += commentary_reply
                elif len(bdinfo_audio_parts) >= 1:
                    # check audio conversions
                    if (
                        bdinfo_audio_parts[0] == "DTS-HD Master Audio"
                        and is_float(bdinfo_audio_parts[1])
                        and float(bdinfo_audio_parts[1]) < 3
                    ):
                        # DTS-HD MA 1.0 or 2.0 to FLAC
                        reply += self._check_audio_conversion(
                            i, "DTS-HD Master Audio", "FLAC Audio"
                        )
                        bdinfo_audio_parts_converted[0] = "FLAC Audio"
                    elif bdinfo_audio_parts[0] == "LPCM Audio":
                        if (
                            is_float(bdinfo_audio_parts[1])
                            and float(bdinfo_audio_parts[1]) < 3
                        ):
                            # LPCM 1.0 or 2.0 to FLAC
                            reply += self._check_audio_conversion(
                                i, "LPCM Audio", "FLAC Audio"
                            )
                            bdinfo_audio_parts_converted[0] = "FLAC Audio"
                        else:
                            # LPCM > 2.0 to DTS-HD MA
                            reply += self._check_audio_conversion(
                                i, "LPCM Audio", "DTS-HD Master Audio"
                            )
                            bdinfo_audio_parts_converted[0] = "DTS-HD Master Audio"

                    # check track names match
                    if "title" in self.mediainfo["audio"][i]:
                        mediainfo_audio_title = self.mediainfo["audio"][i][
                            "title"
                        ].strip()
                        (
                            mediainfo_audio_title,
                            _,
                            _,
                        ) = self._remove_until_first_codec(mediainfo_audio_title)

                        bdinfo_audio_title = " / ".join(bdinfo_audio_parts_converted)
                        if bdinfo_audio_title == self.mediainfo["audio"][i]["title"]:
                            reply += self.reporter.print_report(
                                "correct",
                                "Audio "
                                + self._section_id("audio", i)
                                + ": Track names match",
                            )
                        else:
                            is_bad_audio_format = False

                            # use bitrate from mediainfo audio title
                            m_bit_rate = re.search(
                                r"(\d+)\skbps", mediainfo_audio_title
                            ).group(1)
                            bdinfo_audio_title = re.sub(
                                r"(.*\s)\d+(\skbps.*)",
                                r"\g<1>{}\g<2>".format(m_bit_rate),
                                bdinfo_audio_title,
                            )

                            possible_bdinfo_audio_titles = [bdinfo_audio_title]
                            if self._eac3to_log_has_mono():
                                # could be 1.0 channels if eac3to log uses -mono
                                possible_bdinfo_audio_titles.append(
                                    re.sub(
                                        r"\d+\.\d+",
                                        "1.0",
                                        bdinfo_audio_title,
                                    )
                                )

                            if (
                                mediainfo_audio_title
                                not in possible_bdinfo_audio_titles
                            ):
                                is_bad_audio_format = True

                            if is_bad_audio_format:
                                reply += self.reporter.print_report(
                                    "error",
                                    "Audio "
                                    + self._section_id("audio", i)
                                    + ": Bad conversion:\n```fix\nBDInfo: "
                                    + bdinfo_audio_title
                                    + "\nMediaInfo: "
                                    + self.mediainfo["audio"][i]["title"]
                                    + "```",
                                    new_line=False,
                                )
                                reply += show_diff(
                                    self.mediainfo["audio"][i]["title"],
                                    bdinfo_audio_title,
                                )
                            else:
                                reply += self.reporter.print_report(
                                    "correct",
                                    "Audio "
                                    + self._section_id("audio", i)
                                    + ": Track names match",
                                )
                    else:
                        reply += self.reporter.print_report(
                            "error",
                            "Audio "
                            + self._section_id("audio", i)
                            + ": Missing track name",
                        )

            if diff_len > 0:
                reply += self.reporter.print_report(
                    "warning",
                    "Checked first `{}/{}` audio tracks".format(min_len, max_len),
                )
                if len_bdinfo > len_mediainfo:
                    reply += "Did you forget to add a minus (-) sign in front of unused audio tracks in bdinfo?\n"

        return reply

    def check_flac_audio_tracks(self):
        # check FLAC Audio tracks using mediainfo
        reply = ""

        if len(self.mediainfo["audio"]) > 0:
            for i, audio_track in enumerate(self.mediainfo["audio"]):
                # skip if no title
                if "title" not in audio_track:
                    continue

                # skip if no codec info
                audio_title, _, found_codec = self._remove_until_first_codec(
                    audio_track["title"]
                )
                if not found_codec:
                    continue

                if "format" in audio_track and audio_track["format"] == "FLAC":
                    channels = float(
                        "".join(
                            re.findall(
                                r"\d*\.\d+|\d+", audio_track["channels"].strip().lower()
                            )
                        )
                    )
                    sampling_rate = int(
                        float(
                            "".join(
                                re.findall(
                                    r"\d*\.\d+|\d+",
                                    audio_track["sampling_rate"].strip().lower(),
                                )
                            )
                        )
                    )
                    bit_rate = int(
                        "".join(
                            re.findall(r"\d+", audio_track["bit_rate"].strip().lower())
                        )
                    )
                    bit_depth = (
                        audio_track["bit_depth"]
                        .strip()
                        .lower()
                        .replace(" bits", "-bit")
                    )
                    test_title = (
                        "FLAC Audio / "
                        + "{:.1f}".format(channels)
                        + " / "
                        + str(sampling_rate)
                        + " kHz / "
                        + str(bit_rate)
                        + " kbps / "
                        + bit_depth
                    )

                    if test_title == audio_title:
                        reply += self.reporter.print_report(
                            "correct",
                            "Audio "
                            + self._section_id("audio", i)
                            + ": FLAC Good track name (from MediaInfo)",
                        )
                    else:
                        reply += self.reporter.print_report(
                            "error",
                            "Audio "
                            + self._section_id("audio", i)
                            + ": FLAC Bad track name (from MediaInfo):\n```fix\nActual: "
                            + audio_title
                            + "\nExpected: "
                            + test_title
                            + "```",
                            new_line=False,
                        )

        return reply

    def _remove_until_first_codec(self, title):
        title2, title_parts, found = title, list(), False
        if " / " in title:
            for part in title.split(" / "):
                if self.codecs.is_audio_title(part):
                    # stop when we get first codec
                    found = True
                    break
                else:
                    title2_split = title2.split(" / ")
                    # remove part since its not a codec
                    title2 = " / ".join(title2_split[1:]).strip()
                    # save part in list
                    title_parts.append(title2_split[0])
        return title2, title_parts, found

    def _check_commentary(self, i):
        reply, is_commentary = "", False

        if self._is_commentary_track(self.mediainfo["audio"][i]["title"]):
            is_commentary = True
            # audio = dict{'name':'...', 'language':'...'}
            if self.bdinfo["audio"][i]["name"].count("/") >= 1:
                bdinfo_audio_format = (
                    self.bdinfo["audio"][i]["name"].split("/")[0].strip()
                )

                if bdinfo_audio_format == "Dolby Digital Audio":
                    if "format" in self.mediainfo["audio"][i]:
                        if self.mediainfo["audio"][i]["format"] == "AC-3":
                            reply += self.reporter.print_report(
                                "correct",
                                "Audio "
                                + self._section_id("audio", i)
                                + ": Commentary already AC-3",
                            )
                        else:
                            reply += self.reporter.print_report(
                                "error",
                                "Audio "
                                + self._section_id("audio", i)
                                + ": Commentary should be AC-3 instead of "
                                + self.mediainfo["audio"][i]["format"],
                            )
                    else:
                        reply += self.reporter.print_report(
                            "error",
                            "Audio "
                            + self._section_id("audio", i)
                            + ": Commentary does not have a format",
                        )

                    return is_commentary, reply
            else:
                reply += self.reporter.print_report(
                    "warning",
                    "Audio #"
                    + self._section_id("audio", i)
                    + ": Cannot verify commentary audio conversion",
                )
                return is_commentary, reply

            if (
                "format" in self.mediainfo["audio"][i]
                and self.mediainfo["audio"][i]["format"] == "AC-3"
            ):
                if "bit_rate" in self.mediainfo["audio"][i]:
                    bit_rate = "".join(
                        re.findall(r"[\d]+", self.mediainfo["audio"][i]["bit_rate"])
                    )
                    if bit_rate == "224":
                        reply += self.reporter.print_report(
                            "correct",
                            "Audio "
                            + self._section_id("audio", i)
                            + ": Commentary converted to `AC-3 @ 224 kbps`",
                        )
                    else:
                        reply += self.reporter.print_report(
                            "error",
                            "Audio "
                            + self._section_id("audio", i)
                            + ": Commentary AC-3 bitrate should be `224 kbps` instead of `"
                            + self.mediainfo["audio"][i]["bit_rate"]
                            + "`",
                        )
                else:
                    reply += self.reporter.print_report(
                        "error",
                        "Audio "
                        + self._section_id("audio", i)
                        + ": Commentary AC-3 does not have a bitrate",
                    )
            else:
                reply += self.reporter.print_report(
                    "info",
                    "Audio "
                    + self._section_id("audio", i)
                    + ": Commentary may be converted to AC-3",
                )

        return is_commentary, reply

    def _check_audio_conversion(self, i, audio_from, audio_to):
        reply = ""

        # verify audio track titles
        if (
            " / " not in self.bdinfo["audio"][i]["name"]
            or "title" not in self.mediainfo["audio"][i]
            or " / " not in self.mediainfo["audio"][i]["title"]
        ):
            reply += self.reporter.print_report(
                "warning", "Could not verify audio " + self._section_id("audio", i)
            )
            return reply

        # [codec, channel, sampling rate, bit rate, bit depth]
        bdinfo_audio_parts = self.bdinfo["audio"][i]["name"].split(" / ")
        if len(bdinfo_audio_parts) <= 4:
            reply += self.reporter.print_report(
                "warning", "Could not verify audio " + self._section_id("audio", i)
            )
            return reply

        mediainfo_audio_title = self.mediainfo["audio"][i]["title"]
        (mediainfo_audio_title, _, _) = self._remove_until_first_codec(
            mediainfo_audio_title
        )

        # [codec, channel, sampling rate, bit rate, bit depth]
        mediainfo_parts = mediainfo_audio_title.split(" / ")
        if len(mediainfo_parts) <= 4:
            reply += self.reporter.print_report(
                "warning", "Could not verify audio " + self._section_id("audio", i)
            )
            return reply

        # verify audio conversions
        if mediainfo_parts[0] == audio_to:
            disable_channels_check = self._eac3to_log_has_mono()

            if (
                not disable_channels_check
                and mediainfo_parts[1] != bdinfo_audio_parts[1]
            ):
                reply += self.reporter.print_report(
                    "error",
                    "Audio "
                    + self._section_id("audio", i)
                    + ": Channels should be `"
                    + bdinfo_audio_parts[1]
                    + "` instead of `"
                    + mediainfo_parts[1]
                    + "`",
                )

            # mediainfo bitrate should be less than bdinfo bitrate
            try:
                m_bit_rate = int(
                    "".join(re.findall(r"\d+", mediainfo_parts[3].strip()))
                )

                bd_bit_rate = int(
                    "".join(re.findall(r"\d+", bdinfo_audio_parts[3].strip()))
                )

                if m_bit_rate > bd_bit_rate:
                    reply += self.reporter.print_report(
                        "error",
                        "Audio "
                        + self._section_id("audio", i)
                        + ": MediaInfo bitrate is greater than BDInfo bitrate: `"
                        + str(m_bit_rate)
                        + " kbps > "
                        + str(bd_bit_rate)
                        + " kbps`",
                    )
            except ValueError:
                pass
        else:
            reply += self.reporter.print_report(
                "error",
                "Audio "
                + self._section_id("audio", i)
                + " should be converted to "
                + audio_to,
            )

        return reply

    def check_people(self):
        reply = ""

        # check people in audio track names
        for i, _ in enumerate(self.mediainfo["audio"]):
            if "title" in self.mediainfo["audio"][i]:
                title = self.mediainfo["audio"][i]["title"]

                # skip if has an audio codec
                _, _, found_codec = self._remove_until_first_codec(title)
                if found_codec:
                    continue

                # try to match names
                matched_names = list()
                names = extract_names(title)
                search = tmdb.Search()
                for n in names:
                    # TMDb API
                    try:
                        search.person(query=n)
                        for s in search.results:
                            if n == s["name"]:
                                matched_names.append(n)
                    except:
                        reply += self.reporter.print_report(
                            "info", "Failed to get TMDb people data"
                        )
                    # IMDb API
                    try:
                        for person in ia.search_person(n):
                            if n == person["name"]:
                                matched_names.append(n)
                    except:
                        reply += self.reporter.print_report(
                            "info", "Failed to get IMDb people data"
                        )
                matched_names = set(matched_names)
                if len(matched_names) > 0:
                    reply += self.reporter.print_report(
                        "correct",
                        "Audio "
                        + self._section_id("audio", i)
                        + " People Matched: `"
                        + ", ".join(matched_names)
                        + "`",
                    )
                unmatched_names = set(names) - set(matched_names)
                if len(unmatched_names) > 0:
                    reply += self.reporter.print_report(
                        "warning",
                        "Audio "
                        + self._section_id("audio", i)
                        + " People Unmatched: `"
                        + ", ".join(unmatched_names)
                        + "`",
                    )

        return reply

    def spell_check_track_name(self):
        reply = ""

        # spellcheck audio track names
        for i, _ in enumerate(self.mediainfo["audio"]):
            if "title" in self.mediainfo["audio"][i]:
                title, title_parts, found_codec = self._remove_until_first_codec(
                    self.mediainfo["audio"][i]["title"]
                )

                spellcheck_text = None
                if found_codec:
                    # spellcheck title parts before codec
                    spellcheck_text = " ".join(title_parts)
                else:
                    # spellcheck entire audio title
                    spellcheck_text = title
                if spellcheck_text:
                    # map punctuation to space
                    translator = str.maketrans(
                        string.punctuation, " " * len(string.punctuation)
                    )
                    spellcheck_text = spellcheck_text.translate(translator)

                    # ignore names
                    ignore_list = extract_names(spellcheck_text)
                    ignore_list = [a for b in ignore_list for a in b.split()]

                    # tokenize
                    tokens = nltk.word_tokenize(spellcheck_text)
                    tokens = [t for t in tokens if t not in ignore_list]

                    misspelled_words = list()
                    for t in tokens:
                        if not self.hobj.spell(t):
                            # t is misspelled
                            misspelled_words.append(t)

                    misspelled_words = set(misspelled_words)
                    misspelled_words = [
                        word
                        for word in misspelled_words
                        if word.lower() not in MISSPELLED_IGNORE_LIST
                    ]
                    if len(misspelled_words) > 0:
                        reply += self.reporter.print_report(
                            "error",
                            "Audio "
                            + self._section_id("audio", i)
                            + " Misspelled: `"
                            + ", ".join(misspelled_words)
                            + "`",
                        )

        return reply

    def print_text_tracks(self):
        reply = "> **Text Tracks**\n"
        if len(self.mediainfo["text"]) > 0:
            reply += "```"
            for i, _ in enumerate(self.mediainfo["text"]):
                reply += self._section_id("text", i) + ":"
                if "default" in self.mediainfo["text"][i]:
                    reply += " default:" + self.mediainfo["text"][i]["default"]
                if "forced" in self.mediainfo["text"][i]:
                    reply += " forced:" + self.mediainfo["text"][i]["forced"]
                if "language" in self.mediainfo["text"][i]:
                    reply += " language:" + self.mediainfo["text"][i]["language"]
                if "title" in self.mediainfo["text"][i]:
                    reply += " title: " + self.mediainfo["text"][i]["title"]
                reply += "\n"
            reply += "```"
        else:
            reply += self.reporter.print_report("info", "No text tracks")
        return reply

    def check_text_order(self):
        reply = ""

        if len(self.mediainfo["text"]) == 0:
            return reply

        language_number = 1  # Used to keep track of first actual sub.
        forced_checked, commentary_checked = False, False
        forced_track_eng_first = False
        prev_track_language, prev_track_name = "", ""
        subs_in_order = True

        for i, _ in enumerate(self.mediainfo["text"]):
            forced_track, commentary_track = False, False
            track_language, track_name = "", ""

            if "language" in self.mediainfo["text"][i]:
                track_language = self.mediainfo["text"][i]["language"].lower()
            else:
                # Error printed elsewhere.
                subs_in_order = False
            if "forced" in self.mediainfo["text"][i]:
                forced_track = self.mediainfo["text"][i]["forced"].lower() == "yes"
            if "title" in self.mediainfo["text"][i]:
                track_name = self.mediainfo["text"][i]["title"]
                commentary_track = self._is_commentary_track(track_name)

            if i == 0 and forced_track:
                forced_track_eng_first = track_language == "english"
            elif forced_track and track_language == "english":
                subs_in_order = False
                reply += self.reporter.print_report(
                    "error",
                    "Text {} is a forced English track, it must be first".format(
                        self._section_id("text", i)
                    ),
                )
            elif not forced_checked:
                forced_checked = True
                track_name, track_language = "", ""
            elif commentary_track:
                commentary_checked = True
            elif commentary_checked:
                subs_in_order = False
                reply += self.reporter.print_report(
                    "error",
                    "Text {} came after the commentary sub(s)".format(
                        self._section_id("text", i)
                    ),
                )
            elif track_language == prev_track_language:
                if prev_track_name != "" and track_name < prev_track_name:
                    reply += self.reporter.print_report(
                        "warning",
                        "Text {} might need to come after Text {}, alphabetical within language".format(
                            self._section_id("Text", i - 1), self._section_id("Text", i)
                        ),
                    )
            elif language_number > 1 and track_language < prev_track_language:
                subs_in_order = False
                prev_track_language = ""
                reply += self.reporter.print_report(
                    "error",
                    "Text {} should come after Text {}, language order".format(
                        self._section_id("text", i - 1), self._section_id("text", i)
                    ),
                )
            elif language_number == 1 and track_language != "english":
                language_number += 1
            prev_track_language = track_language
            prev_track_name = track_name

        if subs_in_order:
            reply += self.reporter.print_report("correct", "Subtitles are in order")
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

    def _is_commentary_track(self, title):
        return "commentary" in title.lower().split()

    def _eac3to_log_has_mono(self):
        # get command-lines

        cmd_lines_mono = list()
        for log in self.eac3to:
            cmd_lines_mono.extend(
                [
                    l.lower()
                    for l in log
                    if l.lower().startswith("command line:")
                    and "-mono" in l.lower().split()
                ]
            )

        return len(cmd_lines_mono) > 0

    def _section_id(self, section, i):
        reply = ""
        if "id" in self.mediainfo[section.lower()][i]:
            reply += "#" + self.mediainfo[section.lower()][i]["id"]
        else:
            reply += str(i)
        return reply
