# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models
from django.utils.text import slugify

class Migration(DataMigration):

    def forwards(self, orm):
        for tag in orm.EventTag.objects.all():
            tag.slug = slugify(tag.name)
            tag.save()

    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        u'diary.diaryidea': {
            'Meta': {'object_name': 'DiaryIdea', 'db_table': "'DiaryIdeas'"},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ideas': ('django.db.models.fields.TextField', [], {'max_length': '16384', 'null': 'True', 'blank': 'True'}),
            'month': ('django.db.models.fields.DateField', [], {}),
            'updated_at': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        u'diary.event': {
            'Meta': {'object_name': 'Event', 'db_table': "'Events'"},
            'copy': ('django.db.models.fields.TextField', [], {'max_length': '8192', 'null': 'True', 'blank': 'True'}),
            'copy_summary': ('django.db.models.fields.TextField', [], {'max_length': '4096', 'null': 'True', 'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'duration': ('django.db.models.fields.TimeField', [], {'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'legacy_copy': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'legacy_id': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True'}),
            'media': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['diary.MediaItem']", 'db_table': "'Event_MediaItems'", 'symmetrical': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '4096', 'null': 'True', 'blank': 'True'}),
            'outside_hire': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'private': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['diary.EventTag']", 'symmetrical': 'False', 'db_table': "'Event_Tags'", 'blank': 'True'}),
            'template': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'template'", 'null': 'True', 'to': u"orm['diary.EventTemplate']"}),
            'terms': ('django.db.models.fields.TextField', [], {'default': "'Contacts-\\nCompany-\\nAddress-\\nEmail-\\nPh No-\\nHire Fee (inclusive of VAT, if applicable) -\\nFinancial Deal (%/fee/split etc)-\\nDeposit paid before the night (p/h only) -\\nAmount needed to be collected (p/h only) -\\nSpecial Terms -\\nTech needed -\\nAdditonal Info -'", 'max_length': '4096', 'null': 'True', 'blank': 'True'}),
            'updated_at': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        u'diary.eventtag': {
            'Meta': {'ordering': "['name']", 'object_name': 'EventTag', 'db_table': "'EventTags'"},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '32'}),
            'read_only': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50'})
        },
        u'diary.eventtemplate': {
            'Meta': {'ordering': "['name']", 'object_name': 'EventTemplate', 'db_table': "'EventTemplates'"},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'roles': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['diary.Role']", 'db_table': "'EventTemplates_Roles'", 'symmetrical': 'False'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['diary.EventTag']", 'symmetrical': 'False', 'db_table': "'EventTemplate_Tags'", 'blank': 'True'}),
            'updated_at': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        u'diary.mediaitem': {
            'Meta': {'object_name': 'MediaItem', 'db_table': "'MediaItems'"},
            'caption': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'credit': ('django.db.models.fields.CharField', [], {'default': "'Internet scavenged'", 'max_length': '256', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'media_file': ('django.db.models.fields.files.FileField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'mimetype': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        u'diary.printedprogramme': {
            'Meta': {'object_name': 'PrintedProgramme', 'db_table': "'PrintedProgrammes'"},
            'designer': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'month': ('django.db.models.fields.DateField', [], {'unique': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '8192', 'null': 'True', 'blank': 'True'}),
            'programme': ('django.db.models.fields.files.FileField', [], {'max_length': '256'})
        },
        u'diary.role': {
            'Meta': {'ordering': "['name']", 'object_name': 'Role', 'db_table': "'Roles'"},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            'read_only': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'standard': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'diary.rotaentry': {
            'Meta': {'ordering': "['role', 'rank']", 'object_name': 'RotaEntry', 'db_table': "'RotaEntries'"},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rank': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'required': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'role': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['diary.Role']"}),
            'showing': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['diary.Showing']"})
        },
        u'diary.showing': {
            'Meta': {'ordering': "['start']", 'object_name': 'Showing', 'db_table': "'Showings'"},
            'booked_by': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'cancelled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'discounted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'event': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'showings'", 'to': u"orm['diary.Event']"}),
            'extra_copy': ('django.db.models.fields.TextField', [], {'max_length': '4096', 'null': 'True', 'blank': 'True'}),
            'extra_copy_summary': ('django.db.models.fields.TextField', [], {'max_length': '4096', 'null': 'True', 'blank': 'True'}),
            'hide_in_programme': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'roles': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['diary.Role']", 'through': u"orm['diary.RotaEntry']", 'symmetrical': 'False'}),
            'start': ('toolkit.diary.models.FutureDateTimeField', [], {'db_index': 'True'}),
            'updated_at': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['diary']
    symmetrical = True
