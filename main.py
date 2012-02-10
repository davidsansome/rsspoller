import feedparser
import logging
import re
import traceback
import webapp2

from google.appengine.api import mail
from google.appengine.api import urlfetch
from google.appengine.ext import db

FEED_URL  = "http://www.raspberrypi.org/feed"
SENDER    = "RSS Poller <davidsansome@gmail.com>"
RECEIVERS = [
  "me@davidsansome.com",
]


class FetchError(Exception):
  pass


class FeedEntry(db.Model):
  pass


class PollHandler(webapp2.RequestHandler):
  def get(self):
    if self.request.headers.get("X-AppEngine-Cron", None) != "true":
      self.error(403)
      return

    try:
      self.FetchAndEmail()
    except Exception as ex:
      logging.exception("An error occurred")
      self.SendEmail("RSS poller error", traceback.format_exc())

  def FetchAndEmail(self):
    # Fetch the contents of the feed
    result = urlfetch.fetch(FEED_URL)
    if result.status_code != 200:
      raise FetchError("Got HTTP status %d" % result.status_code)

    # Parse the feed
    feed = feedparser.parse(result.content)

    # Check each entry
    for entry in feed.entries:
      if FeedEntry.get_by_key_name(entry.id) is not None:
        # Already emailed about this entry
        continue

      logging.info("New entry ID '%s'" % entry.id)

      # Send the email and update datastore
      self.SendEmail(entry.title, '<p><a href="%s">%s</a></p>%s' % (
          entry.link, entry.link, entry.content[0].value))

      FeedEntry(key_name=entry.id).put()

  
  def SendEmail(self, subject, body):
    logging.info("Sending email with subject '%s'" % subject)

    for receiver in RECEIVERS:
      logging.info(" ... to '%s'" % receiver)
      mail.send_mail(
        sender=SENDER,
        to=receiver,
        subject=subject,
        body=body,
        html=body)


app = webapp2.WSGIApplication([
  ("/tasks/poll", PollHandler),
])