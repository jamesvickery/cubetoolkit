from __future__ import absolute_import

import pytz
from datetime import datetime, date

from django.test import TestCase

import django.db
from django.core.exceptions import ValidationError
from toolkit.diary.models import Showing, Event, PrintedProgramme, EventTag

from .common import DiaryTestsMixin


class ShowingModelCustomQueryset(DiaryTestsMixin, TestCase):

    def test_manager_public(self):
        records = list(Showing.objects.public())
        # From the fixtures, there are 4 showings that are confirmed and not
        # private / hidden
        self.assertEqual(len(records), 4)
        for showing in records:
            self.assertTrue(showing.confirmed)
            self.assertFalse(showing.hide_in_programme)
            self.assertFalse(showing.event.private)

    def test_queryset_public(self):
        # Difference here is that we get a queryset, then use the public()
        # method on that (rather than using the public() method directly on
        # the manager)
        records = list(Showing.objects.all().public())
        # From the fixtures, there are 4 showings that are confirmed and not
        # private / hidden
        self.assertEqual(len(records), 4)
        for showing in records:
            self.assertTrue(showing.confirmed)
            self.assertFalse(showing.hide_in_programme)
            self.assertFalse(showing.event.private)

    def test_manager_not_cancelled(self):
        records = list(Showing.objects.not_cancelled())
        # From the fixtures, there are 7 showings that aren't cancelled
        self.assertEqual(len(records), 8)
        for showing in records:
            self.assertFalse(showing.cancelled)

    def test_manager_confirmed(self):
        records = list(Showing.objects.confirmed())
        # From the fixtures, there are 7 showings that are confirmed:
        self.assertEqual(len(records), 8)
        for showing in records:
            self.assertTrue(showing.confirmed)

    def test_manager_date_range(self):
        start = pytz.utc.localize(datetime(2013, 4, 2, 12, 0))
        end = pytz.utc.localize(datetime(2013, 4, 4, 12, 0))
        records = list(Showing.objects.start_in_range(start, end))
        # Expect 2 showings in this date range:
        self.assertEqual(len(records), 2)
        for showing in records:
            self.assertTrue(showing.start < end)
            self.assertTrue(showing.start > start)

    def test_queryset_chaining(self):
        start = pytz.utc.localize(datetime(2000, 4, 2, 12, 0))
        end = pytz.utc.localize(datetime(2013, 9, 1, 12, 0))
        records = list(Showing.objects.all()
                                      .public()
                                      .not_cancelled()
                                      .start_in_range(start, end)
                                      .confirmed())
        self.assertEqual(len(records), 3)
        for showing in records:
            self.assertTrue(showing.confirmed)
            self.assertFalse(showing.hide_in_programme)
            self.assertFalse(showing.event.private)
            self.assertFalse(showing.cancelled)
            self.assertTrue(showing.start < end)
            self.assertTrue(showing.start > start)
            self.assertTrue(showing.confirmed)


class EventModelNonLegacyCopy(TestCase):

    def setUp(self):
        self.sample_copy = (
            u"<p>Simple &amp; tidy HTML/unicode \u00a9\u014dpy\n</p>\n"
            u"<p>With a <a href='http://example.com/foo/'>link!</a>"
            u"<p>And another! <a href='https://example.com/bar/'>link!</a>"
            u" and some equivalent things; &pound; &#163; \u00a3<br></p>"
        )
        self.event = Event(name="Test event", legacy_copy=False, copy=self.sample_copy)
        self.event.save()

    def test_simple(self):
        # Test copy goes in and out without being mangled
        reloaded = Event.objects.get(id=self.event.pk)
        self.assertEqual(reloaded.copy, self.sample_copy)

    def test_html_copy(self):
        self.assertEqual(self.event.copy_html, self.sample_copy)

    def test_plaintext_copy(self):
        expected = (
            u"Simple & tidy HTML/unicode \u00a9\u014dpy \n\n"
            u"With a link!: http://example.com/foo/\n\n"
            u"And another! link!: https://example.com/bar/"
            u" and some equivalent things; \u00a3 \u00a3 \u00a3  \n\n"
        )
        self.assertEqual(self.event.copy_plaintext, expected)


