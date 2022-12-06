import copy


class MatchBDInfoAudioToMediaInfo(object):
    def __init__(self, remove_until_first_codec, bdinfo, mediainfo):
        self.remove_until_first_codec = remove_until_first_codec
        self.bdinfo = bdinfo
        self.mediainfo = mediainfo

    def match_bdinfo_audio_to_mediainfo(self):
        # tries to match bdinfo audio tracks to mediainfo by codec and channels
        # for every mediainfo track, pick first matching bdinfo track
        # returns a sorted list of bdinfo audio tracks
        sorted_bdinfo_audio_tracks = list()

        bdinfo_audio_tracks = copy.deepcopy(self.bdinfo["audio"])
        mediainfo_audio_tracks = copy.deepcopy(self.mediainfo["audio"])

        for mediainfo_audio_track in mediainfo_audio_tracks:
            # go through every mediainfo audio track
            mediainfo_audio_title = None
            if "title" in mediainfo_audio_track:
                (
                    mediainfo_audio_title,
                    _,
                    _,
                ) = self.remove_until_first_codec.remove(mediainfo_audio_track["title"])

            # find the next matching bdinfo audio track
            for i, bdinfo_audio_track in enumerate(bdinfo_audio_tracks):
                bdinfo_audio_title = None
                if "name" in bdinfo_audio_track:
                    (
                        bdinfo_audio_title,
                        _,
                        _,
                    ) = self.remove_until_first_codec.remove(bdinfo_audio_track["name"])

                if mediainfo_audio_title and bdinfo_audio_title:
                    bdinfo_audio_track_parts = bdinfo_audio_title.split(" / ")
                    mediainfo_audio_track_parts = mediainfo_audio_title.split(" / ")
                    if (
                        len(bdinfo_audio_track_parts) > 1
                        and len(mediainfo_audio_track_parts) > 1
                    ):
                        print("bdparts = " + ",".join(bdinfo_audio_track_parts))
                        print("miparts = " + ",".join(mediainfo_audio_track_parts))
                        if (
                            bdinfo_audio_track_parts[0]
                            == mediainfo_audio_track_parts[0]
                            and bdinfo_audio_track_parts[1]
                            == mediainfo_audio_track_parts[1]
                        ):
                            # codecs and channel match
                            sorted_bdinfo_audio_tracks.append(bdinfo_audio_track)
                            del bdinfo_audio_tracks[i]
                            break

            if len(bdinfo_audio_tracks) == 0:
                break

        # if len(bdinfo_audio_tracks) > 0:
        #    # add leftover bdinfo audio tracks
        #    sorted_bdinfo_audio_tracks.extend(bdinfo_audio_tracks)

        print(sorted_bdinfo_audio_tracks)
        return sorted_bdinfo_audio_tracks
