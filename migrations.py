import webapp2
from dieci_e_lotto.migrations import UpdateSchema
from google.appengine.ext import deferred


class UpdateHandler(webapp2.RequestHandler):
    def get(self):
        deferred.defer(UpdateSchema)
        self.response.out.write('Schema migration successfully initiated.')

app = webapp2.WSGIApplication([('/update_schema', UpdateHandler)])
