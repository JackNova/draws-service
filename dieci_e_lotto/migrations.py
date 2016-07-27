from google.appengine.ext import deferred
from google.appengine.ext import ndb
import repository as repo
import logging

BATCH_SIZE = 100  # ideal batch size may vary based on entity size.


class Draw(ndb.Model):
    year = ndb.IntegerProperty()
    month = ndb.IntegerProperty()
    day = ndb.IntegerProperty()
    nth = ndb.IntegerProperty()
    lots = ndb.IntegerProperty(repeated=True)
    jolly = ndb.IntegerProperty()


def UpdateSchema(cursor=None, num_updated=0):
    query = Draw.query()
    to_put = []
    to_delete = []

    records, cursor, more = query.fetch_page(BATCH_SIZE, start_cursor=cursor)
    for record in records:
        updated = repo.NdbDraw.create(
            record.year, record.month, record.day,
            record.nth, record.lots, record.jolly)
        to_put.append(updated)
        to_delete.append(record)

    if to_put:
        ndb.put_multi(to_put)
        ndb.delete_multi([x.key for x in to_delete])
        num_updated += len(to_put)
        logging.info(
            'Put %d entities to Datastore for a total of %d',
            len(to_put), num_updated)
    if more:
        deferred.defer(
            UpdateSchema, cursor=cursor, num_updated=num_updated)
    else:
        logging.info(
            'UpdateSchema complete with %d updates!', num_updated)
