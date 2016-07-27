import os
import webapp2
import webtest
import unittest
from google.appengine.ext import ndb
from google.appengine.ext import testbed
from google.appengine.api import memcache
import migrations
from dieci_e_lotto.migrations import UpdateSchema
from dieci_e_lotto.repository import get_by_month


class Draw(ndb.Model):
    year = ndb.IntegerProperty()
    month = ndb.IntegerProperty()
    day = ndb.IntegerProperty()
    nth = ndb.IntegerProperty()
    lots = ndb.IntegerProperty(repeated=True)
    jolly = ndb.IntegerProperty()


def create_old_draws():
    xs = [Draw(year=2016, month=1, day=1, nth=i, lots=[1, 2, 3], jolly=43)
          for i in range(1, 21)]
    ndb.put_multi(xs)


class UpdateSchemaTestCase(unittest.TestCase):
    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        ndb.get_context().clear_cache()
        queue_yaml_dir = os.path.dirname(os.path.dirname(__file__))
        self.testbed.init_taskqueue_stub(root_path=queue_yaml_dir, auto_task_running=True)

        app = webapp2.WSGIApplication([
            ('/update-schema', migrations.UpdateHandler)
        ])
        self.testapp = webtest.TestApp(app)

    def tearDown(self):
        self.testbed.deactivate()

    def test_enqueue_update_schema(self):
        response = self.testapp.get('/update-schema')
        self.assertEqual(response.status_int, 200)
        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        task = q_stub.get_filtered_tasks(
            url="/_ah/queue/deferred", queue_names="default")[0]
        self.assertIsNotNone(task)

    def test_update_schema(self):
        create_old_draws()
        self.assertEqual(len(get_by_month(2016, 1)), 0)
        draws = Draw.query().fetch()
        self.assertEqual(len(draws), 20)
        UpdateSchema()
        draws_after = Draw.query().fetch()
        self.assertEqual(len(draws_after), 0)
        ndbDraws = get_by_month(2016, 1)
        self.assertEqual(len(ndbDraws), 20)
