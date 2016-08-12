import os
import sys
import mock
import json
import config
import webapp2
import webtest
import unittest
from main import FetchDraw
from datetime import datetime
from datetime import timedelta
from dieci_e_lotto import wish
from calendar import monthrange
from main import ScheduleFetchDraw
from main import ScheduleDownloadAll
from google.appengine.ext import ndb
from dieci_e_lotto.entities import Draw
import dieci_e_lotto.repository as repo
from google.appengine.ext import testbed
from google.appengine.api import memcache
from dieci_e_lotto.repository import NdbDraw
from dieci_e_lotto.handlers import handle_fetch
from dieci_e_lotto.handlers import start_synchronization
import logging


class DatastoreTestCase(unittest.TestCase):

    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        ndb.get_context().clear_cache()

        draws_8 = [NdbDraw.create(2015, 8, d, n, [1, 2, 3, 4, 5], 1)
                   for d in range(10) for n in range(10)]
        draws_9 = [NdbDraw.create(2015, 9, d, n, [1, 2, 3, 4, 5], 1)
                   for d in range(10) for n in range(10)]
        ndb.put_multi(draws_8)
        ndb.put_multi(draws_9)

    def tearDown(self):
        self.testbed.deactivate()

    def test_query_by_month(self):
        d8 = set([(x.year, x.month, x.day, x.nth)
                  for x in NdbDraw.query_by_month(2015, 8)])
        self.assertEqual(100, len(d8))

        self.assertFalse((2016, 9, 11, 3) in d8)
        self.assertTrue((2015, 8, 1, 1) in d8)

    def test_is_downloaded_already(self):
        already = repo.get_nth_in_day(2015, 8, 1, 1)
        self.assertIsNotNone(already)

    def test_is_not_downloaded(self):
        already = repo.get_nth_in_day(2016, 1, 1, 1)
        self.assertIsNone(already)

    def test_save_draw(self):
        lots = range(1, 21)
        jolly = 90
        year, month, day, nth = 2017, 7, 11, 1
        date = datetime(year, month, day)
        draw = Draw(year, month, day, nth, lots, jolly)
        repo.save_draw(draw)
        already = repo.get_nth_in_day(year, month, day, nth)
        self.assertIsNotNone(already)
        got = NdbDraw.get_by_id(NdbDraw.draw_id(
            year, month, day, nth), parent=NdbDraw.month_key(year, month))
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
        with open('test/fixtures/draw.json', 'r') as draw:
            self.draw_mock = draw.read()

    def tearDown(self):
        self.testbed.deactivate()

    @mock.patch('dieci_e_lotto.handlers.handle_fetch')
    def test_fetch(self, mock_handle_fetch):
        params = json.dumps({'year': 2016, 'month': 7, 'day': 1, 'nth': 1})
        mock_handle_fetch.return_value = None
        response = self.testapp.post(
            '/task/fetch', params)
        self.assertEqual(response.status_int, 200)
        mock_handle_fetch.assert_called_with(datetime(2016, 7, 1), 1)

    @mock.patch('dieci_e_lotto.repository.get_nth_in_day')
    @mock.patch('dieci_e_lotto.wish.fetch_draw')
    def test_handle_fetch(self, mock_fetch, already):
        mock_fetch.return_value = self.draw_mock
        already.return_value = None
        handle_fetch(datetime(2016, 7, 1), 1)
        already.assert_called_with(2016, 7, 1, 1)
        mock_fetch.assert_called_once()


