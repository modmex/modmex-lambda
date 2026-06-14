from modmex_lambda.stream.filters.event_type import filter_on_event_type
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.filters.content import filter_on_content


def on_event_type(rule):
    def wrapper(uow):
        return filter_on_event_type(rule, uow)
    return faulty(wrapper)


def on_content(rule):
    def wrapper(uow):
        return filter_on_content(rule, uow)
    return faulty(wrapper)
