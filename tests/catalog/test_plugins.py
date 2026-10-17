"""Synthetic audited selectors: nested JSON, JS spans and opaque templates."""
import json
import unittest

from pq_catalog.js_spans import encode_target, replace_spans, selected_literal, template_blocks
from pq_catalog.js_strings import decode_literal, encode_literal
from pq_catalog.json_store import digest_bytes, digest_text
from pq_catalog.plugin_application import replace_file
from pq_catalog.plugin_codecs import apply_nested, parse_plugins, selected_text
from pq_catalog.plugin_contract import Span, Step, Target
from pq_catalog.plugin_diff import assert_nested_diff
from pq_catalog.tokens import assert_preserved


def parameter(source, steps):
    return Target("js/plugins.js", "file-hash", "plugins-array", source, digest_text(source),
                  "synthetic-display", tuple(steps), None, None, None, 0, "Synthetic", True, (), {})


def literal(data, source, raw, template=False, expressions=()):
    start = data.index(raw)
    quote = "`" if template else chr(raw[0])
    span = Span(start, start + len(raw), "utf8-bytes", quote)
    return Target("js/synthetic.js", digest_bytes(data), "js-template-literal" if template else "js-literals",
                  source, digest_text(source), "synthetic-display", (), span, digest_bytes(raw), None,
                  None, None, None, expressions, {})


class PluginTests(unittest.TestCase):
    def test_empty_and_duplicate_plugin_json_are_explicit_failures(self):
        for data in (b"", b'var $plugins=[{"name":"a","name":"b"}];', b'var $plugins=[];run();'):
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                parse_plugins(data)

    def test_nested_fields_share_one_outer_encode_and_keep_internal_values(self):
        quest = {"Title": "A title", "Description": json.dumps("A description"),
                 "Objectives": json.dumps([json.dumps("Find 3"), ""]), "Type": "InternalType", "ID": 4}
        document = [{"name": "Synthetic", "status": True, "parameters": {"Quest": json.dumps(quest)}}]
        root = Step((0, "parameters", "Quest"), "json")
        title = parameter("A title", [root, Step(("Title",), "raw")])
        description = parameter("A description", [root, Step(("Description",), "json-string")])
        objective = parameter("Find 3", [root, Step(("Objectives",), "json"), Step((0,), "json-string")])
        after = apply_nested(document, [(title, "제목"), (description, "설명"), (objective, "3개 찾기")])
        result = json.loads(after[0]["parameters"]["Quest"])
        self.assertEqual(result["Title"], "제목")
        self.assertEqual(json.loads(result["Description"]), "설명")
        self.assertEqual(json.loads(result["Objectives"]), [json.dumps("3개 찾기", ensure_ascii=False), ""])
        self.assertEqual((result["Type"], result["ID"]), ("InternalType", 4))
        self.assertEqual(json.loads(document[0]["parameters"]["Quest"]), quest)
        self.assertEqual(selected_text(document, objective), "Find 3")

    def test_decoded_diff_rejects_unlisted_internal_value_changes(self):
        before = [{"name": "Synthetic", "status": True, "parameters": {"Data": json.dumps({"Title": "A", "ID": 4})}}]
        target = parameter("A", [Step((0, "parameters", "Data"), "json"), Step(("Title",), "raw")])
        after = apply_nested(before, [(target, "제목")])
        assert_nested_diff(before, after, [(target, "제목")])
        changed = json.loads(after[0]["parameters"]["Data"]); changed["ID"] = 5
        after[0]["parameters"]["Data"] = json.dumps(changed)
        with self.assertRaises(ValueError):
            assert_nested_diff(before, after, [(target, "제목")])

    def test_identity_changes_preserve_original_plugin_bytes(self):
        data = b'// prefix\nvar $plugins = [{"name":"Synthetic","status":true,"parameters":{"Text":"Hello"}}];\r\n'
        target = parameter("Hello", [Step((0, "parameters", "Text"), "raw")])
        self.assertEqual(replace_file(data, [(target, "Hello")]), data)
        result = replace_file(data, [(target, "안녕")])
        self.assertTrue(result.startswith(b"// prefix\nvar $plugins = "))
        self.assertTrue(result.endswith(b";\r\n"))
        self.assertEqual(parse_plugins(result)[1][0]["parameters"]["Text"], "안녕")

    def test_plugin_status_and_source_guards_fail(self):
        document = [{"name": "Synthetic", "status": False, "parameters": {"Text": "Hello"}}]
        target = parameter("Hello", [Step((0, "parameters", "Text"), "raw")])
        with self.assertRaises(ValueError):
            selected_text(document, target)
        document[0]["status"] = True; document[0]["parameters"]["Text"] = "Changed"
        with self.assertRaises(ValueError):
            selected_text(document, target)

    def test_js_literal_utf8_span_changes_only_one_equal_literal(self):
        data = 'const prefix="한글";const a="Retry";const b="Retry";\n'.encode()
        target = literal(data, "Retry", b'"Retry"')
        result = replace_spans(data, [(target, "다시 시도")])
        self.assertEqual(result, data.replace(b'"Retry"', '"다시 시도"'.encode(), 1))
        self.assertEqual(selected_literal(data, target, "utf8-bytes"), "Retry")
        self.assertEqual(replace_spans(data, [(target, "Retry")]), data)
        with self.assertRaises(ValueError):
            replace_spans(data, [(target, "a"), (target, "b")])

    def test_js_quote_encoder_round_trip_contains_code_as_text(self):
        text = "';runDangerous();\\\n\t\0한글\u2028"
        for quote in ("'", '"'):
            self.assertEqual(decode_literal(encode_literal(text, quote)), text)
        with self.assertRaises(ValueError):
            decode_literal(b"'unescaped'quote'")

    def test_template_expressions_commands_and_paths_are_opaque(self):
        source = 'Open ${device.path()} <pre>command --flag </pre> "Demo.app"'
        data = ("const message=`" + source + "`;").encode()
        target = literal(data, source, ("`" + source + "`").encode(), True, ("device.path()",))
        blocks = template_blocks(source, target.expressions)
        korean = '${device.path()} 열기 <pre>command --flag </pre> "Demo.app"'
        assert_preserved(source, korean, blocks)
        self.assertEqual(encode_target(target, korean), ("`" + korean + "`").encode())
        for invalid in (korean.replace("device.path()", "other()"), korean.replace("--flag", "--다른"),
                        korean + "${newCall()}", korean + "`", korean.replace("Demo.app", "데모.app")):
            with self.assertRaises(ValueError):
                encode_target(target, invalid)


if __name__ == "__main__":
    unittest.main()
