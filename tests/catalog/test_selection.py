"""Synthetic MV selection tests: verify outputs, aliases and excluded values."""
import unittest

from pq_catalog.core_fields import core_fields
from pq_catalog.event_fields import event_fields
from pq_catalog.tokens import assert_preserved, extract_tokens, has_language


def command(code, parameters, indent=0):
    return {"code": code, "indent": indent, "parameters": parameters}


def common(commands):
    return [None, {"id": 1, "name": "InternalEvent", "list": commands}]


class SelectionTests(unittest.TestCase):
    def test_empty_database_and_null_event_are_not_text(self):
        self.assertEqual(list(core_fields("data/Actors.json", [None])), [])
        self.assertEqual(event_fields("data/CommonEvents.json", [None]), ([], []))

    def test_aliases_nested_choices_and_cancel_keep_indices(self):
        source = common([command(102, [["Left", "Right"], 2, 0, 1, 0]),
            command(402, [0, "Left"]), command(102, [["Nested"], -1, 0, 1, 0], 1),
            command(402, [0, "Nested"], 1), command(404, [], 1),
            command(402, [1, "Right"]), command(403, []), command(404, [])])
        rows, mismatches = event_fields("data/CommonEvents.json", source)
        self.assertEqual(mismatches, [])
        self.assertEqual([row.source for row in rows], ["Left", "Right", "Nested"])
        self.assertEqual([len(row.locations) for row in rows], [2, 2, 2])
        self.assertEqual(rows[1].locations[1].path[-3:], (5, "parameters", 1))
        self.assertEqual(source[1]["list"][6]["code"], 403)

    def test_orphan_branches_and_invalid_indices_fail(self):
        for commands in ([command(402, [0, "A"])], [command(404, [])],
                         [command(102, [["A"], -1]), command(402, [1, "A"]) ]):
            with self.assertRaises(ValueError):
                event_fields("data/CommonEvents.json", common(commands))

    def test_source_alias_mismatch_is_explicit(self):
        rows, mismatches = event_fields("data/CommonEvents.json", common([
            command(102, [["A"], -1]), command(402, [0, "Old"]), command(404, [])]))
        self.assertEqual(rows[0].source, "A")
        self.assertEqual(mismatches[0].source, "Old")

    def test_context_crosses_non_display_commands_without_selecting_them(self):
        commands = [command(401, ["Before"])]
        commands += [command(355, ["console.log('internal')"])] * 12
        commands += [command(401, ["After"]), command(108, ["editor comment"])]
        rows, _ = event_fields("data/CommonEvents.json", common(commands))
        self.assertEqual([row.source for row in rows], ["Before", "After"])
        self.assertEqual(rows[1].context.nearby[0], (0, ("Before",)))

    def test_battle_fragments_have_composition_and_keep_spaces(self):
        rows = list(core_fields("data/Skills.json", [None, {"name": "Hit", "message1": " attacks %1!"}]))
        self.assertEqual(rows[1].source, " attacks %1!")
        self.assertEqual(rows[1].context.composition, "subject.name + fragment; %1=item.name")
        self.assertEqual(rows[0].context.related, (" attacks %1!",))

    def test_namebox_literal_is_language_but_shell_and_actor_id_are_protected(self):
        self.assertTrue(has_language(r"\n<Alice>"))
        self.assertFalse(has_language(r"\N[5]"))
        self.assertEqual(extract_tokens(r"\n<Alice>\N[5]"), [r"\n<", ">", r"\N[5]"])
        assert_preserved(r"\n<Alice>\C[2]3", r"\n<앨리스>\C[2]3")
        with self.assertRaises(ValueError):
            assert_preserved(r"\n<Alice>\C[2]3", r"\N<앨리스>\C[2]3")
        with self.assertRaises(ValueError):
            assert_preserved("2\n3", "2 3")


if __name__ == "__main__":
    unittest.main()
