# -*- coding: utf-8 -*-

import os
import json
import wish
import jinja2
import logging
import webapp2
from entities import Draw
import repository as repo
from itertools import groupby
from datetime import datetime
from calendar import monthrange

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class DrawsMonitoring(webapp2.RequestHandler):

    def get(self, year, month, day):
        year = int(year)
        month = int(month)
        day = int(day)

        situation = set([x.nth for x
                         in repo.get_by_day(y, m, d)])
        draws = [n in situation for n in range(1, 289)]

        template_values = {
            'year': year,
            'month': month,
            'day': day,
            'total': len(situation),
            'xs': draws
        }

        template = JINJA_ENVIRONMENT.get_template(
            'monitoring.jinja')
        self.response.write(template.render(template_values))


class FetchDraw(webapp2.RequestHandler):
    def post(self):
        payload = json.loads(self.request.body)
        date = datetime(payload.get('year'), payload.get(
            'month'), payload.get('day'))
        nth = payload.get('nth')
        handle_fetch(date, nth)


class DownloadAll(webapp2.RequestHandler):
    def post(self):
        start_synchronization()


def handle_fetch(date, nth):
    already = repo.get_nth_in_day(date.year, date.month, date.day, nth)
    if already is not None:
        return

    lots, jolly = wish.get_draw_lots(date, nth)
    draw = Draw(date.year, date.month, date.day, nth, lots, jolly)
    repo.save_draw(draw)


def start_synchronization():
    year, month, day, nth = wish.get_last_draw()
    downloaded_already = set([(x.year, x.month, x.day, x.nth)
                              for x in repo.get_by_month(year, month)])
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
            downloaded_already = set([(x.year, x.month, x.day, x.nth)
                                      for x in repo.get_by_month(year, month)])
            memo_month = month
