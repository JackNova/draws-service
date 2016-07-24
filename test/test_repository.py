import unittest
from dieci_e_lotto.entities import Draw
from datetime import datetime
from google.appengine.ext import ndb
from google.appengine.ext import testbed
from google.appengine.api import memcache
from dieci_e_lotto import repository as repo


class RepositoryTestCase(unittest.TestCase):
    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        ndb.get_context().clear_cache()

        self.today = datetime.now()
        self.lots = list(range(1, 21))
        self.jolly = 34
        self.draws = [Draw(self.today.year, self.today.month, self.today.day,
                           i, self.lots, self.jolly) for i in range(1, 11)]
        for d in self.draws:
            repo.save_draw(d)

    def tearDown(self):
        self.testbed.deactivate()

    def test_create_draws(self):
        queried = repo.get_by_day(
            self.today.year, self.today.month, self.today.day)
        self.assertEqual(len(queried), len(self.draws))
        self.assertGreater(len(queried), 0)
        self.assertEqual(len(queried), 10)

    def test_get_by_day(self):
        draws = repo.get_by_day(
            self.today.year, self.today.month, self.today.day)
        self.assertIsNotNone(draws)
        draw = draws[0]
        self.assertEqual(len(draw.lots), 20)

        xs = [sorted_key(x) for x in draws]
        xs_sorted = sorted(xs)
        self.assertEqual(xs, xs_sorted)

        is_sorted = all(sorted_key(draws[i]) <= sorted_key(
            draws[i + 1]) for i in xrange(len(draws) - 1))
        self.assertTrue(is_sorted)

    def test_get_by_month(self):
        draws = repo.get_by_month(self.today.year, self.today.month)
        self.assertIsNotNone(draws)
        first = draws[0]
        self.assertEqual(len(first.lots), 20)

        xs = [sorted_key(x) for x in draws]
        xs_sorted = sorted(xs)
        self.assertEqual(xs, xs_sorted)

        is_sorted = all(sorted_key(draws[i]) <= sorted_key(
            draws[i + 1]) for i in xrange(len(draws) - 1))
        self.assertTrue(is_sorted)

    def test_nth_in_day(self):
        draw = repo.get_nth_in_day(
            self.today.year, self.today.month, self.today.day, 1)
        self.assertEqual(draw, self.draws[0])


def sorted_key(draw):
    return "%s-%02d-%02d-%02d" % (draw.year, draw.month, draw.day, draw.nth)
