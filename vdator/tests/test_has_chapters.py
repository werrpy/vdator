from unittest.mock import Mock, patch
from checks import CheckHasChapters


def fake_print_report(self, text):
    return text


def test_correct_has_chapters():
    # mock reporter
    reporter = Mock()
    reporter.print_report = fake_print_report

    # data
    eac3to = [["chapters"]]
    mediainfo = {"menu": ["a"]}

    # initialize check
    check_has_chapters = CheckHasChapters(reporter, mediainfo, eac3to)

    # run check
    check_has_chapters_res = check_has_chapters.run()
    expected = "Has chapters (from eac3to log)"

    # assert
    assert check_has_chapters_res == expected
