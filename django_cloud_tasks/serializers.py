import json
from datetime import datetime

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.fields.files import FieldFile

DEFAULT_TIMEZONE = getattr(settings, 'TIMEZONE', 'UTC')


def assure_tz(dt, tz=DEFAULT_TIMEZONE):
    if not dt:
        return dt
    if not dt.tzinfo:
        dt = tz.localize(dt)
    return dt


class JSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if o is None:
            return None
        elif isinstance(o, datetime):
            value = assure_tz(o.astimezone())
            return value.isoformat()
        elif issubclass(o.__class__, FieldFile):
            return o.url if bool(o) else None
        else:
            return super().default(o)


def serialize(value):
    return json.dumps(value, cls=JSONEncoder)


def deserialize(value):
    return json.loads(value)
