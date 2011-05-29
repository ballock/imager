#~ Copyright (C) 2010 Nokia Corporation and/or its subsidiary(-ies).
#~ Contact: Ramez Hanna <ramez.hanna@nokia.com>
#~ This program is free software: you can redistribute it and/or modify
#~ it under the terms of the GNU General Public License as published by
#~ the Free Software Foundation, either version 3 of the License, or
#~ (at your option) any later version.

#~ This program is distributed in the hope that it will be useful,
#~ but WITHOUT ANY WARRANTY; without even the implied warranty of
#~ MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#~ GNU General Public License for more details.

#~ You should have received a copy of the GNU General Public License
#~ along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.db import models
import img_web.settings as settings
from django.contrib.auth.models import User
from django.contrib import admin
from django.db.models.signals import post_save, post_delete
import django.dispatch
from RuoteAMQP import Launcher

GETLOG = django.dispatch.Signal(providing_args=["image_id"])

def launch(process, fields):

    launcher = Launcher(amqp_host = settings.boss_host,
                        amqp_user = settings.boss_user,
                        amqp_pass = settings.boss_pass,
                        amqp_vhost = settings.boss_vhost)

    launcher.launch(process, fields)

def imagejob_getlog(sender, **kwargs):
    with open(settings.getlog_process, mode='r') as process_file:
        process = process_file.read()

    fields = {"image" : {"image_id" : kwargs['image_id']}}

    launch(process, fields)

def imagejob_delete_callback(sender, **kwargs):
    pass

def imagejob_save_callback(sender, **kwargs):
    if kwargs['created']:
        try:
            with open(settings.create_image_process, mode='r') as process_file:
                process = process_file.read()
    
            job = kwargs['instance']

            fields = {"image" : { 
                                  "emails" :  [ i.strip() for i in \
                                                job.email.split(',') ],
                                  "kickstart" : job.kickstart,
                                  "image_id" : job.image_id,
                                  "image_type" : job.image_type,
                                  "name" : job.name,
                                  "arch" : job.arch,
                                  "prefix" : "%s/%s" % (job.queue.name,
                                                        job.user.username)
                                  }
                        }
            if job.release:
                fields['image']['release'] = job.release
            if job.overlay:
                fields['image']['packages'] = job.overlay.split(",")
            if job.extra_repos:
                fields['image']['extra_repos'] = job.extra_repos.split(",")
            if job.test_image:
                fields['image']['test_image'] = job.test_image
                fields['image']['devicegroup'] = job.devicegroup
    
            launch(process, fields)

        except Exception, error:
            kwargs['instance'].status = "ERROR"
            kwargs['instance'].error = error
            kwargs['instance'].save()
    else:
        #launch notify and test if configured and asked for
        job = kwargs['instance']
        if job.status == "DONE" or job.status == "ERROR":
            if settings.notify_enabled and job.notify:
                with open(settings.notify_process, mode='r') as process_file:
                    process = process_file.read()

                launch(process, fields)

        if job.status == "DONE":
            if settings.testing_enabled and job.test_image:
                with open(settings.test_process, mode='r') as process_file:
                    process = process_file.read()

                launch(process, fields)


class Queue(models.Model):    
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name

class ImageJob(models.Model):    
    image_id = models.CharField(max_length=30)
    created = models.DateTimeField(auto_now_add=True)
    done = models.DateTimeField(blank=True, null=True)
    queue = models.ForeignKey(Queue)

    user = models.ForeignKey(User)
    email = models.TextField(blank=True)
    notify = models.BooleanField(blank=True, default=False)

    test_image = models.BooleanField(blank=True, default=False)
    devicegroup = models.CharField(blank=True, max_length=100)
    test_options = models.TextField(blank=True)
    test_result = models.BooleanField(blank=True, default=False)

    image_type = models.CharField(max_length=10)
    release = models.CharField(max_length=50, blank=True)
    arch = models.CharField(max_length=10)

    overlay = models.CharField(max_length=500, blank=True)
    extra_repos = models.CharField(max_length=800, blank=True)
    
    kickstart = models.TextField()
    name = models.CharField(max_length=100)

    status = models.CharField(max_length=30, default="IN QUEUE")
    image_url = models.CharField(max_length=500, blank=True)
    files_url = models.CharField(max_length=500, blank=True)
    logfile_url = models.CharField(max_length=500, blank=True)
    log = models.TextField(blank=True)
    error = models.CharField(max_length=1000, blank=True)

class ImageJobAdmin(admin.ModelAdmin):
    list_display = ('image_id', 'user', 'arch', 'image_type', 'status', 'queue')
    list_filter = ('user', 'arch', 'image_type', 'status', 'queue')

class QueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

admin.site.register(ImageJob, ImageJobAdmin)
admin.site.register(Queue, QueueAdmin)

post_save.connect(imagejob_save_callback, sender=ImageJob, weak=False,
                  dispatch_uid="imagejob_save_callback")

post_delete.connect(imagejob_delete_callback, sender=ImageJob, weak=False,
                    dispatch_uid="imagejob_delete_callback")

GETLOG.connect(imagejob_getlog, weak=False,
               dispatch_uid="imagejob_getlog")
