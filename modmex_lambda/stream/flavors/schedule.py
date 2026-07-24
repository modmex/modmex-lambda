import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from reactivex import Observable, operators as ops

from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.publisher import PublisherOptions
from modmex_lambda.stream.utils.contracts import BaseRule, Event, Uow
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.filters import on_content, on_event_type
from modmex_lambda.stream.utils.operators import try_filter, try_map
from modmex_lambda.stream.utils.print import print_end, print_start
from modmex_lambda.stream.utils.tags import adorn_standard_tags


class ScheduleRule(BaseRule, total=False):
    """Declares a one-time future delivery of a standard domain event."""

    schedule_at: Callable[[Uow], datetime]
    delay_minutes: int | Callable[[Uow], int]
    schedule_name: str | Callable[[Uow], str]
    to_event: Callable[[Uow, "Schedule", Event], Event]
    bus_arn: str | Callable[[Uow], str]
    role_arn: str | Callable[[Uow], str]
    group_name: str | Callable[[Uow], str]
    source: str | Callable[[Uow], str]
    client_token: str | Callable[[Uow], str]


class Schedule(BaseFlavor):
    """Schedules a standard domain event for one future point in time."""

    def __init__(
        self,
        rule: ScheduleRule,
        *,
        logger: Optional[Any] = None,
        connector: Optional[IEventBridgeConnector] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
        publisher_options: Optional[PublisherOptions] = None,
    ) -> None:
        super().__init__(
            logger=logger,
            connector=connector,
            dependency_resolver=dependency_resolver,
            publisher_options=publisher_options,
        )
        self.rule = rule

    @property
    def id(self):
        return self.rule["id"]

    def __call__(self, source: Observable):
        return source.pipe(
            try_filter(on_event_type(self.rule)),
            ops.do_action(print_start(self.logger)),
            try_filter(on_content(self.rule)),
            try_map(faulty(self._to_schedule_request)),
            self.scheduler_ops,
            ops.do_action(print_end(self.logger)),
        )

    def _to_schedule_request(self, uow: Uow) -> Uow:
        schedule_at = self._resolve_schedule_at(uow)
        if schedule_at.tzinfo is None:
            raise ValueError("schedule_at must return a timezone-aware datetime.")

        scheduled_event = self._to_event(uow, schedule_at)
        bus_arn = self._value(
            "bus_arn", uow, os.getenv("BUS_ARN")
        )
        role_arn = self._value("role_arn", uow, os.getenv("SCHEDULER_ROLE_ARN"))
        if not bus_arn:
            raise ValueError("bus_arn or BUS_ARN is required.")
        if not role_arn:
            raise ValueError("role_arn or SCHEDULER_ROLE_ARN is required.")
        return {
            **uow,
            "scheduled_event": scheduled_event,
            "schedule_request": {
                "Name": self._value("schedule_name", uow),
                "GroupName": self._value("group_name", uow, "default"),
                "ScheduleExpression": self._schedule_expression(schedule_at),
                "FlexibleTimeWindow": {"Mode": "OFF"},
                "ActionAfterCompletion": "DELETE",
                "ClientToken": self._value("client_token", uow, scheduled_event["id"]),
                "Target": {
                    "Arn": self._value(
                        "bus_arn", uow, bus_arn
                    ),
                    "RoleArn": self._value(
                        "role_arn", uow, role_arn
                    ),
                    "EventBridgeParameters": {
                        "Source": self._value(
                            "source", uow, os.getenv("BUS_SRC", "custom")
                        ),
                        "DetailType": scheduled_event["type"],
                    },
                    "Input": json.dumps(scheduled_event),
                },
            },
        }

    def _to_event(self, uow: Uow, schedule_at: datetime) -> Event:
        template: Event = {
            "id": self._value("client_token", uow, self._value("schedule_name", uow)),
            "timestamp": int(schedule_at.timestamp() * 1000),
            "partition_key": uow["event"].get("partition_key"),
            "triggers": [
                {
                    "id": uow["event"]["id"],
                    "type": uow["event"]["type"],
                    "timestamp": uow["event"].get("timestamp"),
                }
            ],
        }
        event = self.rule["to_event"](uow, self, template)
        return adorn_standard_tags("scheduled_event")({
            **uow,
            "scheduled_event": event,
        })["scheduled_event"]

    def _resolve_schedule_at(self, uow: Uow) -> datetime:
        has_schedule_at = "schedule_at" in self.rule
        has_delay_minutes = "delay_minutes" in self.rule
        if has_schedule_at == has_delay_minutes:
            raise ValueError(
                "Schedule requires exactly one of schedule_at or delay_minutes."
            )

        if has_schedule_at:
            return self.rule["schedule_at"](uow)

        delay_minutes = self._value("delay_minutes", uow)
        if isinstance(delay_minutes, bool) or not isinstance(delay_minutes, int):
            raise ValueError("delay_minutes must resolve to a non-negative integer.")
        if delay_minutes < 0:
            raise ValueError("delay_minutes must resolve to a non-negative integer.")

        timestamp = uow["event"].get("timestamp")
        if timestamp is None:
            raise ValueError("delay_minutes requires event.timestamp.")
        return datetime.fromtimestamp(
            timestamp / 1000,
            tz=timezone.utc,
        ) + timedelta(minutes=delay_minutes)

    def _value(self, key: str, uow: Uow, default=None):
        value = self.rule.get(key, default)
        return value(uow) if callable(value) else value

    @staticmethod
    def _schedule_expression(value: datetime) -> str:
        return "at({})".format(
            value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        )
