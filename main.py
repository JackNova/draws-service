#!/usr/bin/env python

import os
import config
import jinja2
import webapp2
from google.appengine.api import taskqueue
from dieci_e_lotto.handlers import FetchDraw
from dieci_e_lotto.handlers import DownloadAll
from dieci_e_lotto.handlers import DrawsMonitoring
from dieci_e_lotto.handlers import MonthMonitoring

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class MainHandler(webapp2.RequestHandler):

    def get(self):
        self.response.write("HELLO WORLD")


class ScheduleDownloadAll(webapp2.RequestHandler):

    def get(self):
        taskqueue.add(url="/task/download-all")


class ScheduleFetchDraw(webapp2.RequestHandler):

    def post(self):
        taskqueue.add(url="/task/fetch-draw",
                      queue_name="fetch-draws", payload=self.request.body)

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/monitoring/10-e-lotto/(\d+)/(\d+)/(\d+)', DrawsMonitoring),
    ('/monitoring/10-e-lotto/(\d+)/(\d+)', MonthMonitoring),
    ('/schedule/download-all', ScheduleDownloadAll),
    ('/task/download-all', DownloadAll),
    ('/schedule/fetch-draw', ScheduleFetchDraw),
    ('/task/fetch-draw', FetchDraw)
], debug=(config.id == 'develop'), config=None)
