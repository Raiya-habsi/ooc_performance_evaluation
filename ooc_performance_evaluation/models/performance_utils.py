from datetime import timedelta


PARAM_PREFIX = "ooc_performance_evaluation."


def get_param(env, key, default=None, cast=str):
    value = env["ir.config_parameter"].sudo().get_param(f"{PARAM_PREFIX}{key}")
    if value in (None, ""):
        return default
    if cast is bool:
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def add_working_days(start_date, working_days):
    if not start_date:
        return start_date
    current = start_date
    days_added = 0
    while days_added < working_days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days_added += 1
    return current


def working_days_between(start_date, end_date):
    if not start_date or not end_date or end_date < start_date:
        return 0
    current = start_date
    days = 0
    while current <= end_date:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    return days
