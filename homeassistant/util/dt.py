"""Helper methods to handle the time in Home Assistant."""
from __future__ import annotations

import bisect
from contextlib import suppress
import datetime as dt
import re
import sys
from typing import Any, cast

import ciso8601

if sys.version_info[:2] >= (3, 9):
    import zoneinfo
else:
    from backports import zoneinfo

DATE_STR_FORMAT = "%Y-%m-%d"
UTC = dt.timezone.utc
DEFAULT_TIME_ZONE: dt.tzinfo = dt.timezone.utc

# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
# https://github.com/django/django/blob/master/LICENSE
DATETIME_RE = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})"
    r"[T ](?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
    r"(?::(?P<second>\d{1,2})(?:\.(?P<microsecond>\d{1,6})\d{0,6})?)?"
    r"(?P<tzinfo>Z|[+-]\d{2}(?::?\d{2})?)?$"
)


def set_default_time_zone(time_zone: dt.tzinfo) -> None:
    """Set a default time zone to be used when none is specified.

    Async friendly.
    """
    global DEFAULT_TIME_ZONE  # pylint: disable=global-statement

    assert isinstance(time_zone, dt.tzinfo)

    DEFAULT_TIME_ZONE = time_zone


def get_time_zone(time_zone_str: str) -> dt.tzinfo | None:
    """Get time zone from string. Return None if unable to determine.

    Async friendly.
    """
    try:
        # Cast can be removed when mypy is switched to Python 3.9.
        return cast(dt.tzinfo, zoneinfo.ZoneInfo(time_zone_str))
    except zoneinfo.ZoneInfoNotFoundError:
        return None


def utcnow() -> dt.datetime:
    """Get now in UTC time."""
    return dt.datetime.now(UTC)


def now(time_zone: dt.tzinfo | None = None) -> dt.datetime:
    """Get now in specified time zone."""
    return dt.datetime.now(time_zone or DEFAULT_TIME_ZONE)


def as_utc(dattim: dt.datetime) -> dt.datetime:
    """Return a datetime as UTC time.

    Assumes datetime without tzinfo to be in the DEFAULT_TIME_ZONE.
    """
    if dattim.tzinfo == UTC:
        return dattim
    if dattim.tzinfo is None:
        dattim = dattim.replace(tzinfo=DEFAULT_TIME_ZONE)

    return dattim.astimezone(UTC)


def as_timestamp(dt_value: dt.datetime | str) -> float:
    """Convert a date/time into a unix time (seconds since 1970)."""
    parsed_dt: dt.datetime | None
    if isinstance(dt_value, dt.datetime):
        parsed_dt = dt_value
    else:
        parsed_dt = parse_datetime(str(dt_value))
    if parsed_dt is None:
        raise ValueError("not a valid date/time.")
    return parsed_dt.timestamp()


def as_local(dattim: dt.datetime) -> dt.datetime:
    """Convert a UTC datetime object to local time zone."""
    if dattim.tzinfo == DEFAULT_TIME_ZONE:
        return dattim
    if dattim.tzinfo is None:
        dattim = dattim.replace(tzinfo=DEFAULT_TIME_ZONE)

    return dattim.astimezone(DEFAULT_TIME_ZONE)


def utc_from_timestamp(timestamp: float) -> dt.datetime:
    """Return a UTC time from a timestamp."""
    return dt.datetime.utcfromtimestamp(timestamp).replace(tzinfo=UTC)


def start_of_local_day(dt_or_d: dt.date | dt.datetime | None = None) -> dt.datetime:
    """Return local datetime object of start of day from date or datetime."""
    if dt_or_d is None:
        date: dt.date = now().date()
    elif isinstance(dt_or_d, dt.datetime):
        date = dt_or_d.date()
    else:
        date = dt_or_d

    return dt.datetime.combine(date, dt.time(), tzinfo=DEFAULT_TIME_ZONE)


# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
# https://github.com/django/django/blob/master/LICENSE
def parse_datetime(dt_str: str) -> dt.datetime | None:
    """Parse a string and return a datetime.datetime.

    This function supports time zone offsets. When the input contains one,
    the output uses a timezone with a fixed offset from UTC.
    Raises ValueError if the input is well formatted but not a valid datetime.
    Returns None if the input isn't well formatted.
    """
    with suppress(ValueError, IndexError):
        return ciso8601.parse_datetime(dt_str)

    if not (match := DATETIME_RE.match(dt_str)):
        return None
    kws: dict[str, Any] = match.groupdict()
    if kws["microsecond"]:
        kws["microsecond"] = kws["microsecond"].ljust(6, "0")
    tzinfo_str = kws.pop("tzinfo")

    tzinfo: dt.tzinfo | None = None
    if tzinfo_str == "Z":
        tzinfo = UTC
    elif tzinfo_str is not None:
        offset_mins = int(tzinfo_str[-2:]) if len(tzinfo_str) > 3 else 0
        offset_hours = int(tzinfo_str[1:3])
        offset = dt.timedelta(hours=offset_hours, minutes=offset_mins)
        if tzinfo_str[0] == "-":
            offset = -offset
        tzinfo = dt.timezone(offset)
    kws = {k: int(v) for k, v in kws.items() if v is not None}
    kws["tzinfo"] = tzinfo
    return dt.datetime(**kws)


def parse_date(dt_str: str) -> dt.date | None:
    """Convert a date string to a date object."""
    try:
        return dt.datetime.strptime(dt_str, DATE_STR_FORMAT).date()
    except ValueError:  # If dt_str did not match our format
        return None


def parse_time(time_str: str) -> dt.time | None:
    """Parse a time string (00:20:00) into Time object.

    Return None if invalid.
    """
    parts = str(time_str).split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        return dt.time(hour, minute, second)
    except ValueError:
        # ValueError if value cannot be converted to an int or not in range
        return None


def get_age(date: dt.datetime) -> str:
    """
    Take a datetime and return its "age" as a string.

    The age can be in second, minute, hour, day, month or year. Only the
    biggest unit is considered, e.g. if it's 2 days and 3 hours, "2 days" will
    be returned.
    Make sure date is not in the future, or else it won't work.
    """

    def formatn(number: int, unit: str) -> str:
        """Add "unit" if it's plural."""
        if number == 1:
            return f"1 {unit}"
        return f"{number:d} {unit}s"

    delta = (now() - date).total_seconds()
    rounded_delta = round(delta)

    units = ["second", "minute", "hour", "day", "month"]
    factors = [60, 60, 24, 30, 12]
    selected_unit = "year"

    for i, next_factor in enumerate(factors):
        if rounded_delta < next_factor:
            selected_unit = units[i]
            break
        delta /= next_factor
        rounded_delta = round(delta)

    return formatn(rounded_delta, selected_unit)


def parse_time_expression(parameter: Any, min_value: int, max_value: int) -> list[int]:
    """Parse the time expression part and return a list of times to match."""
    if parameter is None or parameter == "*":
        res = list(range(min_value, max_value + 1))
    elif isinstance(parameter, str):
        if parameter.startswith("/"):
            parameter = int(parameter[1:])
            res = [x for x in range(min_value, max_value + 1) if x % parameter == 0]
        else:
            res = [int(parameter)]

    elif not hasattr(parameter, "__iter__"):
        res = [int(parameter)]
    else:
        res = sorted(int(x) for x in parameter)

    for val in res:
        if val < min_value or val > max_value:
            raise ValueError(
                f"Time expression '{parameter}': parameter {val} out of range "
                f"({min_value} to {max_value})"
            )

    return res


def _dst_offset_diff(dattim: dt.datetime) -> dt.timedelta:
    """Return the offset when crossing the DST barrier."""
    delta = dt.timedelta(hours=24)
    return (dattim + delta).utcoffset() - (dattim - delta).utcoffset()  # type: ignore[operator]


def _lower_bound(arr: list[int], cmp: int) -> int | None:
    """Return the first value in arr greater or equal to cmp.

    Return None if no such value exists.
    """
    if (left := bisect.bisect_left(arr, cmp)) == len(arr):
        return None
    return arr[left]


