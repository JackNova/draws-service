import mock
import json
import unittest
from dieci_e_lotto import wish
from datetime import datetime
from datetime import timedelta
import config


class WishTestCase(unittest.TestCase):

    def setUp(self):
        with open('test/fixtures/calendario.json', 'r') as file:
            self.calendar_mock = file.read()
        with open('test/fixtures/draw.json', 'r') as draw:
            self.draw_mock = draw.read()

    def test_extract_last_draw(self):
        r = wish.extract_last_draw(self.calendar_mock)
        expected = (30, 219)
        self.assertEqual(r, expected)

        x = json.loads(self.calendar_mock)
        giorni = [y.get('giorno')
                  for y in x.get('giorniRaccolte')]
        self.assertTrue(len(giorni) > 0)
        self.assertEqual(max(giorni), expected[0])

    @mock.patch('dieci_e_lotto.wish.fetch_calendar')
    def test_get_last_draw(self, mock_get):
        mock_get.return_value = self.calendar_mock

        (anno, mese, giorno, progressivo) = wish.get_last_draw()

        mock_get.assert_called_once()
        oggi = datetime.now()
        self.assertEqual(anno, oggi.year)
        self.assertEqual(mese, oggi.month)
        self.assertEqual(giorno, 30)
        self.assertEqual(progressivo, 219)

    @mock.patch('dieci_e_lotto.wish.fetch_calendar')
    def test_total_day_draws_for_month(self, mock_get):
        mock_get.return_value = self.calendar_mock

        result = wish.total_day_draws_for_month(2016, 6)
        mock_get.assert_called_once()
        first = result.get('1')
        self.assertIsNotNone(first)
        self.assertEqual(first, 288)
        self.assertTrue(len(result) > 1)

    def test_previous_draw(self):
        draw = (2015, 8, 22, 45)
        self.assertEqual(wish.previous_draw(*draw), (2015, 8, 22, 44))

        draw = (2015, 8, 1, 1)
        self.assertEqual(wish.previous_draw(*draw), (2015, 7, 31, 288))

    def test_is_time_to_stop(self):
        past = datetime.today() - \
            timedelta(days=config.MAX_DAYS_IN_THE_PAST + 1)
        self.assertTrue(wish.is_time_to_stop(past.year, past.month, past.day))

        past = datetime.today() - \
            timedelta(days=config.MAX_DAYS_IN_THE_PAST)
        self.assertFalse(wish.is_time_to_stop(
            past.year, past.month, past.day))

        past = datetime.today() - \
            timedelta(days=config.MAX_DAYS_IN_THE_PAST - 1)
        self.assertFalse(wish.is_time_to_stop(
            past.year, past.month, past.day))

    def test_is_not_time_to_stop_the_same_day(self):
        config.MAX_DAYS_IN_THE_PAST = 1
        yesterday = datetime.today() - \
            timedelta(days=1)
        self.assertFalse(wish.is_time_to_stop(
            yesterday.year, yesterday.month, yesterday.day))

    @mock.patch('dieci_e_lotto.wish.fetch_draw')
    def test_get_draw_lots(self, mock_fetch):
        mock_fetch.return_value = self.draw_mock
        date = datetime(2016, 7, 11)
        nth = 122
        lots, jolly = wish.get_draw_lots(date, nth)
        mock_fetch.assert_called_once()
        self.assertEqual(lots, [12, 18, 21, 23, 26, 31, 33, 37,
                                40, 41, 43, 51, 52, 59, 61, 67,
                                68, 82, 84, 86])
        self.assertEqual(jolly, 86)
