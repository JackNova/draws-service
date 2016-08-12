# -*- coding: utf-8 -*-

import os
import json
import wish
import config
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
                         in repo.get_by_day(year, month, day)])
        draws = [n in situation for n in range(1, config.TOTAL_DAY_DRAWS + 1)]

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


class MonthMonitoring(webapp2.RequestHandler):

    def get(self, year, month):
        year = int(year)
        month = int(month)

        db = repo.get_by_month(year, month)
        situation = dict(groupby(db, lambda x: x.day))
        first_week_day, total_days = monthrange(year, month)
        days = [len(list(situation.get(day) or [])) ==
                config.TOTAL_DAY_DRAWS for day in range(1, total_days + 1)]

        template_values = {
            'year': year,
            'month': month,
            'days': days
        }

        template = JINJA_ENVIRONMENT.get_template(
            'monitor-month.jinja')
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
    tasks_enqueued = 0
    year, month, day, nth = wish.get_last_draw()
    logging.info('Last draw is the number %s of %s/%s/%s' %
                 (nth, day, month, year))
    downloaded_already = set([(x.year, x.month, x.day, x.nth)
                              for x in repo.get_by_month(year, month)])
    logging.info("%s draws have been downloaded already for the month %s/%s" %
                 (len(downloaded_already), month, year))
    memo_month = month
    memo_day = day
    while True:
        if tasks_enqueued >= config.FETCH_DRAW_BATCH_SIZE:
            logging.info(
                "Queue is full, (already enqueued %s in this batch) ending process early." % tasks_enqueued)
            break
        if memo_day is not day and wish.queue_is_full():
            logging.info(
                "Queue is full, (for day %s) ending process early." % day)
            break
        if memo_day is not day and wish.is_time_to_stop(year, month, day):
            logging.info('Process complete. No more task to schedule')
            break
        memo_day = day

        first_week_day, month_total_days = monthrange(year, month)
        is_month_download_complete = (
            len(downloaded_already) == config.TOTAL_DAY_DRAWS * month_total_days)
        if is_month_download_complete:
            logging.info(
                "There are no additional draws in this month to download")
            year, month, day, nth = wish.last_extraction_of_previous_month(
                year, month)
            continue
        else:
            if (year, month, day, nth) not in downloaded_already:
                wish.schedule_fetch_draw(year, month, day, nth)
                tasks_enqueued += 1
                logging.info("schedule fetch draw number %s of %s/%s/%s" %
                             (nth, day, month, year))
            year, month, day, nth = wish.previous_draw(
                year, month, day, nth)

        if memo_month is not month:
            logging.info("month switch from %s to %s" % (memo_month, month))
            downloaded_already = set([(x.year, x.month, x.day, x.nth)
                                      for x in repo.get_by_month(year, month)])
            memo_month = month
