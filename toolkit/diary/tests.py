import re
import json
import os.path

import pytz
from datetime import datetime, date, time
import tempfile

from mock import patch

from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse, resolve
import django.http
import django.contrib.auth.models as auth_models
import django.contrib.contenttypes as contenttypes

from toolkit.diary.models import (Showing, Event, Role, EventTag, DiaryIdea,
                                  EventTemplate, RotaEntry, MediaItem)
from toolkit.members.models import Member, Volunteer
import toolkit.diary.edit_prefs


class DiaryTestsMixin(object):

    def setUp(self):
        self._setup_test_data()

        return super(DiaryTestsMixin, self).setUp()

    # Useful method:
    def assert_return_to_index(self, response):
        # Check status=200 and expected text included:
        self.assertContains(
            response,
            "<!DOCTYPE html><html>"
            "<head><title>-</title></head>"
            "<body onload='self.close(); opener.location.reload(true);'>Ok</body>"
            "</html>"
        )

    def assert_has_message(self, response, msg, level):
        self.assertContains(
            response,
            u'<li class="{0}">{1}</li>'.format(level, msg)
        )

    def _setup_test_data(self):

        self._fake_now = pytz.timezone("Europe/London").localize(datetime(2013, 6, 1, 11, 00))

        # Roles:
        r1 = Role(name=u"Role 1 (standard)", read_only=False, standard=True)
        r1.save()
        r2 = Role(name=u"Role 2 (nonstandard)", read_only=False, standard=False)
        r2.save()
        r3 = Role(name=u"Role 3", read_only=False, standard=False)
        r3.save()

        # Tags:
        t1 = EventTag(name=u"tag one", read_only=False)
        t1.save()
        t2 = EventTag(name=u"tag two", read_only=False)
        t2.save()
        t3 = EventTag(name=u"\u0167ag \u0165hre\u0119", read_only=False)
        t3.save()

        """
        Event  outside_hire   private   Tags
        ---------------------------------------
        e1     True           False
        e2     False          False
        e3     False          False    t2
        e4     False          False    t2
        e5     False          True
        e6     True           True     t3

        Showing  Event  Date    Confirmed  Hidden  Cancelled  Discount|E: outside  private
        --------------------------------------------------------------|-------------------
        e2s1       e2    1/4/13   F          F       F          F     |   F        F
        e2s2       e2    2/4/13   T          F       F          F     |   F        F
        e2s3       e2    3/4/13   T          F       T          F     |   F        F
        e2s4       e2    4/4/13   T          T       F          F     |   F        F
        e2s5       e2    5/4/13   T          T       T          F     |   F        F

        s2       e3    13/4/13  T          F       F          F       |   F        F
        s3       e4    9/6/13   T          F       F          F       |   F        F
        s4       e4    14/9/13  F          F       F          F       |   F        F
        s5       e5    14/2/13  T          F       F          F       |   F        T
        s6       e1    15/2/13  T          T       F          F       |   F        F
        """

        # Events:
        e1 = Event(
            name="Event one title",
            copy="Event one copy",
            copy_summary="Event one copy summary",
            duration="01:30:00",
            outside_hire=True,
        )
        e1.save()

        e2 = Event(
            name="Event two title",
            copy="Event\n two\n copy",  # newlines will be stripped at legacy conversion
            copy_summary="Event two\n copy summary",
            duration="01:30:00",
            legacy_id="100",
            legacy_copy=True,
        )
        e2.save()

        e3 = Event(
            name="Event three title",
            copy="Event three Copy",
            copy_summary="Copy three summary",
            duration="03:00:00",
            notes="Notes",
        )
        e3.save()
        e3.tags = [t2, ]
        e3.save()

        e4 = Event(
            name=u"Event four titl\u0113",
            copy=u"Event four C\u014dpy",
            copy_summary=u"\u010copy four summary",
            terms=u"Terminal price: \u00a31 / \u20ac3",
            duration="01:00:00",
            notes="\u0147otes on event fou\u0159",
        )
        e4.save()
        e4.tags = [t2, ]
        e4.save()

        e5 = Event(
            name=u"PRIVATE Event FIVE titl\u0113!",
            copy=u"PRIVATE Event 5ive C\u014dpy",
            copy_summary=u"\u010copy five summary",
            terms=u"More terms; price: \u00a32 / \u20ac5",
            duration="10:00:00",
            notes="\u0147otes on event five",
            private=True
        )
        e5.save()

        e6 = Event(
            name=u"PRIVATE OUTSIDE Event (Six)",
            copy=u"PRIVATE OUTSIDE Event 6ix copy",
            copy_summary=u"OUTSIDE PRIVATE \u010copy six summary",
            terms=u"Ever More terms; price: \u00a32 / \u20ac5",
            duration="4:00:00",
            notes="\u0147otes on private/outwide event six",
            outside_hire=True,
            private=True
        )
        e6.save()
        e6.tags = [t3, ]
        e6.save()

        # Showings:
        self.e2s1 = Showing(  # pk :1
            start=pytz.timezone("Europe/London").localize(datetime(2013, 4, 1, 19, 00)),
            event=e2, booked_by="User",
            confirmed=False, hide_in_programme=False, cancelled=False, discounted=False)
        self.e2s1.save(force=True)
        self.e2s2 = Showing(  # pk :2
            start=pytz.timezone("Europe/London").localize(datetime(2013, 4, 2, 19, 00)),
            event=e2, booked_by="User",
            confirmed=True, hide_in_programme=False, cancelled=False, discounted=False)
        self.e2s2.save(force=True)
        e2s3 = Showing(  # pk :3
            start=pytz.timezone("Europe/London").localize(datetime(2013, 4, 3, 19, 00)),
            event=e2, booked_by="User",
            confirmed=True, hide_in_programme=False, cancelled=True, discounted=False)
        e2s3.save(force=True)
        e2s4 = Showing(  # pk :4
            start=pytz.timezone("Europe/London").localize(datetime(2013, 4, 4, 19, 00)),
            event=e2, booked_by="User",
            confirmed=True, hide_in_programme=True, cancelled=False, discounted=False)
        e2s4.save(force=True)
        e2s5 = Showing(  # pk :5
            start=pytz.timezone("Europe/London").localize(datetime(2013, 4, 5, 19, 00)),
            event=e2, booked_by="User",
            confirmed=True, hide_in_programme=True, cancelled=True, discounted=False)
        e2s5.save(force=True)

        s2 = Showing(
            start=pytz.timezone("Europe/London").localize(datetime(2013, 4, 13, 18, 00)),
            event=e3,
            booked_by="User Two",
            confirmed=True
        )
        s2.save(force=True)  # Force start date in the past

        # When the clock is patched to claim that it's 1/6/2013, this showing
        # will be in the future:
        s3 = Showing(
            start=pytz.timezone("Europe/London").localize(datetime(2013, 6, 9, 18, 00)),
            event=e4,
            booked_by=u"\u0102nother \u0170ser",
            confirmed=True
        )
        s3.save(force=True)  # Force start date in the past

        s4 = Showing(
            start=pytz.timezone("Europe/London").localize(datetime(2013, 9, 14, 18, 00)),
            event=e4,
            booked_by="User Two",
            hide_in_programme=True,
            confirmed=False
        )
        s4.save(force=True)  # Force start date in the past

        s5 = Showing(
            start=pytz.timezone("Europe/London").localize(datetime(2013, 2, 14, 18, 00)),
            event=e5,
            booked_by="Yet another user",
            confirmed=True,
        )
        s5.save(force=True)

        s6 = Showing(
            start=pytz.timezone("Europe/London").localize(datetime(2013, 2, 15, 18, 00)),
            event=e1,
            booked_by="Blah blah",
            confirmed=True,
            hide_in_programme=True,
        )
        s6.save(force=True)

        # Rota items:
        RotaEntry(showing=self.e2s1, role=r2, rank=1).save()
        RotaEntry(showing=self.e2s1, role=r3, rank=1).save()
        RotaEntry(showing=s2, role=r1, rank=1).save()
        RotaEntry(showing=s2, role=r1, rank=2).save()
        RotaEntry(showing=s2, role=r1, rank=3).save()
        RotaEntry(showing=s2, role=r1, rank=4).save()
        RotaEntry(showing=s2, role=r1, rank=5).save()
        RotaEntry(showing=s2, role=r1, rank=6).save()
        RotaEntry(showing=s3, role=r2, rank=1).save()

        # Ideas:
        i = DiaryIdea(
            ideas="April 2013 ideas",
            month=date(year=2013, month=4, day=1)
        )
        i.save()
        i = DiaryIdea(
            ideas="May 2013 ideas",
            month=date(year=2013, month=5, day=1)
        )
        i.save()

        # Templates:
        tmpl = EventTemplate(name="Template 1")
        tmpl.save()
        tmpl.roles = [r1]
        tmpl.tags = [t1]
        tmpl.save()

        tmpl = EventTemplate(name="Template 2")
        tmpl.save()
        tmpl.roles = [r2]
        tmpl.tags = [t2]
        tmpl.save()

        tmpl = EventTemplate(name="Template 3")
        tmpl.save()
        tmpl.roles = [r1, r2, r3]
        tmpl.save()

        # Members:
        m1 = Member(name="Member One", email="one@example.com", number="1",
                    postcode="BS1 1AA")
        m1.save()
        m2 = Member(name="Two Member", email="two@example.com", number="2",
                    postcode="")
        m2.save()
        m3 = Member(name="Volunteer One", email="volon@cube.test", number="3",
                    phone="0800 000 000", address="1 Road", posttown="Town",
                    postcode="BS6 123", country="UK", website="http://foo.test/")
        m3.save()
        m4 = Member(name="Volunteer Two", email="", number="4",
                    phone="", altphone="", address="", posttown="", postcode="",
                    country="", website="http://foo.test/")
        m4.save()
        m5 = Member(name="Volunteer Three", email="volthree@foo.test", number="4",
                    phone="", altphone="", address="", posttown="", postcode="",
                    country="", website="")
        m5.save()

        # Volunteers:
        v1 = Volunteer(member=m3)
        v1.save()
        v1.roles = [r1, r3]
        v1.save()

        v2 = Volunteer(member=m4)
        v2.save()

        v3 = Volunteer(member=m5)
        v3.save()
        v3.roles = [r3]
        v3.save()

        # System user:
        user_rw = auth_models.User.objects.create_user('admin', 'toolkit_admin@localhost', 'T3stPassword!')
        # Create dummy ContentType:
        ct = contenttypes.models.ContentType.objects.get_or_create(
            model='',
            app_label='toolkit'
        )[0]
        # Create 'write' permission:
        write_permission = auth_models.Permission.objects.get_or_create(
            name='Write access to all toolkit content',
            content_type=ct,
            codename='write'
        )[0]
        # Give "admin" user the write permission:
        user_rw.user_permissions.add(write_permission)


