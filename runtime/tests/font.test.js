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

// Minimal external MV window API. Canvas rendering is checked in the actual app.
class NameEditBoundary {
    initialize(actor, maxLength) {
        this._name = actor.name();
        this._maxLength = maxLength;
        Object.assign(this, {width: 480, height: 180, y: 80, padding: 18, redraws: 0});
    }
    charWidth() { return 15; }
    textWidth(text) { return text === "한" ? 28 : 15; }
    faceWidth() { return 144; }
    move(x, y, width, height) { Object.assign(this, {x, y, width, height}); }
    createContents() { this.redraws += 1; }
    refresh() { this.renderedName = this._name; }
}

test("a twelve-slot Korean name reserves full glyph cells beside the portrait", () => {
    class KoreanNameEdit extends NameEditBoundary {}
    font.installNameEdit(KoreanNameEdit.prototype, () => 816);
    const window = new KoreanNameEdit();
    window.initialize({name: () => "가나다라마바사아자차카타"}, 12);
    const available = window.width - window.padding * 2 - window.faceWidth();
    assert.equal(window.charWidth(), 28);
    assert.ok(available >= 13 * window.charWidth());
    assert.equal(window.renderedName, "가나다라마바사아자차카타");
    assert.ok(window.x >= 0 && window.x + window.width <= 816);
    assert.equal(window.redraws, 1);
});

test("empty and Latin names retain the original layout and input length", () => {
    class LatinNameEdit extends NameEditBoundary {}
    font.installNameEdit(LatinNameEdit.prototype, () => 816);
    for (const name of ["", "Player", "ABCDEFGHIJKL"]) {
        const window = new LatinNameEdit();
        window.initialize({name: () => name}, 12);
        assert.equal(window.charWidth(), 15);
        assert.equal(window.width, 480);
        assert.equal(window._maxLength, 12);
        assert.equal(window.redraws, 0);
    }
});

test("an unsupported name-edit API fails at the installation boundary", () => {
    assert.throws(() => font.installNameEdit({}, () => 816), /name-edit/);
});
