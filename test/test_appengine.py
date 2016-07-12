import os
import mock
import json
import webapp2
import webtest
import unittest
from dieci_e_lotto import wish
from datetime import datetime
from dieci_e_lotto.wish import Draw
from main import ScheduleFetchDraw
from main import FetchDraw
from google.appengine.ext import ndb
from google.appengine.ext import testbed
from google.appengine.api import memcache
from dieci_e_lotto.dieci_e_lotto import start_synchronization


class DatastoreTestCase(unittest.TestCase):

    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        ndb.get_context().clear_cache()

        draws_8 = [Draw.create(2015, 8, d, n, [1, 2, 3, 4, 5], 1)
                   for d in range(10) for n in range(10)]
        draws_9 = [Draw.create(2015, 9, d, n, [1, 2, 3, 4, 5], 1)
                   for d in range(10) for n in range(10)]
        ndb.put_multi(draws_8)
        ndb.put_multi(draws_9)

    def tearDown(self):
        self.testbed.deactivate()

    def test_query_by_month(self):
        d8 = Draw.by_month(2015, 8)
        self.assertEqual(100, len(d8))

        self.assertFalse((2016, 9, 11, 3) in d8)
        self.assertTrue((2015, 8, 1, 1) in d8)

    def test_is_downloaded_already(self):
        self.assertTrue(wish.is_downloaded_already(2015, 8, 1, 1))

    def test_is_not_downloaded(self):
        self.assertFalse(wish.is_downloaded_already(2016, 1, 1, 1))

    def test_save_draw(self):
        lots = range(1, 21)
        jolly = 90
        year, month, day, nth = 2017, 7, 11, 1
        date = datetime(year, month, day)
        wish.save_draw(date, nth, lots, jolly)
        self.assertTrue(wish.is_downloaded_already(year, month, day, nth))
        got = Draw.get_by_id(Draw.draw_id(
            year, month, day, nth), parent=Draw.month_key(year, month))
        self.assertEqual(got.lots, lots)
        self.assertEqual(got.jolly, jolly)

    if __name__ == '__main__':
        unittest.main()


class FetchDrawTest(unittest.TestCase):
    def setUp(self):
        app = webapp2.WSGIApplication([
            ('/task/fetch', FetchDraw)
        ])
        self.testapp = webtest.TestApp(app)
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        ndb.get_context().clear_cache()
        queue_yaml_dir = os.path.dirname(os.path.dirname(__file__))
        self.testbed.init_taskqueue_stub(root_path=queue_yaml_dir)
        with open('test/fixtures/draw.json', 'r') as draw:
            self.draw_mock = draw.read()

    def tearDown(self):
        self.testbed.deactivate()

    @mock.patch('dieci_e_lotto.wish.is_downloaded_already')
    @mock.patch('dieci_e_lotto.wish.fetch_draw')
    def test_fetch(self, mock_fetch, already):
        mock_fetch.return_value = self.draw_mock

        params = json.dumps({'year': 2016, 'month': 7, 'day': 1, 'nth': 1})
        response = self.testapp.post(
            '/task/fetch', params)
        self.assertEqual(response.status_int, 200)
        mock_fetch.assert_called_once()
        already.assert_called_with(2016, 7, 1, 1)
        self.assertTrue(wish.is_downloaded_already(2016, 7, 1, 1))


class AppTest(unittest.TestCase):
    def setUp(self):
        app = webapp2.WSGIApplication([
            ('/schedule/fetch', ScheduleFetchDraw)
        ])
        self.testapp = webtest.TestApp(app)
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        queue_yaml_dir = os.path.dirname(os.path.dirname(__file__))
        self.testbed.init_taskqueue_stub(root_path=queue_yaml_dir)

    def test_schedule_fetch_draw(self):
        params = json.dumps({'year': 2016, 'month': 7, 'day': 1, 'nth': 1})
        response = self.testapp.post(
            '/schedule/fetch', params)
        self.assertEqual(response.status_int, 200)
        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        names = [queue['name'] for queue in q_stub.GetQueues()]
        self.assertGreater(len(names), 0)
        self.assertIn('fetch-draws', names)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")
        self.assertGreater(len(tasks), 0)
        # cleanup
        q_stub.FlushQueue("fetch-draws")
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")
        self.assertEqual(len(tasks), 0)

    @mock.patch('dieci_e_lotto.wish.get_downloaded_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_synchronize_all_unneeded_synch(self,
                                            last_draw, downloaded):
        wish.MAX_DAYS_IN_THE_PAST = 0

        # STUB get_last_draw
        now = datetime.today()
        last_draw.return_value = (now.year, now.month, now.day, 4)

        # STUB downloaded_by_month
        downloaded.return_value = set([
            (now.year, now.month, now.day, i)
            for i in range(1, 5)])

        self.assertIn(
            (now.year, now.month, now.day, 4),
            downloaded.return_value)

        self.assertNotIn(
            (now.year, now.month, now.day, 5),
            downloaded.return_value)

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")
        self.assertEqual(len(tasks), 0)

    @mock.patch('dieci_e_lotto.wish.get_downloaded_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_synchronize_enquee_one(self,
                                    last_draw, downloaded):
        wish.MAX_DAYS_IN_THE_PAST = 0

        # STUB get_last_draw
        now = datetime.today()
        last_draw.return_value = (now.year, now.month, now.day, 288)

        # STUB downloaded_by_month
        downloaded.return_value = set([
            (now.year, now.month, now.day, i)
            for i in range(1, 288)])

        self.assertIn(
            (now.year, now.month, now.day, 287),
            downloaded.return_value)

        self.assertNotIn(
            (now.year, now.month, now.day, 288),
            downloaded.return_value)

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        single = json.loads(tasks[0].payload)
        self.assertEqual(single, {
            'year': now.year,
            'month': now.month,
            'day': now.day,
            'nth': 288
        })

        self.assertEqual(len(tasks), 1)

    @mock.patch('dieci_e_lotto.wish.get_downloaded_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_synchronize_enquee_some(self,
                                     last_draw, downloaded):
        wish.MAX_DAYS_IN_THE_PAST = 0

        # STUB get_last_draw
        now = datetime.today()
        last_draw.return_value = (now.year, now.month, now.day, 288)

        # STUB downloaded_by_month
        downloaded.return_value = set([
            (now.year, now.month, now.day, i)
            for i in range(1, 189)])

        self.assertIn(
            (now.year, now.month, now.day, 188),
            downloaded.return_value)

        self.assertNotIn(
            (now.year, now.month, now.day, 189),
            downloaded.return_value)

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        self.assertEqual(len(tasks), 100)

    @mock.patch('dieci_e_lotto.wish.get_downloaded_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_synchronize_enquee_previous_day(self,
                                             last_draw, downloaded):
        wish.MAX_DAYS_IN_THE_PAST = 1

        # STUB get_last_draw
        now = datetime.today()
        last_draw.return_value = (now.year, now.month, now.day, 1)

        # STUB downloaded_by_month
        downloaded.return_value = set()

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        self.assertEqual(len(tasks), 289)

    def tearDown(self):
        self.testbed.deactivate()