def find_next_time_expression_time(
    now: dt.datetime,  # pylint: disable=redefined-outer-name
    seconds: list[int],
    minutes: list[int],
    hours: list[int],
) -> dt.datetime:
    """Find the next datetime from now for which the time expression matches.

    The algorithm looks at each time unit separately and tries to find the
    next one that matches for each. If any of them would roll over, all
    time units below that are reset to the first matching value.

    Timezones are also handled (the tzinfo of the now object is used),
    including daylight saving time.
    """
    if not seconds or not minutes or not hours:
        raise ValueError("Cannot find a next time: Time expression never matches!")

    while True:
        # Reset microseconds and fold; fold (for ambiguous DST times) will be handled later
        result = now.replace(microsecond=0, fold=0)

        # Match next second
        if (next_second := _lower_bound(seconds, result.second)) is None:
            # No second to match in this minute. Roll-over to next minute.
            next_second = seconds[0]
            result += dt.timedelta(minutes=1)

        result = result.replace(second=next_second)

        # Match next minute
        next_minute = _lower_bound(minutes, result.minute)
        if next_minute != result.minute:
            # We're in the next minute. Seconds needs to be reset.
            result = result.replace(second=seconds[0])

        if next_minute is None:
            # No minute to match in this hour. Roll-over to next hour.
            next_minute = minutes[0]
            result += dt.timedelta(hours=1)

        result = result.replace(minute=next_minute)

        # Match next hour
        next_hour = _lower_bound(hours, result.hour)
        if next_hour != result.hour:
            # We're in the next hour. Seconds+minutes needs to be reset.
            result = result.replace(second=seconds[0], minute=minutes[0])

        if next_hour is None:
            # No minute to match in this day. Roll-over to next day.
            next_hour = hours[0]
            result += dt.timedelta(days=1)

        result = result.replace(hour=next_hour)

        if result.tzinfo in (None, UTC):
            # Using UTC, no DST checking needed
            return result

        if not _datetime_exists(result):
            # When entering DST and clocks are turned forward.
            # There are wall clock times that don't "exist" (an hour is skipped).

            # -> trigger on the next time that 1. matches the pattern and 2. does exist
            # for example:
            #   on 2021.03.28 02:00:00 in CET timezone clocks are turned forward an hour
            #   with pattern "02:30", don't run on 28 mar (such a wall time does not exist on this day)
            #   instead run at 02:30 the next day

            # We solve this edge case by just iterating one second until the result exists
            # (max. 3600 operations, which should be fine for an edge case that happens once a year)
            now += dt.timedelta(seconds=1)
            continue

        now_is_ambiguous = _datetime_ambiguous(now)
        result_is_ambiguous = _datetime_ambiguous(result)

        # When leaving DST and clocks are turned backward.
        # Then there are wall clock times that are ambiguous i.e. exist with DST and without DST
        # The logic above does not take into account if a given pattern matches _twice_
        # in a day.
        # Example: on 2021.10.31 02:00:00 in CET timezone clocks are turned backward an hour

        if now_is_ambiguous and result_is_ambiguous:
            # `now` and `result` are both ambiguous, so the next match happens
            # _within_ the current fold.

            # Examples:
            #  1. 2021.10.31 02:00:00+02:00 with pattern 02:30 -> 2021.10.31 02:30:00+02:00
            #  2. 2021.10.31 02:00:00+01:00 with pattern 02:30 -> 2021.10.31 02:30:00+01:00
            return result.replace(fold=now.fold)

        if now_is_ambiguous and now.fold == 0 and not result_is_ambiguous:
            # `now` is in the first fold, but result is not ambiguous (meaning it no longer matches
            # within the fold).
            # -> Check if result matches in the next fold. If so, emit that match

            # Turn back the time by the DST offset, effectively run the algorithm on the first fold
            # If it matches on the first fold, that means it will also match on the second one.

            # Example: 2021.10.31 02:45:00+02:00 with pattern 02:30 -> 2021.10.31 02:30:00+01:00

            check_result = find_next_time_expression_time(
                now + _dst_offset_diff(now), seconds, minutes, hours
            )
            if _datetime_ambiguous(check_result):
                return check_result.replace(fold=1)

        return result


def _datetime_exists(dattim: dt.datetime) -> bool:
    """Check if a datetime exists."""
    assert dattim.tzinfo is not None
    original_tzinfo = dattim.tzinfo
    # Check if we can round trip to UTC
    return dattim == dattim.astimezone(UTC).astimezone(original_tzinfo)


def _datetime_ambiguous(dattim: dt.datetime) -> bool:
    """Check whether a datetime is ambiguous."""
    assert dattim.tzinfo is not None
    opposite_fold = dattim.replace(fold=not dattim.fold)
    return _datetime_exists(dattim) and dattim.utcoffset() != opposite_fold.utcoffset()
