"""Link each 402 label to its owning 102 option by indent and option index."""
from dataclasses import dataclass

from .json_store import array_value, int_value, string_value
from .model import EventList, Location


@dataclass(frozen=True)
class ChoiceLinks:
    locations: dict[tuple[int, int], tuple[Location, ...]]
    mismatches: tuple[Location, ...]


def choices(event: EventList) -> ChoiceLinks:
    active: dict[int, int] = {}
    found: dict[tuple[int, int], list[Location]] = {}
    mismatches: list[Location] = []
    for index, command in enumerate(event.commands):
        code, indent = int_value(command["code"]), int_value(command["indent"])
        params = array_value(command["parameters"])
        if code == 102:
            active[indent] = index
            for option, raw in enumerate(array_value(params[0])):
                text = string_value(raw)
                path = event.path + (index, "parameters", 0, option)
                found[index, option] = [Location(event.file, path, text)]
        elif code == 402:
            if indent not in active:
                raise ValueError("A 402 branch has no owning 102: " + event.file + str(event.path + (index,)))
            owner, option = active[indent], int_value(params[0])
            key = owner, option
            if key not in found:
                raise ValueError("A 402 branch index is outside its 102 choices.")
            text = string_value(params[1])
            alias = Location(event.file, event.path + (index, "parameters", 1), text, "choice_alias")
            found[key].append(alias)
            if text != found[key][0].source:
                mismatches.append(alias)
        elif code == 404:
            if indent not in active:
                raise ValueError("A 404 terminator has no owning 102.")
            del active[indent]
    return ChoiceLinks({key: tuple(value) for key, value in found.items()}, tuple(mismatches))
