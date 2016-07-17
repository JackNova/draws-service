import json
import urllib2
import logging
from datetime import datetime
from datetime import timedelta
from google.appengine.ext import ndb
from google.appengine.api import taskqueue
import config

calendar_url = "http://www.lottomaticaitalia.it/10elotto/estrazioni-e-vincite/10-e-lotto-calendario-estrazioni-ogni-5.json"
draw_url = "http://www.lottomaticaitalia.it/10elotto/estrazioni-e-vincite/10-e-lotto-estrazioni-ogni-5.json"


def fetch_draw(date, nth):
    request_date = date.strftime('%Y%m%d')
    payload = {'data': request_date,
               'progressivoGiornaliero': str(nth)}
    req = urllib2.Request(draw_url, json.dumps(payload), {
                          'Content-Type': 'application/json'})
    r = urllib2.urlopen(req)
    return r.read()


def get_draw_lots(date, nth):
    result = fetch_draw(date, nth)
    data = json.loads(result)
    lots = [int(x) for x in data.get('numeriEstratti')]
    jolly = int(data.get('numeroSpeciale'))
    return lots, jolly


def extract_last_draw(json_calendar):
    days = json.loads(json_calendar).get('giorniRaccolte')
    last = max(days, key=lambda g: g.get('giorno'))
    return (last.get('giorno'), last.get('progressivoGiornaliero'))


def fetch_calendar(anno, mese):
    url = calendar_url
    payload = json.dumps({
        'anno': anno,
        'mese': "%02d" % mese
    })
    headers = {'Content-Type': 'application/json'}
    req = urllib2.Request(url, payload, headers)
    r = urllib2.urlopen(req)
    if r.getcode() != 200:
        logging.error("fetch calendar for year: %s, month: %s returned %s" % (
            anno, mese, r.getcode()))
    json_calendar = r.read()
    logging.info("calendar got:")
    logging.info(json_calendar)
    return json_calendar


def total_day_draws_for_month(year, month):
    json_data = fetch_calendar(year, month)
    return dict([(
        str(x.get('giorno')),
        x.get('progressivoGiornaliero')
    ) for x in json.loads(json_data).get('giorniRaccolte')])


def get_last_draw():
    year = datetime.now().year
    month = datetime.now().month
    json_calendar = fetch_calendar(year, month)
    giorno, progressivo = extract_last_draw(json_calendar)

    return (year, month, giorno, progressivo)


def schedule_fetch_draw(year, month, day, nth):
    task = taskqueue.add(
        url='/task/fetch-draw',
        queue_name="fetch-draws",
        payload=json.dumps({
            'year': year,
            'month': month,
            'day': day,
            'nth': nth
        }))
    return task

    # logging.info(
    #     'Task {} enqueued, ETA {}.'.format(task.name, task.eta))


class Draw(ndb.Model):
    year = ndb.IntegerProperty()
    month = ndb.IntegerProperty()
    day = ndb.IntegerProperty()
    nth = ndb.IntegerProperty()
    lots = ndb.IntegerProperty(repeated=True)
    jolly = ndb.IntegerProperty()

    @classmethod
    def month_key(cls, year, month):
        return ndb.Key('Month', "%s-%s" % (year, month))

    @classmethod
    def draw_id(cls, year, month, day, nth):
        return "%s-%s-%s-%s" % (year, month, day, nth)

    @classmethod
    def create(cls, year, month, day, nth, lots, jolly):
        return Draw(id=cls.draw_id(year, month, day, nth),
                    parent=cls.month_key(year, month),
                    year=year, month=month,
                    day=day, nth=nth,
                    lots=lots, jolly=jolly)

    @classmethod
    def by_month(cls, year, month):
        xs = Draw.query(ancestor=cls.month_key(year, month)).fetch()
        return set((x.year, x.month, x.day, x.nth) for x in xs)


def get_downloaded_by_month(year, month):
    return Draw.by_month(year, month)


def get_downloaded_by(year, month, day=None):
    if day is None:
        return get_downloaded_by_month(year, month)
    else:
        xs = Draw.query( Draw.day==day, ancestor=Draw.month_key(year, month) )
        return set((x.year, x.month, x.day, x.nth) for x in xs.fetch())


def is_downloaded_already(year, month, day, nth):
    target = Draw.get_by_id(parent=Draw.month_key(year, month),
                            id=Draw.draw_id(year, month, day, nth))
    return target is not None


def save_draw(date, nth, lots, jolly):
    record = Draw.create(date.year, date.month, date.day, nth, lots, jolly)
    record.put()


def previous_draw(year, month, day, nth):
    if nth > 1:
        return (year, month, day, nth - 1)
    else:
        date = datetime(year, month, day)
        previous_day = date - timedelta(days=1)
        return (previous_day.year, previous_day.month,
                previous_day.day, config.TOTAL_DAY_DRAWS)


def is_time_to_stop(year, month, day):
    stop_date = datetime.today() - \
        timedelta(days=config.MAX_DAYS_IN_THE_PAST + 1)

    return datetime(year, month, day) < stop_date
