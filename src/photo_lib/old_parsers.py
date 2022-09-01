import datetime


def parse_file(metadata: dict, dict_key: str):
    dt, offset = metadata[dict_key].split("+")
    base_date = datetime.datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")
    h, m = offset.split(":")
    delta = datetime.timedelta(hours=int(h), minutes=int(m))
    return base_date + delta


def parse_xmpdatetimeoriginal(metadata: dict, dict_key: str):
    datetime_string = metadata[dict_key].split("+")[0]
    if len(metadata[dict_key].split("+")) == 2:
        offset = metadata[dict_key].split("+")[1]
        h, m = offset.split(":")
        delta = datetime.timedelta(hours=int(h), minutes=int(m))
        return datetime.datetime.strptime(datetime_string, "%Y:%m:%d %H:%M") + delta
    else:
        return datetime.datetime.strptime(datetime_string, "%Y:%m:%d %H:%M")


# done
def parse_exif(metadata: dict, dict_key: str):
    datetime_string = metadata[dict_key].split("+")[0]
    if datetime_string == "0000:00:00 00:00:00":
        return None
    if len(metadata[dict_key].split("+")) == 2:
        offset = metadata[dict_key].split("+")[1]
        h, m = offset.split(":")
        delta = datetime.timedelta(hours=int(h), minutes=int(m))
        return datetime.datetime.strptime(datetime_string, "%Y:%m:%d %H:%M:%S") + delta
    else:
        return datetime.datetime.strptime(datetime_string, "%Y:%m:%d %H:%M:%S")


# def parse_subsec(metadata: dict, dict_key: str):
#     return datetime.datetime.strptime(metadata[dict_key], "%Y:%m:%d %H:%M:%S.%f")


def double_assembly(metadata: dict, date_key: str, time_key: str):
    datetime_string = f"{metadata[date_key]} {metadata[time_key].split('+')[0]}"
    if len(metadata[time_key].split('+')) == 2:
        offset = metadata[time_key].split("+")[1]
        h, m = offset.split(":")
        delta = datetime.timedelta(hours=int(h), minutes=int(m))
        return datetime.datetime.strptime(datetime_string, "%Y:%m:%d %H:%M:%S") + delta
    else:
        return datetime.datetime.strptime(datetime_string, "%Y:%m:%d %H:%M:%S")


# DONE
def parse_tplus(metadata: dict, dict_key: str):
    datetime_string = metadata[dict_key].split("+")[0]
    if len(metadata[dict_key].split("+")) == 2:
        offset = metadata[dict_key].split("+")[1]
        h, m = offset.split(":")
        delta = datetime.timedelta(hours=int(h), minutes=int(m))
        return datetime.datetime.strptime(datetime_string, "%Y-%m-%dT%H:%M:%S") + delta
    else:
        return datetime.datetime.strptime(datetime_string, "%Y-%m-%dT%H:%M:%S")


def decorator(func, date_key, time_key):
    def return_func(metadata: dict, key: str):
        date = metadata.get(date_key)
        time = metadata.get(time_key)

        if date is not None and time is not None:
            return func(metadata, date_key, time_key)

        else:
            return None

    return return_func


def dummy_func(metadata: dict, key: str):
    return None


# DONE
def parse_quicktime(metadata: dict, key: str):
    x = datetime.datetime.strptime(metadata[key], "%Y-%m-%d %H:%M:%S %z")
    p = datetime.datetime.strptime(x.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")
    return p + x.utcoffset()