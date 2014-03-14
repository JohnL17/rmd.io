#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# vim: autoindent expandtab tabstop=4 sw=4 sts=4 filetype=python

import re
import email
from django.utils import timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mails.models import Mail, SentStatistic
from mails import tools
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        try:
            imap = tools.imap_login()
            smtp = tools.smtp_login()
            mails_to_send = Mail.objects.filter(due__lte=timezone.now())
        except:
            return

        for mail_to_send in mails_to_send:

            imap_mail_ids = tools.mails_with_id(mail_to_send.id, imap)

            for mail_in_imap in imap_mail_ids:

                results, data = imap.fetch(mail_in_imap, 'RFC822')
                raw_email = data[0][1]

                original_msg = email.message_from_string(raw_email)
                charset = original_msg.get_content_charset()
                text = 'This mail was originally sent to: %s' % mail_to_send.sent_to

                if original_msg.is_multipart():
                    add_text = MIMEText(text, 'plain', 'utf-8')
                    if original_msg.get_content_maintype == 'multipart/signed':
                        # If it's a signed message, only take first payload
                        msg = MIMEMultipart()
                        orig = original_msg.get_payload(0)
                        msg.attach(orig)
                        msg.attach(add_text)
                    else:
                        msg = MIMEMultipart()
                        msg.attach(original_msg)
                        msg.attach(add_text)

                else:
                    msg = MIMEText(original_msg.get_payload(), 'plain', charset)

                try:
                    msg['Subject'] = "Reminder from %s: %s" % (
                        mail_to_send.sent.strftime('%b %d %H:%M'),
                        mail_to_send.subject
                    )
                    msg['From'] = settings.EMAIL_ADDRESS
                    msg['To'] = mail_to_send.sent_from
                    msg['Date'] = email.utils.formatdate(localtime=True)
                    msg['References'] = original_msg['Message-ID']
                except:
                    tools.delete_imap_mail(mail_in_imap)
                    print('Failed to write new header')
                    break

                if not msg.is_multipart():
                    # Attachs text if isn't a multipart message
                    msg = str(msg) + '\n\n' + str(text)

                smtp.sendmail(
                    settings.EMAIL_ADDRESS,
                    mail_to_send.sent_from,
                    str(msg)
                )
                l = SentStatistic(
                    date=timezone.now()
                )
                l.save()

            tools.delete_imap_mail(mail_to_send.id)
            mail_to_send.delete()

        smtp.quit()
        imap.logout()
