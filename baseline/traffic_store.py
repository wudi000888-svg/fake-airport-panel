import store_facade
from repositories.sqlite_traffic import SQLiteTrafficRepository


def repo():
    return SQLiteTrafficRepository(store_facade.ensure_sqlite())


def add_sample(sample):
    return repo().add_sample(sample)


def series(start, end, granularity="hour"):
    return repo().series(start, end, granularity)


def top_users(start, end, limit=12):
    return repo().top_users(start, end, limit)


def by_node(start, end):
    return repo().by_node(start, end)


def totals(start=None, end=None):
    return repo().totals(start, end)


def delete_before(cutoff):
    return repo().delete_before(cutoff)
