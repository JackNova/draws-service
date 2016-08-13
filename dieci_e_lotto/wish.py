import json
import config
import urllib2
import logging
from datetime import datetime
from datetime import timedelta
from google.appengine.api import taskqueue

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
    # https://cloud.google.com/appengine/docs/python/taskqueue/push/creating-tasks#naming_a_task
    # A task name must be unique within a queue. If you try to add another
    # task with the same name to a the queue, the operation will fail. After a
    # task is removed from a queue you can't insert a task with the same name
    # into the queue until 10 days have passed.

    # unique_name = "%s-%02d-%02d-%02d" % (year, month, day, nth)
    task = taskqueue.add(
        url='/task/fetch-draw',
        queue_name="fetch-draws",
        # name=unique_name,
        payload=json.dumps({
            'year': year,
            'month': month,
            'day': day,
            'nth': nth
        }))
    return task

    # logging.info(
    #     'Task {} enqueued, ETA {}.'.format(task.name, task.eta))


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


def queue_is_full():
    stats = taskqueue.QueueStatistics.fetch("fetch-draws")
    return stats.tasks > config.FETCH_DRAW_BATCH_SIZE


def last_extraction_of_previous_month(year, month):
    return previous_draw(year, month, 1, 1)
