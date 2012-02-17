import difflib
import feedparser
import logging
import re
import traceback
import webapp2

from google.appengine.api import mail
from google.appengine.api import urlfetch
from google.appengine.ext import db

FEED_URL  = "http://www.raspberrypi.org/feed"
STORE_URL = "http://raspberrypi.com/"

SCRIPT_RE = re.compile(r'<script.*?</script>', re.DOTALL)

SENDER    = "RSS Poller <davidsansome@gmail.com>"
RECEIVERS = [
  "me@davidsansome.com",
]


class FetchError(Exception):
  pass


class FeedEntry(db.Model):
  pass


class StorePage(db.Model):
  content = db.BlobProperty(default="")


class PollHandler(webapp2.RequestHandler):
  def get(self):
    #if self.request.headers.get("X-AppEngine-Cron", None) != "true":
    #  self.error(403)
    #  return

    try:
      self.FetchFeed()
    except Exception as ex:
      logging.exception("Error fetching feed")
      self.SendEmail("Error fetching feed", traceback.format_exc())
    
    try:
      self.FetchStore()
    except Exception as ex:
      logging.exception("Error fetching store")
      self.SendEmail("Error fetching store", traceback.format_exc())

  def FetchFeed(self):
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
      html = '<p><a href="%s">%s</a></p>%s' % (
          entry.link, entry.link, entry.content[0].value)
      self.SendEmail(entry.title, html, html)

      FeedEntry(key_name=entry.id).put()
  
  def FetchStore(self):
    # Get the current store page
    current = urlfetch.fetch(STORE_URL)
    if current.status_code != 200:
      raise FetchError("Got HTTP status %d" % current.status_code)
    
    current_content = SCRIPT_RE.sub("", current.content)

    # Get the old store page
    try:
      old_content_instance = StorePage.all()[0]
    except IndexError:
      old_content_instance = StorePage()
    
    old_content = old_content_instance.content

    # Are they the same?
    if old_content == current_content:
      return

    # Make the diffs and send the email
    unified = "".join(difflib.unified_diff(
      old_content.splitlines(True),
      current_content.splitlines(True)))
    
    self.SendEmail("Store page changed", unified)

    # Store the new content in datastore
    old_content_instance.content = current_content
    old_content_instance.put()
  
  def SendEmail(self, subject, body, html_body=None):
    logging.info("Sending email with subject '%s'" % subject)
    logging.info(body)

    for receiver in RECEIVERS:
      logging.info(" ... to '%s'" % receiver)

      kwargs = {
        "sender": SENDER,
        "to": receiver,
        "subject": subject,
        "body": body,
      }

      if html_body is not None:
        kwargs["html_body"] = html_body

      mail.send_mail(**kwargs)


app = webapp2.WSGIApplication([
  ("/tasks/poll", PollHandler),
])
