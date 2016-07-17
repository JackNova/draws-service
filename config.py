from google.appengine.api import app_identity
import yaml
import logging

try:
    id = app_identity.get_application_id()
except Exception, e:
    # .get_application_id() crashed when the module has no access
    # to the .env folder, happens when running tests inside
    # the virtualenv
    logging.info(e)
    id = 'unittest'

base_application_name = yaml.load(open('app.yaml', 'rb')).get('application')


TOTAL_DAY_DRAWS = 288
MAX_DAYS_IN_THE_PAST = 3

if id == 'develop':
    MAX_DAYS_IN_THE_PAST = 0
elif id == base_application_name + '_staging':
    MAX_DAYS_IN_THE_PAST = 3
else:
    MAX_DAYS_IN_THE_PAST = 3

logging.info("current app id is %s" % id)