class SynchronizeAllTest(unittest.TestCase):
    def setUp(self):
        synch_handler_url = '/schedule/download-all'
        self.synch_handler_url = synch_handler_url
        app = webapp2.WSGIApplication([
            (synch_handler_url, ScheduleDownloadAll)
        ])
        self.testapp = webtest.TestApp(app)
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        ndb.get_context().clear_cache()
        queue_yaml_dir = os.path.dirname(os.path.dirname(__file__))
        self.testbed.init_taskqueue_stub(root_path=queue_yaml_dir)

    def test_enqueue_task(self):
        response = self.testapp.get(self.synch_handler_url)
        self.assertEqual(response.status_int, 200)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url='/task/download-all', queue_names="default")
        self.assertEqual(len(tasks), 1)


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
        self.old_logging_level = logging.getLogger().level

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

    @mock.patch('dieci_e_lotto.repository.get_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_synchronize_all_unneeded_synch(self,
                                            last_draw, downloaded):
        config.MAX_DAYS_IN_THE_PAST = 0

        # STUB get_last_draw
        now = datetime.today()
        last_draw.return_value = (now.year, now.month, now.day, 4)

        # STUB downloaded_by_month
        downloaded.return_value = [
            Draw(now.year, now.month, now.day, i, [], 0) for i in range(1, 5)]

        self.assertIn(
            (now.year, now.month, now.day, 4, [], 0),
            downloaded.return_value)

        self.assertNotIn(
            (now.year, now.month, now.day, 5, [], 0),
            downloaded.return_value)

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")
        self.assertEqual(len(tasks), 0)

    @mock.patch('dieci_e_lotto.repository.get_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_synchronize_enquee_one(self,
                                    last_draw, downloaded):
        config.MAX_DAYS_IN_THE_PAST = 0

        # STUB get_last_draw
        now = datetime.today()
        last_draw.return_value = (now.year, now.month, now.day, 288)

        # STUB downloaded_by_month
        downloaded.return_value = [
            Draw(now.year,
                 now.month,
                 now.day, i, [], 0) for i in range(1, 288)]

        self.assertIn(
            (now.year, now.month, now.day, 287, [], 0),
            downloaded.return_value)

        self.assertNotIn(
            (now.year, now.month, now.day, 288, [], 0),
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

    @mock.patch('dieci_e_lotto.repository.get_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_synchronize_enquee_some(self,
                                     last_draw, downloaded):
        config.MAX_DAYS_IN_THE_PAST = 0

        # STUB get_last_draw
        now = datetime.today()
        last_draw.return_value = (now.year, now.month, now.day, 288)

        # STUB downloaded_by_month
        downloaded.return_value = [
            Draw(now.year,
                 now.month,
                 now.day, i, [], 0) for i in range(1, 189)]

        self.assertIn(
            (now.year, now.month, now.day, 188, [], 0),
            downloaded.return_value)

        self.assertNotIn(
            (now.year, now.month, now.day, 189, [], 0),
            downloaded.return_value)

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        self.assertEqual(len(tasks), config.FETCH_DRAW_BATCH_SIZE)

    @mock.patch('dieci_e_lotto.repository.get_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_synchronize_enquee_previous_day(self,
                                             last_draw, downloaded):
        config.MAX_DAYS_IN_THE_PAST = 1

        # STUB get_last_draw
        now = datetime.today()
        last_draw.return_value = (now.year, now.month, now.day, 1)

        # STUB downloaded_by_month
        downloaded.return_value = []

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        self.assertEqual(len(tasks), config.FETCH_DRAW_BATCH_SIZE)

    def tearDown(self):
        self.testbed.deactivate()


# last day of month and all already downloaded, expect first n of previous
# month  enqueued
    @mock.patch('dieci_e_lotto.repository.get_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_synchronize_on_last_draw_of_month(self,
                                               last_draw, downloaded):
        config.MAX_DAYS_IN_THE_PAST = 10
        config.FETCH_DRAW_BATCH_SIZE = 12

        # STUB get_last_draw
        now = datetime.today()
        first_week_day, total_days = monthrange(now.year, now.month)
        last_draw.return_value = (
            now.year, now.month, now.day, config.TOTAL_DAY_DRAWS)

        # STUB downloaded_by_month
        downloaded.return_value = [
            Draw(now.year,
                 now.month,
                 now.day, i, [], 0) for i in range(1, config.TOTAL_DAY_DRAWS + 1)]

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        self.assertEqual(len(tasks), config.FETCH_DRAW_BATCH_SIZE)

        xs = [json.loads(x.payload) for x in tasks]
        yesterday = now - timedelta(1)
        for x in xrange(config.TOTAL_DAY_DRAWS,
                        config.TOTAL_DAY_DRAWS - config.FETCH_DRAW_BATCH_SIZE + 1,
                        -1):
            expected = dict(year=yesterday.year,
                            month=yesterday.month, day=yesterday.day, nth=x)
            self.assertIn(expected, xs)

# the queue is full, expect just the first task enqueued
    @mock.patch('dieci_e_lotto.wish.queue_is_full')
    @mock.patch('dieci_e_lotto.repository.get_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_queue_full_enqueue_just_last(self,
                                          last_draw, downloaded, full):
        config.MAX_DAYS_IN_THE_PAST = 10
        config.FETCH_DRAW_BATCH_SIZE = 12

        # STUB get_last_draw
        now = datetime.today()
        first_week_day, total_days = monthrange(now.year, now.month)
        last_draw.return_value = (
            now.year, now.month, now.day, config.TOTAL_DAY_DRAWS)

        # STUB downloaded_by_month
        downloaded.return_value = [
            Draw(now.year,
                 now.month,
                 now.day, i, [], 0) for i in range(1, config.TOTAL_DAY_DRAWS)]

        # STUB queue_is_full
        full.return_value = True

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        self.assertEqual(len(tasks), 1)

        xs = [json.loads(x.payload) for x in tasks]
        self.assertEqual(xs[0], dict(
            year=now.year, month=now.month, day=now.day, nth=config.TOTAL_DAY_DRAWS))

    def tearDown(self):
        self.testbed.deactivate()

# the queue is full, the last extraction fetch has already enqueued,
# enqueue it again? (no big deal)
    @mock.patch('dieci_e_lotto.wish.queue_is_full')
    @mock.patch('dieci_e_lotto.repository.get_by_month')
    @mock.patch('dieci_e_lotto.wish.get_last_draw')
    def test_call_start_synch_twice(self,
                                    last_draw, downloaded, full):

        config.MAX_DAYS_IN_THE_PAST = 10
        config.FETCH_DRAW_BATCH_SIZE = 12

        # STUB get_last_draw
        now = datetime.today()
        first_week_day, total_days = monthrange(now.year, now.month)
        last_draw.return_value = (
            now.year, now.month, now.day, config.TOTAL_DAY_DRAWS)

        # STUB downloaded_by_month
        downloaded.return_value = [
            Draw(now.year,
                 now.month,
                 now.day, i, [], 0) for i in range(1, config.TOTAL_DAY_DRAWS)]

        # STUB queue_is_full
        full.return_value = True

        start_synchronization()

        last_draw.assert_called_once()
        downloaded.assert_called_with(now.year, now.month)

        q_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        self.assertEqual(len(tasks), 1)

        xs = [json.loads(x.payload) for x in tasks]
        self.assertEqual(xs[0], dict(
            year=now.year, month=now.month, day=now.day, nth=config.TOTAL_DAY_DRAWS))

        tasks_again = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        self.assertEqual(len(tasks), 1)

        start_synchronization()
        tasks_again = q_stub.get_filtered_tasks(
            url="/task/fetch-draw", queue_names="fetch-draws")

        self.assertEqual(len(tasks), 1)

        xs = [json.loads(x.payload) for x in tasks]
        self.assertEqual(xs[0], dict(
            year=now.year, month=now.month, day=now.day, nth=config.TOTAL_DAY_DRAWS))

    def tearDown(self):
        self.testbed.deactivate()
