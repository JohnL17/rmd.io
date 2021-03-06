import smtplib
import logging
from django.utils import timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mails.models import Statistic, Due
from mails import imaphelper
from django.core.management.base import BaseCommand
from django.conf import settings
from django.template import Context
from django.template.loader import get_template
from django.core.mail import EmailMessage


logger = logging.getLogger('mails')


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        try:
            smtp = smtplib.SMTP(settings.EMAIL_HOST)
            smtp.starttls()
            smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        except:
            return

        dues = Due.objects.filter(due__lte=timezone.now())

        for due in dues:
            mail = due.mail

            imap_conn = imaphelper.get_connection()
            try:
                message = imaphelper.IMAPMessage.from_dbid(mail.id, imap_conn)
            except IndexError:
                mail.delete()
                logger.warning(
                    'Imap message of mail {} could not be found'
                    .format(mail.id)
                )

                return

            charset = message.msg.get_content_charset()
            recipients = mail.recipient_set
            tpl = get_template('mails/messages/mail_attachment.txt')
            text = tpl.render(
                Context({
                    'recipients': recipients
                })
            )

            if message.msg.is_multipart():
                add_text = MIMEText(text, 'plain', 'utf-8')
                if message.msg.get_content_maintype == 'multipart/signed':
                    # If it's a signed message, only take first payload
                    msg = MIMEMultipart()
                    orig = message.msg.get_payload(0)
                    msg.attach(orig)
                    msg.attach(add_text)
                else:
                    msg = MIMEMultipart()
                    msg.attach(message.msg)
                    msg.attach(add_text)

            else:
                msg = MIMEText(
                    '\n\n'.join((message.msg.get_payload(), str(text))),
                    'plain',
                    charset
                )

            try:
                for i in message.msg.walk():
                    if i.get_content_maintype() == 'text':
                        content = i.get_payload(decode=True)
                        break

                attachments = []
                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    attachments.append(part)

                email = EmailMessage(
                    "Reminder from {}: {}".format(mail.sent.strftime('%b %d %H:%M'), mail.subject),
                    content.decode("utf-8") + text ,
                    settings.EMAIL_HOST_USER,
                    [mail.user.email],
                )
                for attachment in attachments:
                    email.attach(
                        attachment.get_filename(),
                        attachment.get_payload(decode=True),
                        attachment.get_content_type()
                    )
                email.send(fail_silently=False)

            except:
                message.delete()
                print('Failed to write new header')
                break

            l = Statistic(
                type='SENT',
                email=mail.user.email,
                date=timezone.now()
            )
            l.save()

            due.delete()

            if not mail.due_set.count():
                message.delete()
                mail.delete()

        smtp.quit()
