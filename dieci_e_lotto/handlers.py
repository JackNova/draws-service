# -*- coding: utf-8 -*-

import json
import wish
import webapp2
from datetime import datetime


class FetchDraw(webapp2.RequestHandler):
    def post(self):
        payload = json.loads(self.request.body)
        date = datetime(payload.get('year'), payload.get(
            'month'), payload.get('day'))
        nth = payload.get('nth')

        if wish.is_downloaded_already(date.year, date.month, date.day, nth):
            return

        numbers, jolly = wish.get_draw_lots(date, nth)
        wish.save_draw(date, nth, numbers, jolly)


class DownloadAll(webapp2.RequestHandler):
    def post(self):
        start_synchronization()


def start_synchronization():
    year, month, day, nth = wish.get_last_draw()
    downloaded_already = wish.get_downloaded_by_month(year, month)
    memo_month = month
    memo_day = day
    while True:
        if memo_day is not day and wish.is_time_to_stop(year, month, day):
            break
        memo_day = day

        if (year, month, day, nth) not in downloaded_already:
            wish.schedule_fetch_draw(year, month, day, nth)
        year, month, day, nth = wish.previous_draw(
            year, month, day, nth)
        if memo_month is not month:
            downloaded_already = wish.get_downloaded_by_month(year, month)
            memo_month = month