class EventModelLegacyCopy(TestCase):

    def setUp(self):
        self.sample_copy = (
            u"Simple &amp; tidy legacy \u00a9\u014dpy\n\n"
            u"With an unardorned link: http://example.com/foo/"
            u" https://example.com/foo/"
            u" and some equivalent things; &pound; &#163; \u00a3..."
            u" and <this> \"'<troublemaker>'\""
        )
        self.event = Event(name="Test event", legacy_copy=True, copy=self.sample_copy)
        self.event.save()

    def test_simple(self):
        # Test copy goes in and out without being mangled
        reloaded = Event.objects.get(id=self.event.pk)
        self.assertEqual(reloaded.copy, self.sample_copy)

    def test_html_copy(self):
        expected = (
            u"Simple &amp; tidy legacy \u00a9\u014dpy <br><br>"
            u'With an unardorned link: <a href="http://example.com/foo/">http://example.com/foo/</a>'
            u' <a href="https://example.com/foo/">https://example.com/foo/</a>'
            u" and some equivalent things; &pound; &#163; \u00a3..."
            u" and <this> \"'<troublemaker>'\""
        )
        self.assertEqual(self.event.copy_html, expected)

    def test_plaintext_copy(self):
        expected = (
            u"Simple & tidy legacy \u00a9\u014dpy\n\n"
            u"With an unardorned link: http://example.com/foo/"
            u" https://example.com/foo/"
            u" and some equivalent things; \u00a3 \u00a3 \u00a3..."
            u" and <this> \"'<troublemaker>'\""
        )
        self.assertEqual(self.event.copy_plaintext, expected)


class PrintedProgrammeModelTests(TestCase):

    def test_month_ok(self):
        pp = PrintedProgramme(
            programme="/foo/bar",
            month=date(2010, 2, 1)
        )
        pp.save()

        pp = PrintedProgramme.objects.get(pk=pp.pk)
        self.assertEqual(pp.month, date(2010, 2, 1))

    def test_month_normalised(self):
        pp = PrintedProgramme(
            programme="/foo/bar",
            month=date(2010, 2, 2)
        )
        pp.save()

        pp = PrintedProgramme.objects.get(pk=pp.pk)
        self.assertEqual(pp.month, date(2010, 2, 1))


class EventTagTests(TestCase):
    def test_can_delete_not_readonly(self):
        tag = EventTag(name=u"test", slug=u"test", read_only=False)
        tag.save()
        pk = tag.pk

        tag.delete()

        self.assertEqual(EventTag.objects.filter(id=pk).count(), 0)

    def test_cant_delete_readonly(self):
        tag = EventTag(name=u"test", slug=u"test", read_only=True)
        tag.save()
        pk = tag.pk

        tag.delete()

        self.assertEqual(EventTag.objects.filter(id=pk).count(), 1)
        tag = EventTag.objects.get(id=pk)
        self.assertEqual(tag.name, "test")

    def test_can_edit_not_readonly(self):
        tag = EventTag(name=u"test", slug=u"test", read_only=False)
        tag.save()
        pk = tag.pk
        # Try to edit:
        tag.name = "crispin"
        tag.save()

        tag = EventTag.objects.get(id=pk)
        self.assertEqual(tag.name, "crispin")

    def test_cant_edit_readonly(self):
        tag = EventTag(name=u"test", slug=u"test", read_only=True)
        tag.save()
        pk = tag.pk
        # Try to edit:
        tag.name = "crispin"
        tag.save()

        tag = EventTag.objects.get(id=pk)
        self.assertEqual(tag.name, "test")

    def test_clean_case(self):
        tag = EventTag(name=u"BIGlettersHERE")
        tag.clean()
        self.assertEqual(tag.name, "biglettershere")
        self.assertEqual(tag.slug, "biglettershere")

    def test_slugify(self):
        tag = EventTag(name=u"with space", slug=u"")
        tag.clean()
        self.assertEqual(tag.name, "with space")
        self.assertEqual(tag.slug, "with-space")

        tag = EventTag(name=u"with&ampersand")
        tag.clean()
        self.assertEqual(tag.name, "with&ampersand")
        self.assertEqual(tag.slug, "withampersand")

        tag = EventTag(name=u"with?questionmark")
        tag.clean()
        self.assertEqual(tag.name, "with?questionmark")
        self.assertEqual(tag.slug, "withquestionmark")

        tag = EventTag(name=u"with#hash")
        tag.clean()
        self.assertEqual(tag.name, "with#hash")
        self.assertEqual(tag.slug, "withhash")

    def test_reject_blank(self):
        tag = EventTag(name=u"")
        self.assertRaises(ValidationError, tag.full_clean)

    def test_must_be_unique(self):
        t1 = EventTag(name=u"jim", slug=u"jim")
        t1.save()

        t2 = EventTag(name=u"jim!", slug=u"jim")
        self.assertRaises(django.db.IntegrityError, t2.save)
