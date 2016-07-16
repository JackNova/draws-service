#!/usr/bin/env python

import webapp2
from google.appengine.api import taskqueue
from dieci_e_lotto.handlers import FetchDraw
from dieci_e_lotto.handlers import DownloadAll


class MainHandler(webapp2.RequestHandler):

    def get(self):
        self.response.write('Hello world!')


class ScheduleDownloadAll(webapp2.RequestHandler):

    def post(self):
        taskqueue.add(url="/task/download-all")


class ScheduleFetchDraw(webapp2.RequestHandler):

    def post(self):
        taskqueue.add(url="/task/fetch-draw",
                      queue_name="fetch-draws", payload=self.request.body)

config = {}
app = webapp2.WSGIApplication([
    ('/schedule/download-all', ScheduleDownloadAll),
    ('/task/download-all', DownloadAll),
    ('/schedule/fetch-draw', ScheduleFetchDraw),
    ('/task/fetch-draw', FetchDraw)
], debug=True, config=config)
