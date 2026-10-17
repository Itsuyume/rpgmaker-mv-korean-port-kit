"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const font = require("../font-fallback.js");

test("Korean fallback precedes generic families and preserves named selections", () => {
    assert.equal(font.withKoreanFamily("GameFont, sans-serif"), "GameFont, PQNativeKorean, sans-serif");
    assert.equal(font.withKoreanFamily("BRTTER, Monaco"), "BRTTER, Monaco, PQNativeKorean");
    assert.equal(font.withKoreanFamily("serif"), "PQNativeKorean, serif");
    assert.equal(font.withKoreanFamily('"Fancy, serif, cool", sans-serif'),
        '"Fancy, serif, cool", PQNativeKorean, sans-serif');
    assert.equal(font.withKoreanFamily('"PQNativeKorean", serif'), '"PQNativeKorean", serif');
});

test("null, empty and malformed font lists fail rather than guessing", () => {
    for (const value of [null, "", "Arial,,serif", '"unclosed']) {
        assert.throws(() => font.withKoreanFamily(value));
    }
});

// This models only the external CSSStyleDeclaration boundary, not a browser renderer.
class CssStyleBoundary {
    constructor() { this.prefix = ""; this.fontFamily = ""; }
    set font(value) {
        const match = /^(.*?\d+(?:\.\d+)?px\s+)(.+)$/.exec(value);
        this.prefix = match ? match[1] : "";
        this.fontFamily = match ? match[2] : "";
    }
    get font() { return this.prefix ? this.prefix + this.fontFamily : ""; }
}

test("final bitmap hook preserves bold, italic, size and changed font option", () => {
    const prototype = {
        _makeFontNameText() {
            return (this.fontBold ? "bold " : "") + (this.fontItalic ? "italic " : "") +
                this.fontSize + "px " + this.fontFace;
        }
    };
    const document = {createElement() { return {style: new CssStyleBoundary()}; }};
    font.installBitmapFont(prototype, document);
    const bitmap = Object.assign(Object.create(prototype),
        {fontBold: true, fontItalic: true, fontSize: 26, fontFace: "GameFont, sans-serif"});
    assert.equal(bitmap._makeFontNameText(), "bold italic 26px GameFont, PQNativeKorean, sans-serif");
    bitmap.fontFace = "Monaco";
    bitmap.fontSize = 18;
    assert.equal(bitmap._makeFontNameText(), "bold italic 18px Monaco, PQNativeKorean");
});

test("font loading waits for one loaded bundled face and propagates failure", async () => {
    let requested;
    await font.load({fonts: {load: async value => { requested = value; return [{status: "loaded"}]; }}});
    assert.equal(requested, "28px PQNativeKorean");
    await assert.rejects(font.load({fonts: {load: async () => []}}), /could not be loaded/);
    await assert.rejects(font.load({fonts: {load: async () => { throw new Error("read failure"); }}}), /read failure/);
});
