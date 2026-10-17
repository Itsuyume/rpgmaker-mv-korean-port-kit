"""Select display commands with ordered context from the same event page."""
from bisect import bisect_left
from collections.abc import Iterator

from .choices import ChoiceLinks, choices
from .event_lists import event_lists
from .json_store import array_value, int_value, string_value
from .model import Candidate, Context, EventList, JsonValue, Location
from .rules import DISPLAY_COMMAND_FIELDS


def text_at(event: EventList, index: int) -> tuple[str, ...]:
    command = event.commands[index]
    code = int_value(command["code"])
    params = array_value(command["parameters"])
    if code in DISPLAY_COMMAND_FIELDS:
        return (string_value(params[DISPLAY_COMMAND_FIELDS[code][0]]),)
    if code == 102:
        return tuple(string_value(t) for t in array_value(params[0]))
    return ()


def context(event: EventList, trace: dict[int, tuple[str, ...]], index: int,
            face: str | None, options: tuple[str, ...] = ()) -> Context:
    indices = list(trace)
    position = bisect_left(indices, index)
    nearby = tuple((i, trace[i]) for i in indices[max(0, position - 2):position + 3])
    return Context(event.path, event.owner_name, index, face, choices=options, nearby=nearby)


def event_candidates(event: EventList, links: ChoiceLinks) -> Iterator[Candidate]:
    trace = {i: text_at(event, i) for i in range(len(event.commands)) if text_at(event, i)}
    face: str | None = None
    for index, command in enumerate(event.commands):
        code = int_value(command["code"])
        params = array_value(command["parameters"])
        if code == 101:
            face = string_value(params[0])
        elif code == 105:
            face = None
        elif code == 102:
            options = tuple(string_value(t) for t in array_value(params[0]))
            for option, source in enumerate(options):
                if source.strip():
                    yield Candidate(source, "choice", links.locations[index, option], context(event, trace, index, face, options))
        elif code in DISPLAY_COMMAND_FIELDS:
            parameter, kind = DISPLAY_COMMAND_FIELDS[code]
            source = string_value(params[parameter])
            if source.strip():
                location = Location(event.file, event.path + (index, "parameters", parameter), source)
                speaker = face if code == 401 else None
                yield Candidate(source, kind, (location,), context(event, trace, index, speaker))


def event_fields(file: str, data: JsonValue) -> tuple[list[Candidate], list[Location]]:
    candidates: list[Candidate] = []
    mismatches: list[Location] = []
    for event in event_lists(file, data):
        links = choices(event)
        candidates.extend(event_candidates(event, links))
        mismatches.extend(links.mismatches)
    return candidates, mismatches
