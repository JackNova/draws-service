from google.appengine.ext import ndb
from entities import Draw

# PUBLIC API


def get_by_month(year, month):
    xs = NdbDraw.query_by_month(year, month)
    return [Draw(x.year, x.month, x.day, x.nth, x.lots, x.jolly) for x in xs]


def get_by_day(year, month, day):
    xs = NdbDraw.query_by_day(year, month, day)
    return [Draw(x.year, x.month, x.day, x.nth, x.lots, x.jolly) for x in xs]


def get_nth_in_day(year, month, day, nth):
    x = NdbDraw.query_nth_in_day(year, month, day, nth)
    if x is not None:
        return Draw(x.year, x.month, x.day, x.nth, x.lots, x.jolly)


def save_draw(draw):
    record = NdbDraw.create(draw.year, draw.month,
                            draw.day, draw.nth, draw.lots, draw.jolly)
    record.put()

# INFRASTRUCTURE SPECIFIC IMPLEMENTATION


class NdbDraw(ndb.Model):
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
        return NdbDraw(id=cls.draw_id(year, month, day, nth),
                       parent=cls.month_key(year, month),
                       year=year, month=month,
                       day=day, nth=nth,
                       lots=lots, jolly=jolly)

    @classmethod
    def query_by_month(cls, year, month):
        q = cls.query(cls.month == month,
                      ancestor=cls.month_key(year, month)).order(
            cls.year, cls.month, cls.day, cls.nth)
        return q

    @classmethod
    def query_by_day(cls, year, month, day):
        q = cls.query(cls.day == day, ancestor=cls.month_key(
            year, month)).order(cls.year, cls.month, cls.day, cls.nth)
        return q

    @classmethod
    def query_nth_in_day(cls, year, month, day, nth):
        q = cls.get_by_id(parent=cls.month_key(year, month),
                          id=cls.draw_id(year, month, day, nth))
        return q