class PublicDiaryViews(DiaryTestsMixin, TestCase):

    """Basic test that all the public diary pages load"""

    def test_view_default(self):
        # Hard code root URL to assert that it gets something:
        response = self.client.get('/programme/')
        self.assertEqual(response.status_code, 200)

    def test_view_default_reversed(self):
        url = reverse("default-view")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_by_type(self):
        url = reverse("type-view", kwargs={"event_type": "film"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_by_year(self):
        url = reverse("year-view", kwargs={"year": "2013"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Should test the contents better, I suspect...
        self.assertContains(response, u'Event three title')
        self.assertContains(response, u'<p>Event three Copy</p>')
        # Not confirmed / private:
        self.assertNotContains(response, u'Event one title')
        self.assertNotContains(response, u'<p>Event one copy</p>')

    def test_view_by_month(self):
        url = reverse("month-view", kwargs={"year": "2010", "month": "12"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_by_day(self):
        url = reverse("day-view", kwargs={"year": "2010", "month": "12", "day": "31"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_by_tag_nothing_found(self):
        url = reverse("type-view", kwargs={"event_type": "folm"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response,
                            "<p>Couldn't find anything tagged <strong>folm</strong></p>",
                            html=True)

    def test_view_by_date_nothing_found(self):
        url = reverse("year-view", kwargs={"year": "2093"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "<p>Nothing on between Thursday 1 Jan 2093 and Friday 1 Jan 2094</p>",
            html=True
        )

    # JSON day data:
    def test_day_json(self):
        url = reverse("day-view-json", kwargs={"year": "2013", "month": "4", "day": "13"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # Eh (shrug)
        self.assertEqual(data, [{
                         u"name": u"Event three title",
                         u"tags": u"tag two",
                         u"image": None,
                         u"start": u"13/04/2013 18:00",
                         u"link": u"/programme/event/id/3/",
                         u"copy": u"Event three Copy"
                         }])

    # View of individual showing:
    def test_view_showing(self):
        url = reverse("single-showing-view", kwargs={"showing_id": str(self.e2s2.pk)})
        response = self.client.get(url)
        self.assertContains(response, u'Event two title')
        self.assertContains(response, u'<p>Event <br>\n two <br>\n copy</p>')
        self.assertEqual(response.status_code, 200)

    def test_view_hidden_showing(self):
        url = reverse("single-showing-view", kwargs={"showing_id": str(self.e2s1.pk)})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # Event series view:
    def test_view_event(self):
        url = reverse("single-event-view", kwargs={"event_id": "2"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_event.html")

        # TODO: test data better, including media!
        self.assertContains(response, u'Event two title')
        self.assertContains(response, u'<p>Event <br> two <br> copy</p>', html=True)
        self.assertEqual(response.status_code, 200)
        # Some showings *should* be listed:
        self.assertContains(response, "Tue 2 Apr, 7 p.m.")
        self.assertContains(response, "Wed 3 Apr, 7 p.m.")
        # Some showings should *not* be listed:
        self.assertNotContains(response, "1 Apr")
        self.assertNotContains(response, "4 Apr")
        self.assertNotContains(response, "5 Apr")

    def test_view_event_legacy(self):
        url = reverse("single-event-view-legacyid", kwargs={"legacy_id": "100"})
        response = self.client.get(url)
        # TODO: test data!
        self.assertEqual(response.status_code, 200)

    def test_view_event_no_public_showings(self):
        # Event 1 has no publicly viewable showings:
        url = reverse("single-event-view", kwargs={"event_id": "1"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # TODO: Cancelled/confirmed/visible/TTT


class EditDiaryViewsLoginRequired(DiaryTestsMixin, TestCase):

    """Basic test that the private diary pages do not load without a login"""

    def test_urls(self):
        views_to_test = {
            "default-edit": {},
            "year-edit": {"year": "2013"},
            "month-edit": {"year": "2013", "month": "1"},
            "day-edit": {"year": "2013", "month": "1", "day": "1"},
            "edit-event-details-view": {"pk": "1"},
            "edit-event-details": {"event_id": "1"},
            "edit-showing": {"showing_id": "1"},
            "edit-ideas": {"year": "2012", "month": "1"},
            "add-showing": {"event_id": "1"},
            "delete-showing": {"showing_id": "1"},
            "add-event": {},

            "edit_event_templates": {},
            "edit_event_tags": {},
            "edit_roles": {},
            "members-mailout": {},
            "exec-mailout": {},
            "mailout-progress": {},
            "set_edit_preferences": {},
        }
        for view_name, kwargs in views_to_test.iteritems():
            url = reverse(view_name, kwargs=kwargs)
            expected_redirect = ("{0}?next={1}"
                                 .format(reverse("django.contrib.auth.views.login"), url))

            # Test GET:
            response = self.client.get(url)
            self.assertRedirects(response, expected_redirect)

            # Test POST:
            response = self.client.post(url)
            self.assertRedirects(response, expected_redirect)


class EditDiaryViews(DiaryTestsMixin, TestCase):

    """Basic test that various private diary pages load"""

    def setUp(self):
        super(EditDiaryViews, self).setUp()

        self.client.login(username="admin", password="T3stPassword!")

    def tearDown(self):
        self.client.logout()

    def test_view_default(self):
        url = reverse("default-edit")
        response = self.client.get(url)
        # self.assertIn(u'Event one title', response.content)
        # self.assertIn(u'<p>Event one copy</p>', response.content)
        self.assertEqual(response.status_code, 200)

    def test_view_tag_editor(self):
        url = reverse("edit_event_tags")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_tags.html")

    def test_view_template_editor(self):
        url = reverse("edit_event_templates")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_templates.html")

    def test_view_role_editor(self):
        url = reverse("edit_roles")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_edit_roles.html")


class AddShowingView(DiaryTestsMixin, TestCase):

    def setUp(self):
        super(AddShowingView, self).setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def test_add_showing_must_post(self):
        # Add a new showing
        url = reverse("add-showing", kwargs={"event_id": 1})
        url += "?copy_from=2"
        # TODO: Add more query data that might work
        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)

    def test_add_showing_no_copy_from(self):
        # No copy_from parameter: should return 404
        url = reverse("add-showing", kwargs={"event_id": 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_add_showing_no_start(self):
        url = reverse("add-showing", kwargs={"event_id": 1})
        url += "?copy_from=2"

        showing_count_before = Showing.objects.count()

        source = Showing.objects.get(id=2)

        self.assertEqual(source.event.showings.count(), 5)

        response = self.client.post(url, data={
            "booked_by": "someone",
        })

        showing_count_after = Showing.objects.count()
        self.assertEqual(showing_count_after, showing_count_before)

        self.assertFormError(response, 'clone_showing_form', 'clone_start',
                             u'This field is required.')

    def test_add_showing_no_booked_by(self):
        url = reverse("add-showing", kwargs={"event_id": 1})
        url += "?copy_from=2"

        showing_count_before = Showing.objects.count()

        source = Showing.objects.get(id=2)

        self.assertEqual(source.event.showings.count(), 5)

        # Start is in past, but should get error about missing booked_by
        response = self.client.post(url, data={
            "clone_start": "13/07/2010 20:00"
        })

        showing_count_after = Showing.objects.count()
        self.assertEqual(showing_count_after, showing_count_before)

        self.assertFormError(response, 'clone_showing_form', 'booked_by',
                             u'This field is required.')

    @patch('django.utils.timezone.now')
    def test_add_showing_in_past(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("add-showing", kwargs={"event_id": 1})
        url += "?copy_from=2"

        showing_count_before = Showing.objects.count()

        source = Showing.objects.get(id=2)

        self.assertEqual(source.event.showings.count(), 5)

        # do add/clone:
        response = self.client.post(url, data={
            "booked_by": u"Someone",
            "clone_start": u"01/01/2010 20:00"  # The past!
        })

        showing_count_after = Showing.objects.count()
        self.assertEqual(showing_count_after, showing_count_before)

        self.assertFormError(response, 'clone_showing_form', 'clone_start',
                             u'Must be in the future')

    @patch('django.utils.timezone.now')
    def test_add_showing(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("add-showing", kwargs={"event_id": 1})
        url += "?copy_from=2"

        showing_count_before = Showing.objects.count()

        source = Showing.objects.get(id=2)

        self.assertEqual(source.event.showings.count(), 5)

        # do add/clone:
        response = self.client.post(url, data={
            "booked_by": u"Someone or the other - \u20ac",
            "clone_start": "13/07/2013 20:00"
        })

        showing_count_after = Showing.objects.count()
        self.assertEqual(showing_count_after, showing_count_before + 1)

        # Get clone:
        dest = list(source.event.showings.all())[-1]

        # Check "booked by":
        self.assertEqual(dest.booked_by, u"Someone or the other - \u20ac")

        # Check fields were cloned:
        self.assertEqual(source.event_id, dest.event_id)
        self.assertEqual(source.extra_copy, dest.extra_copy)
        self.assertEqual(source.extra_copy_summary, dest.extra_copy_summary)
        self.assertEqual(source.confirmed, dest.confirmed)
        self.assertEqual(source.hide_in_programme, dest.hide_in_programme)
        self.assertEqual(source.cancelled, dest.cancelled)
        self.assertEqual(source.discounted, dest.discounted)

        # Check rota cloned:
        src_rota = source.rotaentry_set.all()
        dst_rota = dest.rotaentry_set.all()

        self.assertEqual(
            len(src_rota),
            len(dst_rota)
        )

        for src_entry, dst_entry in zip(source.rotaentry_set.all(), dest.rotaentry_set.all()):
            self.assertEqual(src_entry.role, dst_entry.role)
            self.assertEqual(src_entry.rank, dst_entry.rank)

        self.assert_return_to_index(response)


class EditShowing(DiaryTestsMixin, TestCase):

    def setUp(self):
        super(EditShowing, self).setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def tests_edit_showing_get(self):
        url = reverse("edit-showing", kwargs={"showing_id": 7})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")

        # (In the following, can't use "HTML" matching (which doesn't mind if
        # the text isn't exact, so long as it's equivalent) as the output isn't
        # currently valid HTML. Whoops.)

        # "clone" part should have expected start time:
        self.assertContains(
            response,
            u'<input id="id_clone_start" name="clone_start" type="text" value="10/06/2013 18:00" />'
        )
        # Edit should have existing values:
        self.assertContains(
            response,
            u'<input id="id_start" name="start" type="text" value="09/06/2013 18:00" />'
        )
        self.assertContains(
            response,
            u'<input id="id_booked_by" maxlength="64" name="booked_by" type="text" value="\u0102nother \u0170ser" />'
        )
        self.assertContains(
            response,
            u'<input checked="checked" id="id_confirmed" name="confirmed" type="checkbox" />'
        )
        self.assertContains(
            response,
            u'<input id="id_hide_in_programme" name="hide_in_programme" type="checkbox" />'
        )
        self.assertContains(
            response,
            u'<input id="id_cancelled" name="cancelled" type="checkbox" />'
        )
        self.assertContains(
            response,
            u'<input id="id_discounted" name="discounted" type="checkbox" />'
        )

        # Rota edit:
        self.assertContains(
            response,
            u'<input class="rota_count" id="id_role_1" name="role_1" type="text" value="0" />'
        )
        self.assertContains(
            response,
            u'<option value="2" selected="selected">'
        )
        self.assertContains(
            response,
            u'<option value="3">'
        )

    @patch('django.utils.timezone.now')
    def tests_edit_showing(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 7})
        response = self.client.post(url, data={
            u"start": u"15/08/2013 19:30",
            u"booked_by": u"Yet \u0102nother \u0170ser",
            u"confirmed": u"on",
            u"hide_in_programme": u"on",
            u"cancelled": u"on",
            u"discounted": u"on",
            u"role_1": u"3",
            u"other_roles": u"3",
        })

        self.assertEqual(response.status_code, 200)
        self.assert_return_to_index(response)

        # Check showing was updated:
        showing = Showing.objects.get(id=7)
        self.assertEqual(showing.start, pytz.utc.localize(datetime(2013, 8, 15, 18, 30)))
        self.assertEqual(showing.booked_by, u"Yet \u0102nother \u0170ser")
        self.assertEqual(showing.confirmed, True)
        self.assertEqual(showing.hide_in_programme, True)
        self.assertEqual(showing.cancelled, True)
        self.assertEqual(showing.discounted, True)
        # Check rota is as expected:
        rota = list(showing.rotaentry_set.all())
        self.assertEqual(len(rota), 4)
        self.assertEqual(rota[0].role_id, 1)
        self.assertEqual(rota[0].rank, 1)
        self.assertEqual(rota[1].role_id, 1)
        self.assertEqual(rota[1].rank, 2)
        self.assertEqual(rota[2].role_id, 1)
        self.assertEqual(rota[2].rank, 3)
        self.assertEqual(rota[3].role_id, 3)
        self.assertEqual(rota[3].rank, 1)

    @patch('django.utils.timezone.now')
    def tests_edit_showing_in_past(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 1})
        response = self.client.post(url, data={
            u"start": u"15/08/2013 19:30",
            u"booked_by": u"Valid",
            u"role_1": u"0",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")
        self.assert_has_message(response, u"Can&#39;t edit showings that are in the past", "error")

    @patch('django.utils.timezone.now')
    def tests_edit_showing_missing_data(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 3})
        response = self.client.post(url, data={
            u"start": u"",
            u"booked_by": u"",
            u"role_1": u"0",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")

        self.assertFormError(response, 'form', 'start', u'This field is required.')
        self.assertFormError(response, 'form', 'booked_by', u'This field is required.')

    @patch('django.utils.timezone.now')
    def tests_edit_showing_invalid_date_past(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 3})
        response = self.client.post(url, data={
            u"start": u"15/01/2013 19:30",
            u"booked_by": u"Valid",
            u"role_1": u"0",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")

        self.assertFormError(response, 'form', 'start', u'Must be in the future')

    @patch('django.utils.timezone.now')
    def tests_edit_showing_invalid_date_malformed(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 3})
        response = self.client.post(url, data={
            u"start": u"Spinach",
            u"booked_by": u"Valid",
            u"role_1": u"0",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")

        self.assertFormError(response, 'form', 'start', u'Enter a valid date/time.')


class DeleteShowing(DiaryTestsMixin, TestCase):

    def setUp(self):
        super(DeleteShowing, self).setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def test_delete_showing_must_post(self):

        url = reverse("delete-showing", kwargs={"showing_id": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        Showing.objects.get(id=1)  # Will raise an exception if it doesn't exist

    @patch('django.utils.timezone.now')
    def test_delete_showing_in_past(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("delete-showing", kwargs={"showing_id": 1})
        response = self.client.post(url)

        # Should redirect to edit page:
        self.assertRedirects(response, reverse("edit-showing", kwargs={"showing_id": 1}))

        # Showing should still exist:
        Showing.objects.get(id=1)  # Will raise an exception if it doesn't exist

    @patch('django.utils.timezone.now')
    def test_delete_showing(self, now_patch):
        now_patch.return_value = self._fake_now

        self.assertTrue(Showing.objects.filter(id=7))

        url = reverse("delete-showing", kwargs={"showing_id": 7})
        response = self.client.post(url)

        # Showing should have been deleted
        self.assertFalse(Showing.objects.filter(id=7))

        self.assert_return_to_index(response)


class AddEventView(DiaryTestsMixin, TestCase):

    def setUp(self):
        super(AddEventView, self).setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    @patch('django.utils.timezone.now')
    def test_get_add_event_form_default_start(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("add-event")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_new_event_and_showing.html")
        # Default start should be set one day in the future:
        self.assertContains(
            response,
            ur'<input id="id_start" name="start" value="02/06/2013 20:00" type="text" />',
            html=True
        )

    def test_get_add_event_form_specify_start(self):
        url = reverse("add-event")
        response = self.client.get(url, data={"date": "01-01-1950"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_new_event_and_showing.html")
        # Default start should be set one day in the future:
        self.assertContains(
            response,
            ur'<input id="id_start" name="start" value="01/01/1950 20:00" type="text" />',
            html=True
        )

    def test_get_add_event_form_specify_malformed_start(self):
        url = reverse("add-event")
        response = self.client.get(url, data={"date": "crisp packet"})
        self.assertContains(response, "Invalid start date", status_code=400)

    def test_get_add_event_form_specify_invalid_start(self):
        url = reverse("add-event")
        response = self.client.get(url, data={"date": "99-01-1950"})
        self.assertContains(response, "Illegal date", status_code=400)

    @patch('django.utils.timezone.now')
    def test_add_event(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("add-event")
        response = self.client.post(url, data={
            u"start": u"02/06/2013 20:00",
            u"duration": u"01:30:00",
            u"number_of_days": u"3",
            u"event_name": u"Ev\u0119nt of choic\u0119",
            u"event_template": u"1",
            u"booked_by": u"\u015Comeb\u014ddy",
            u"private": u"on",
            u"external": u"",
            u"confirmed": u"on",
            u"discounted": u"on",
        })
        # Request succeeded?
        self.assertEqual(response.status_code, 200)
        self.assert_return_to_index(response)

        # Event added correctly?
        event = Event.objects.get(name=u"Ev\u0119nt of choic\u0119")
        self.assertEqual(event.duration, time(1, 30))
        self.assertEqual(event.private, True)
        self.assertEqual(event.outside_hire, False)
        self.assertEqual(event.template, EventTemplate.objects.get(id=1))

        showings = list(event.showings.all())
        self.assertEqual(len(showings), 3)
        # Showings should have been added over 3 days. Time specified was BST,
        # so should be 7pm in UTC:
        self.assertEqual(showings[0].start, pytz.utc.localize(datetime(2013, 6, 2, 19, 0)))
        self.assertEqual(showings[1].start, pytz.utc.localize(datetime(2013, 6, 3, 19, 0)))
        self.assertEqual(showings[2].start, pytz.utc.localize(datetime(2013, 6, 4, 19, 0)))

        role_1 = Role.objects.get(id=1)
        for s in showings:
            self.assertEqual(s.booked_by, u"\u015Comeb\u014ddy")
            self.assertEqual(s.confirmed, True)
            self.assertEqual(s.hide_in_programme, False)
            self.assertEqual(s.cancelled, False)
            self.assertEqual(s.discounted, True)
            self.assertEqual(list(s.roles.all()), [role_1, ])

    @patch('django.utils.timezone.now')
    def test_add_event_in_past(self, now_patch):
        now_patch.return_value = self._fake_now

        event_count_before = Event.objects.count()

        url = reverse("add-event")
        response = self.client.post(url, data={
            u"start": u"30/05/2013 20:00",
            u"duration": u"01:30:00",
            u"number_of_days": u"3",
            u"event_name": u"Ev\u0119nt of choic\u0119",
            u"event_template": u"1",
            u"booked_by": u"\u015Comeb\u014ddy",
            u"private": u"on",
            u"external": u"",
            u"confirmed": u"on",
            u"discounted": u"on",
        })
        # Request succeeded?
        self.assertEqual(response.status_code, 200)

        # Event shouldn't have been added:
        self.assertEqual(event_count_before, Event.objects.count())

        self.assertTemplateUsed(response, "form_new_event_and_showing.html")

        # Check error was as expected:
        self.assertFormError(response, 'form', 'start', u'Must be in the future')

    @patch('django.utils.timezone.now')
    def test_add_event_missing_fields(self, now_patch):
        now_patch.return_value = self._fake_now

        event_count_before = Event.objects.count()

        url = reverse("add-event")
        response = self.client.post(url, data={
            u"start": u"",
            u"duration": u"",
            u"number_of_days": u"",
            u"event_name": u"",
            u"event_template": u"",
            u"booked_by": u"",
            u"private": u"",
            u"external": u"",
            u"confirmed": u"",
            u"discounted": u"",
        })
        # Request succeeded?
        self.assertEqual(response.status_code, 200)

        # Event shouldn't have been added:
        self.assertEqual(event_count_before, Event.objects.count())

        self.assertTemplateUsed(response, "form_new_event_and_showing.html")

        # Check error was as expected:
        self.assertFormError(response, 'form', 'start', u'This field is required.')
        self.assertFormError(response, 'form', 'duration', u'This field is required.')
        self.assertFormError(response, 'form', 'number_of_days', u'This field is required.')
        self.assertFormError(response, 'form', 'event_name', u'This field is required.')
        self.assertFormError(response, 'form', 'booked_by', u'This field is required.')


class EditEventView(DiaryTestsMixin, TestCase):

    def setUp(self):
        super(EditEventView, self).setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_edit_event_form_no_media_no_legacy_copy(self):
        url = reverse("edit-event-details", kwargs={"event_id": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")

        self.assertContains(response, u"Event one title")
        self.assertContains(response, u"Event one copy")
        self.assertContains(response, u"Event one copy summary")
        self.assertContains(response, u"01:30:00")
        self.assertContains(response, u'<input id="id_outside_hire" checked="checked" name="outside_hire" type="checkbox" />', html=True)
        self.assertContains(response, u'<input id="id_private" name="private" type="checkbox" />', html=True)
        # Blah. It's probably fine. Ahem.

    def test_get_edit_event_form_no_media_legacy_copy(self):
        # Test the transformation of legacy copy properly in a separate set of
        # tests...

        url = reverse("edit-event-details", kwargs={"event_id": 2})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")

        self.assertContains(response, u"Event two title")
        self.assertContains(response, u"Event <br>\n two <br>\n copy")  # newlines -> <br>
        self.assertContains(response, u"Event two\n copy summary")  # not stripped
        self.assertContains(response, u"01:30:00")
        self.assertContains(response, u'<input id="id_outside_hire" name="outside_hire" type="checkbox" />', html=True)
        self.assertContains(response, u'<input id="id_private" name="private" type="checkbox" />', html=True)
        # It's probably still fine. Cough.

    @override_settings(MEDIA_ROOT="/tmp")
    def test_get_edit_event_form_media_item(self):
        with tempfile.NamedTemporaryFile(dir="/tmp", prefix="toolkit-test-", suffix=".jpg") as temp_jpg:
            # Add MediaItem to event 1:
            media_item = MediaItem(media_file=temp_jpg.name, mimetype="image/jpeg", caption="Image Caption!", credit="Image Credit!")
            media_item.save()
            event = Event.objects.get(id=1)
            event.media.add(media_item)
            event.save()

            # Get page:
            url = reverse("edit-event-details", kwargs={"event_id": 1})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "form_event.html")

            self.assertContains(response, media_item.media_file)
                    # Submit the minimum amount of data to validate:
            self.assertContains(response, "Image Credit!")
            # Caption not currently exposed to user

    def test_get_edit_missing_event(self):
        url = reverse("edit-event-details", kwargs={"event_id": 1000})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_post_edit_missing_event(self):
        url = reverse("edit-event-details", kwargs={"event_id": 1000})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_post_edit_event_no_media_missing_data(self):
        url = reverse("edit-event-details", kwargs={"event_id": 1})
        response = self.client.post(url, data={})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")

        self.assertFormError(response, 'form', 'name', u'This field is required.')
        self.assertFormError(response, 'form', 'duration', u'This field is required.')

    def test_post_edit_event_no_media_minimal_data(self):
        url = reverse("edit-event-details", kwargs={"event_id": 2})

        # Submit the minimum amount of data to validate:
        response = self.client.post(url, data={
            'name': u'New \u20acvent Name',
            'duration': u'00:10:00',
        })
        self.assert_return_to_index(response)

        event = Event.objects.get(id=2)
        self.assertEqual(event.name, u'New \u20acvent Name')
        self.assertEqual(event.duration, time(0, 10))
        self.assertEqual(event.copy, u'')
        self.assertEqual(event.copy_summary, u'')
        self.assertEqual(event.terms, u'')
        self.assertEqual(event.notes, u'')
        self.assertEqual(event.media.count(), 0)
        self.assertEqual(event.outside_hire, False)
        self.assertEqual(event.private, False)
        # Shouldn't have changed:
        self.assertEqual(event.legacy_id, u'100')

    def test_post_edit_event_no_media_all_fields(self):
        url = reverse("edit-event-details", kwargs={"event_id": 2})

        # Submit the minimum amount of data to validate:
        response = self.client.post(url, data={
            'name': u'New \u20acvent Name!',
            'duration': u'01:10:09',
            'copy': u'Some more copy',
            'copy_summary': u'Copy summary blah',
            'terms': u'Always term time',
            'notes': u'This is getting\n boring',
            'outside_hire': u'on',
            'private': u'on',
        })
        self.assert_return_to_index(response)

        event = Event.objects.get(id=2)
        self.assertEqual(event.name, u'New \u20acvent Name!')
        self.assertEqual(event.duration, time(1, 10, 9))
        self.assertEqual(event.copy, u'Some more copy')
        self.assertEqual(event.copy_summary, u'Copy summary blah')
        self.assertEqual(event.terms, u'Always term time')
        self.assertEqual(event.notes, u'This is getting\n boring')
        self.assertEqual(event.media.count(), 0)
        self.assertEqual(event.outside_hire, True)
        self.assertEqual(event.private, True)
        # Shouldn't have changed:
        self.assertEqual(event.legacy_id, u'100')

    @patch("toolkit.util.image.get_mimetype")
    def test_post_edit_event_add_media_invalid_empty(self, get_mimetype_patch):

        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(dir="/tmp", prefix="toolkit-test-", suffix=".jpg") as temp_jpg:
            response = self.client.post(url, data={
                'name': u'New \u20acvent Name',
                'duration': u'00:10:00',
                'media_file': temp_jpg,
            })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")
        self.assertFormError(response, 'media_form', 'media_file', u'The submitted file is empty.')

        self.assertFalse(get_mimetype_patch.called)

        event = Event.objects.get(id=2)
        self.assertEqual(event.media.count(), 0)

    @patch("toolkit.util.image.get_mimetype")
    def test_post_edit_event_add_media_not_an_image(self, get_mimetype_patch):
        get_mimetype_patch.return_value = "text/plain"

        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(dir="/tmp", prefix="toolkit-test-", suffix=".jpg") as temp_jpg:
            temp_jpg.write("Not an empty jpeg")
            temp_jpg.seek(0)
            response = self.client.post(url, data={
                'name': u'New \u20acvent Name',
                'duration': u'00:10:00',
                'media_file': temp_jpg,
                'credit': u'All new image credit!'
            })

        self.assert_return_to_index(response)

        self.assertTrue(get_mimetype_patch.called)

        event = Event.objects.get(id=2)
        self.assertEqual(event.media.count(), 1)
        media_item = event.media.all()[0]
        self.assertEqual(media_item.mimetype, "text/plain")
        self.assertEqual(media_item.credit, u'All new image credit!')
        self.assertEqual(media_item.caption, None)

    @patch("toolkit.util.image.get_mimetype")
    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_edit_event_add_media_jpeg(self, get_mimetype_patch):
        get_mimetype_patch.return_value = "image/jpeg"

        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(dir="/tmp", prefix="toolkit-test-", suffix=".jpg") as temp_jpg:
            # used for assertion:
            temp_file_name = os.path.basename(temp_jpg.name)

            temp_jpg.write("Dummy jpeg")
            temp_jpg.seek(0)
            response = self.client.post(url, data={
                'name': u'New \u20acvent Name',
                'duration': u'00:10:00',
                'media_file': temp_jpg,
                'credit': u'All new image credit!'
            })

        self.assert_return_to_index(response)

        self.assertTrue(get_mimetype_patch.called)

        event = Event.objects.get(id=2)
        self.assertEqual(event.media.count(), 1)
        media_item = event.media.all()[0]
        self.assertEqual(media_item.mimetype, "image/jpeg")
        self.assertEqual(media_item.credit, u'All new image credit!')
        self.assertEqual(media_item.caption, None)
        self.assertEqual(media_item.media_file.name,
            os.path.join("diary", temp_file_name))

    @override_settings(MEDIA_ROOT="/tmp")
    @patch("toolkit.util.image.get_mimetype")
    def test_post_edit_event_add_media_png(self, get_mimetype_patch):
        get_mimetype_patch.return_value = "image/png"

        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(dir="/tmp", prefix="toolkit-test-", suffix=".png") as temp_png:
            # used for assertion:
            temp_file_name = os.path.basename(temp_png.name)

            temp_png.write("Dummy png")
            temp_png.seek(0)
            response = self.client.post(url, data={
                'name': u'New \u20acvent Name',
                'duration': u'00:10:00',
                'media_file': temp_png,
                'credit': u'All new image credit!'
            })

        self.assert_return_to_index(response)

        self.assertTrue(get_mimetype_patch.called)

        event = Event.objects.get(id=2)
        self.assertEqual(event.media.count(), 1)
        media_item = event.media.all()[0]
        self.assertEqual(media_item.mimetype, "image/png")
        self.assertEqual(media_item.credit, u'All new image credit!')
        self.assertEqual(media_item.caption, None)
        self.assertEqual(media_item.media_file.name,
            os.path.join("diary", temp_file_name))

    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_edit_event_clear_media(self):
        with tempfile.NamedTemporaryFile(dir="/tmp", prefix="toolkit-test-", suffix=".jpg") as temp_jpg:
            # Add MediaItem to event 1:
            media_item = MediaItem(
                media_file=temp_jpg.name, mimetype="image/jpeg", caption="Image Caption!", credit="Image Credit!")
            media_item.save()
            event = Event.objects.get(id=2)
            event.media.add(media_item)
            event.save()

            url = reverse("edit-event-details", kwargs={"event_id": 2})

            response = self.client.post(url, data={
                'name': u'New \u20acvent Name',
                'duration': u'00:10:00',
                'media_file': temp_jpg.name,
                'media_file-clear': 'on',
            })
            self.assert_return_to_index(response)

            event = Event.objects.get(id=2)
            # Media item should be gone:
            self.assertEqual(event.media.count(), 0)


class EditIdeasViewTests(DiaryTestsMixin, TestCase):

    def setUp(self):
        super(EditIdeasViewTests, self).setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_form_no_existing_ideas(self):
        # Confirm no ideas in the database for Jan 2012:
        self.assertQuerysetEqual(DiaryIdea.objects.all().filter(month=date(2012, 1, 1)), [])

        # Get the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_idea.html")

        # There should now be a Jan 2012 entry in the DB:
        idea = DiaryIdea.objects.get(month=date(2012, 1, 1))
        # With no content:
        self.assertIsNone(idea.ideas)

    def test_get_form_existing_ideas(self):
        # Ensure there's something in the DB for Jan 2012:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertTrue(created)  # Not strictly necessary
        idea.ideas = u"An ide\u0113 f\u014d\u0159 some \u20acvent"
        idea.save()

        # Get the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_idea.html")

        self.assertContains(response, u"An ide\u0113 f\u014d\u0159 some \u20acvent")

    def test_post_form_no_existing_idea(self):
        # Confirm no ideas in the database for Jan 2012:
        self.assertQuerysetEqual(DiaryIdea.objects.all().filter(month=date(2012, 1, 1)), [])

        # Post an idea to the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.post(url, data={
            "ideas": u"An ide\u0113 f\u014d\u0159 some \u20acvent",
        })

        # Check that's made it into the database:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertFalse(created)
        self.assertEqual(idea.ideas, u"An ide\u0113 f\u014d\u0159 some \u20acvent")

        self.assert_return_to_index(response)

    def test_post_form_existing_idea(self):
        # Ensure there's something in the DB for Jan 2012:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertTrue(created)  # Not strictly necessary
        idea.ideas = u"Any old junk, which shall be overwritten"
        idea.save()

        # Post an idea to the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.post(url, data={
            "ideas": u"An ide\u0113 f\u014d\u0159 some \u20acvent",
        })

        # Check that's made it into the database:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertFalse(created)
        self.assertEqual(idea.ideas, u"An ide\u0113 f\u014d\u0159 some \u20acvent")

        self.assert_return_to_index(response)


class ViewEventFieldTests(DiaryTestsMixin, TestCase):

    def setUp(self):
        super(ViewEventFieldTests, self).setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

        # Fake "now()" function to return a fixed time:
        self.time_patch = patch('django.utils.timezone.now')
        self.time_mock = self.time_patch.start()
        self.time_mock.return_value = self._fake_now

    def tearDown(self):
        self.time_patch.stop()

    def test_view_event_field_rota(self):
        url = reverse("view_event_field", kwargs={"field": "rota"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_rota.html")

        self.assertNotContains(response, u"EVENT THREE TITLE")
        self.assertContains(response, u"EVENT FOUR TITL\u0112")
        self.assertContains(response, u"Role 2 (nonstandard)-1")

    def test_view_event_field_copy(self):
        url = reverse("view_event_field", kwargs={"field": "copy"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_copy.html")

        self.assertNotContains(response, u"EVENT THREE TITLE")
        self.assertContains(response, u"Sun 09 18:00 ......... Event four titl\u0113")
        self.assertContains(response, u"<p>EVENT FOUR TITL\u0112</p>", html=True)
        self.assertContains(response, u"<p>Event four C\u014dpy</p>", html=True)

    def test_view_event_field_terms(self):
        url = reverse("view_event_field", kwargs={"field": "terms"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_terms.html")

        self.assertContains(response, u"Sun 09 18:00 ......... Event four titl\u0113")
        self.assertContains(response, u"Cube event / Public event / Confirmed")
        self.assertContains(response, u"Terminal price: \u00a31 / \u20ac3")

    def test_custom_start_date_rota_long_time(self):
        # Reverse doesn't work for full date, as regex is apparently too
        # complicated:
        url = reverse("view_event_field", kwargs={"field": "rota"})
        url += "/2013/01/01?daysahead=365"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_rota.html")

        self.assertContains(response, u"EVENT THREE TITLE")
        self.assertContains(response, u"EVENT FOUR TITL\u0112")

    def test_custom_start_date_rota_less_long_time(self):
        # Now shorter date range, should find one fewer event
        url = reverse("view_event_field", kwargs={"field": "rota"})
        url += "/2013/01/01?daysahead=120"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_rota.html")

        self.assertContains(response, u"EVENT THREE TITLE")
        self.assertNotContains(response, u"EVENT FOUR TITL\u0112")

    def test_custom_start_date_rota_invalid_date(self):
        # Now shorter date range, should find one fewer event
        url = reverse("view_event_field", kwargs={"field": "rota"})
        url += "/2013/99/99?daysahead=120"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_custom_start_date_terms_search_success(self):
        url = reverse("view_event_field", kwargs={"field": "terms"})
        url += "/2013/01/01?daysahead=365&search=Terminal"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_terms.html")

        self.assertNotContains(response, u"EVENT THREE TITLE")
        self.assertContains(response, u"EVENT FOUR TITL\u0112")

    def test_custom_start_date_terms_search_no_result(self):
        url = reverse("view_event_field", kwargs={"field": "terms"})
        url += "/2013/01/01?daysahead=365&search=elephant"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_terms.html")

        self.assertNotContains(response, u"EVENT THREE TITLE")
        self.assertNotContains(response, u"EVENT FOUR TITL\u0112")


class MailoutTests(DiaryTestsMixin, TestCase):

    def setUp(self):
        super(MailoutTests, self).setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

        # Fake "now()" function to return a fixed time:
        self.time_patch = patch('django.utils.timezone.now')
        self.time_mock = self.time_patch.start()
        self.time_mock.return_value = self._fake_now

        self.expected_mailout_header = (
            u"CUBE PROGRAMME OF EVENTS\n"
            u"\n"
            u"http://www.cubecinema.com/programme/\n"
            u"\n"
        )

        self.expected_mailout_event = (
            u"CUBE PROGRAMME OF EVENTS\n"
            u"\n"
            u"http://www.cubecinema.com/programme/\n"
            u"\n"
            u"2013\n"
            u" JUNE\n"
            u"  Sun 09 18:00 ........ Event four titl\u0113\n"
            u"\n"
            u"------------------------------------------------------------------------------\n"
            u"\n"
            u"EVENT FOUR TITL\u0112\n"
            u"\n"
            u"18:00 09/06/2013\n"
            u"\n"
            u"Event four C\u014dpy\n"
        )

    def tearDown(self):
        self.time_patch.stop()

    # Tests of edit mailout / confirm mailout form ##########################

    def test_get_form(self):
        url = reverse("members-mailout")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_mailout.html")
        self.assertContains(response, self.expected_mailout_header)
        self.assertContains(response, self.expected_mailout_event)

    def test_get_form_custom_daysahead(self):
        url = reverse("members-mailout")
        response = self.client.get(url, data={"daysahead": 15})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_mailout.html")

        self.assertContains(response, self.expected_mailout_header)
        self.assertContains(response, self.expected_mailout_event)

    def test_get_form_invalid_daysahead(self):
        url = reverse("members-mailout")
        response = self.client.get(url, data={"daysahead": "monkey"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_mailout.html")

        self.assertContains(response, self.expected_mailout_header)
        self.assertContains(response, self.expected_mailout_event)

    def test_get_form_no_events(self):
        url = reverse("members-mailout")
        response = self.client.get(url, data={"daysahead": 1})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_mailout.html")

        self.assertContains(response, self.expected_mailout_header)
        # NOT:
        self.assertNotContains(response, self.expected_mailout_event)

    def test_post_form(self):
        url = reverse("members-mailout")
        response = self.client.post(url, data={
            'subject': "Yet another member's mailout",
            'body': u"Let the bodies hit the floor\netc."
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "mailout_send.html")

    def test_post_form_no_data(self):
        url = reverse("members-mailout")
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_mailout.html")

        self.assertFormError(response, 'form', 'subject', u'This field is required.')
        self.assertFormError(response, 'form', 'body', u'This field is required.')

    def test_invalid_method(self):
        url = reverse("members-mailout")
        response = self.client.put(url)
        self.assertEqual(response.status_code, 405)

    # Tests of send mailout / Ajax form ######################################
    def test_exec_view_invalid_method(self):
        url = reverse("exec-mailout")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_exec_view_invalid_content(self):
        url = reverse("exec-mailout")
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)

        response = json.loads(response.content)
        self.assertEqual(response, {
            u"status": u"error",
            u"errors": {
                u"body": [u"This field is required."],
                u"subject": [u"This field is required."]
            }
        })

    @patch("toolkit.members.tasks.send_mailout")
    def test_exec_view_good_content(self, send_mailout_patch):
        send_mailout_patch.delay.return_value.task_id = u'dummy-task-id'

        url = reverse("exec-mailout")
        response = self.client.post(url, data={
            u"subject": u"Mailout of the month",
            u"body": u"Blah\nBlah\nBlah",
        })

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(response_data, {
            u"status": u"ok",
            u"progress": 0,
            u"task_id": u"dummy-task-id"
        })

    def test_exec_view_get_progress_invalid_method(self):
        url = reverse("mailout-progress")
        response = self.client.post(url, data={u"task_id": u"dummy-task-id"})
        self.assertEqual(response.status_code, 405)

    @patch("celery.result.AsyncResult")
    def test_exec_view_get_progress(self, async_result_patch):
        async_result_patch.return_value.state = u"PROGRESS10"
        async_result_patch.return_value.task_id = u"dummy-task-id"

        url = reverse("mailout-progress")
        response = self.client.get(url, data={u"task_id": u"dummy-task-id"})

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual({
            u'complete': False,
            u'error': None,
            u'error_msg': None,
            u'sent_count': None,
            u'progress': 10,
            u'task_id': u'dummy-task-id'
        }, response_data)

    @patch("celery.result.AsyncResult")
    def test_exec_view_get_progress_pending(self, async_result_patch):
        async_result_patch.return_value.state = u"PENDING"
        async_result_patch.return_value.task_id = u"dummy-task-id"

        url = reverse("mailout-progress")
        response = self.client.get(url, data={u"task_id": u"dummy-task-id"})

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual({
            u'complete': False,
            u'error': None,
            u'error_msg': None,
            u'sent_count': None,
            u'progress': 0,
            u'task_id': u'dummy-task-id'
        }, response_data)

    @patch("celery.result.AsyncResult")
    def test_exec_view_get_progress_failure(self, async_result_patch):
        async_result_patch.return_value.state = u"FAILURE"
        async_result_patch.return_value.task_id = u"dummy-task-id"
        async_result_patch.return_value.result = IOError("This could happen")

        url = reverse("mailout-progress")
        response = self.client.get(url, data={u"task_id": u"dummy-task-id"})

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual({
            u'complete': True,
            u'error': True,
            u'error_msg': "This could happen",
            u'sent_count': None,
            u'progress': 0,
            u'task_id': u'dummy-task-id'
        }, response_data)

    @patch("celery.result.AsyncResult")
    def test_exec_view_get_progress_failure_no_result(self, async_result_patch):
        async_result_patch.return_value.state = u"FAILURE"
        async_result_patch.return_value.task_id = u"dummy-task-id"
        async_result_patch.return_value.result = None

        url = reverse("mailout-progress")
        response = self.client.get(url, data={u"task_id": u"dummy-task-id"})

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual({
            u'complete': True,
            u'error': True,
            u'error_msg': "Failed: Unknown error",
            u'sent_count': None,
            u'progress': 0,
            u'task_id': u'dummy-task-id'
        }, response_data)

    @patch("celery.result.AsyncResult")
    def test_exec_view_get_progress_complete(self, async_result_patch):
        async_result_patch.return_value.state = u"SUCCESS"
        async_result_patch.return_value.task_id = u"dummy-task-id"
        async_result_patch.return_value.result = (False, 321, "Ok")

        url = reverse("mailout-progress")
        response = self.client.get(url, data={u"task_id": u"dummy-task-id"})

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual({
            u'complete': True,
            u'error': False,
            u'error_msg': u'Ok',
            u'sent_count': 321,
            u'progress': 100,
            u'task_id': u'dummy-task-id'
        }, response_data)

    @patch("celery.result.AsyncResult")
    def test_exec_view_get_progress_complete_bad_result(self, async_result_patch):
        async_result_patch.return_value.state = u"SUCCESS"
        async_result_patch.return_value.task_id = u"dummy-task-id"
        async_result_patch.return_value.result = "Nu?"

        url = reverse("mailout-progress")
        response = self.client.get(url, data={u"task_id": u"dummy-task-id"})

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual({
            u'complete': True,
            u'error': True,
            u'error_msg': u"Couldn't retrieve status from completed job",
            u'sent_count': 0,
            u'progress': 100,
            u'task_id': u'dummy-task-id'
        }, response_data)

    @patch("celery.result.AsyncResult")
    def test_exec_view_get_progress_complete_error(self, async_result_patch):
        async_result_patch.return_value.state = u"SUCCESS"
        async_result_patch.return_value.task_id = u"dummy-task-id"
        async_result_patch.return_value.result = (True, 322, "Error message")

        url = reverse("mailout-progress")
        response = self.client.get(url, data={u"task_id": u"dummy-task-id"})

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual({
            u'complete': True,
            u'error': True,
            u'error_msg': u'Error message',
            u'sent_count': 322,
            u'progress': 100,
            u'task_id': u'dummy-task-id'
        }, response_data)

    @patch("celery.result.AsyncResult")
    def test_exec_view_get_bad_celery_progress_data(self, async_result_patch):
        async_result_patch.return_value.state = u"PROGRESS"
        async_result_patch.return_value.task_id = u"dummy-task-id"

        url = reverse("mailout-progress")
        response = self.client.get(url, data={u"task_id": u"dummy-task-id"})

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual({
            u'complete': False,
            u'error': None,
            u'error_msg': None,
            u'sent_count': None,
            u'progress': 0,
            u'task_id': u'dummy-task-id'
        }, response_data)

    @patch("celery.result.AsyncResult")
    def test_exec_view_get_bad_celery_data(self, async_result_patch):
        async_result_patch.return_value.state = u"garbage scow"
        async_result_patch.return_value.task_id = u"dummy-task-id"

        url = reverse("mailout-progress")
        response = self.client.get(url, data={u"task_id": u"dummy-task-id"})

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual({
            u'complete': False,
            u'error': None,
            u'error_msg': None,
            u'sent_count': None,
            u'progress': 0,
            u'task_id': u'dummy-task-id'
        }, response_data)


class PreferencesTests(DiaryTestsMixin, TestCase):

    def setUp(self):
        super(PreferencesTests, self).setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def _get_edit_prefs(self, response):
        match = re.search(ur"var\s+edit_prefs\s*=\s*({.*?});", str(response), re.DOTALL)
        return json.loads(match.group(1))

    def test_set_pref(self):
        url = reverse("default-edit")

        # Get current prefs:
        response = self.client.get(url)
        edit_prefs = self._get_edit_prefs(response)
        self.assertEqual(edit_prefs["popups"], "true")

        # Set popups false:
        response = self.client.get(reverse("set_edit_preferences"),
                                   data={"popups": "false"})
        self.assertEqual(response.status_code, 200)

        # Verify change:
        response = self.client.get(url)
        edit_prefs = self._get_edit_prefs(response)
        self.assertEqual(edit_prefs["popups"], "false")

        # Back to true:
        response = self.client.get(reverse("set_edit_preferences"),
                                   data={"popups": "true"})
        self.assertEqual(response.status_code, 200)

        # Verify change:
        response = self.client.get(url)
        edit_prefs = self._get_edit_prefs(response)
        self.assertEqual(edit_prefs["popups"], "true")

    def test_set_get_single_pref(self):
        session_mock = {}
        toolkit.diary.edit_prefs.set_preference(session_mock, 'daysahead', 30)

        retrieved_pref = toolkit.diary.edit_prefs.get_preference(session_mock, 'daysahead')
        self.assertEqual(retrieved_pref, '30')

    def test_set_get_single_missing_pref(self):
        session_mock = {}
        retrieved_pref = toolkit.diary.edit_prefs.get_preference(session_mock, 'daysahead')
        self.assertEqual(retrieved_pref, '90')

    def test_set_get_single_bad_pref(self):
        session_mock = {'spangles': 'foo'}
        # Shouldn't return the value, as it's not a known pref, even tho it's
        # in the session:
        retrieved_pref = toolkit.diary.edit_prefs.get_preference(session_mock, 'spangles')
        self.assertEqual(retrieved_pref, None)

    def test_bad_value(self):
        url = reverse("default-edit")

        # Set popups something stupid:
        response = self.client.get(reverse("set_edit_preferences"),
                                   data={"popups": "tralala" * 100})
        self.assertEqual(response.status_code, 200)

        # Verify change:
        response = self.client.get(url)
        edit_prefs = self._get_edit_prefs(response)
        self.assertEqual(edit_prefs["popups"], "tralalatra")

    def test_bad_pref(self):
        url = reverse("default-edit")

        # Set weird value, verify it doesn't come out in the edit page:
        response = self.client.get(reverse("set_edit_preferences"),
                                   data={"nonsense": "tralala"})
        self.assertEqual(response.status_code, 200)

        response = self.client.get(url)
        edit_prefs = self._get_edit_prefs(response)
        self.assertEqual(edit_prefs.keys(), ["daysahead", "popups"])

    def test_redirect_change(self):
        url = reverse("cancel-edit")
        # default to javscript hackery:
        response = self.client.get(url)
        self.assert_return_to_index(response)

        # Set popup preference false:
        response = self.client.get(reverse("set_edit_preferences"),
                                   data={"popups": "false"})
        self.assertEqual(response.status_code, 200)

        # should now 302 to edit list:
        response = self.client.get(url)
        self.assertRedirects(response, reverse("default-edit"))


class UrlTests(DiaryTestsMixin, TestCase):

    """Test the regular expressions in urls.py"""

    def test_diary_urls(self):
        # Test all basic diary URLs
        calls_to_test = {
            # '/diary': (), # This is a 302...
            '/programme/view/': {},
            '/programme/view/2012': {'year': '2012'},
            '/programme/view/2012/': {'year': '2012'},
            '/programme/view/2012/12': {'year': '2012', 'month': '12'},
            '/programme/view/2012/12/': {'year': '2012', 'month': '12'},
            '/programme/view/2012/12/30': {'year': '2012', 'month': '12', 'day': '30'},
            '/programme/view/2012/12/30/': {'year': '2012', 'month': '12', 'day': '30'},
            '/programme/view/films/': {'event_type': 'films'},
            # Tags that are similar to, but aren't quite the same as, years:
            '/programme/view/1/': {'event_type': '1'},
            '/programme/view/12/': {'event_type': '12'},
            '/programme/view/123/': {'event_type': '123'},
            '/programme/view/12345/': {'event_type': '12345'},
        }
        for query, response in calls_to_test.iteritems():
            match = resolve(query)
            self.assertEqual(match.func.__name__, "view_diary")
            for k, v in response.iteritems():
                self.assertEqual(match.kwargs[k], v)

    def test_diary_invalid_urls(self):
        # Test all basic diary URLs

        calls_to_test = (
            '/diary/123',
            '/diary/-123',
            '/diary/-2012/',
            '/diary/2012//',
            '/diary/2012///',
        )
        for query in calls_to_test:
            self.assertRaises(django.http.Http404, resolve, query)

    def test_diary_edit_urls(self):
        # Test all basic diary URLs

        calls_to_test = {
            '/diary/edit': {},
            '/diary/edit/': {},
            '/diary/edit/2012': {'year': '2012'},
            '/diary/edit/2012/': {'year': '2012'},
            '/diary/edit/2012/12': {'year': '2012', 'month': '12'},
            '/diary/edit/2012/12/': {'year': '2012', 'month': '12'},
            '/diary/edit/2012/12/30': {'year': '2012', 'month': '12', 'day': '30'},
            '/diary/edit/2012/12/30/': {'year': '2012', 'month': '12', 'day': '30'},
        }
        for query, response in calls_to_test.iteritems():
            match = resolve(query)
            self.assertEqual(match.func.__name__, "edit_diary_list")
            for k, v in response.iteritems():
                self.assertEqual(match.kwargs[k], v)

    def test_diary_rota_urls(self):
        # Test all basic diary URLs

        calls_to_test = {
            '/diary/rota': {'field': 'rota'},
            '/diary/rota/': {'field': 'rota'},
            '/diary/rota/2012/12': {'field': 'rota', 'year': '2012', 'month': '12'},
            '/diary/rota/2012/12/': {'field': 'rota', 'year': '2012', 'month': '12'},
            '/diary/rota/2012/12/30': {'field': 'rota', 'year': '2012', 'month': '12', 'day': '30'},
            '/diary/rota/2012/12/30/': {'field': 'rota', 'year': '2012', 'month': '12', 'day': '30'},
            '/diary/rota/2012/12//': {'field': 'rota', 'year': '2012', 'month': '12', 'day': ''},
        }
        # (rota URLS must have at least year/month, not just a year!)
        for query, response in calls_to_test.iteritems():
            match = resolve(query)
            self.assertEqual(match.func.__name__, "view_event_field")
            for k, v in response.iteritems():
                self.assertEqual(match.kwargs[k], v)


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
