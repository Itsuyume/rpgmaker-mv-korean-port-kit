/* Keep original Latin fonts and sizes; insert Korean before generic fallback. */
(function (factory) {
    "use strict";
    var api = factory();
    if (typeof window === "undefined") {
        module.exports = api;
        return;
    }
    window.PQNativeFont = api;
}(function () {
    "use strict";
    var family = "PQNativeKorean";

    function splitFamilies(value) {
        var result = [], start = 0, quote = "", escaped = false;
        for (var index = 0; index < value.length; index += 1) {
            var character = value[index];
            if (escaped) { escaped = false; continue; }
            if (character === "\\") { escaped = true; continue; }
            if (quote) {
                if (character === quote) { quote = ""; }
                continue;
            }
            if (character === "'" || character === '"') { quote = character; continue; }
            if (character === ",") {
                result.push(value.slice(start, index).trim());
                start = index + 1;
            }
        }
        result.push(value.slice(start).trim());
        if (quote || escaped || result.some(function (item) { return !item; })) {
            throw new Error("Invalid CSS font-family list");
        }
        return result;
    }

    /** @param {string} families @returns {string} */
    function withKoreanFamily(families) {
        if (typeof families !== "string") {
            throw new TypeError("Font-family list must be a string");
        }
        var parts = splitFamilies(families);
        if (parts.some(function (item) {
            return item.replace(/^['"]|['"]$/g, "").toLowerCase() === family.toLowerCase();
        })) {
            return families;
        }
        var generics = new Set(["serif", "sans-serif", "monospace", "system-ui", "cursive",
            "fantasy", "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded"]);
        var insertion = parts.findIndex(function (item) { return generics.has(item.toLowerCase()); });
        parts.splice(insertion < 0 ? parts.length : insertion, 0, family);
        return parts.join(", ");
    }

    /** @param {{_makeFontNameText: function(): string}} prototype @param {Document} document */
    function installBitmapFont(prototype, document) {
        var original = prototype._makeFontNameText;
        if (typeof original !== "function") {
            throw new Error("Expected the final MV Bitmap font method");
        }
        var parser = document.createElement("span").style;
        var cache = new Map();
        prototype._makeFontNameText = function () {
            var actual = original.call(this);
            if (!cache.has(actual)) {
                parser.font = "";
                parser.font = actual;
                if (!parser.font) {
                    throw new Error("The selected bitmap font is not valid CSS");
                }
                parser.fontFamily = withKoreanFamily(parser.fontFamily);
                cache.set(actual, parser.font);
            }
            return cache.get(actual);
        };
    }

    /** @param {Document} document @returns {Promise<void>} */
    function load(document) {
        return document.fonts.load("28px " + family, "한글 표시 검사").then(function (faces) {
            if (faces.length !== 1 || faces[0].status !== "loaded") {
                throw new Error("The bundled Korean font could not be loaded");
            }
        });
    }

    /**
     * @typedef {{initialize: function({name: function(): string}, number): void,
     * charWidth: function(): number}} NameEditPrototype
     * @param {NameEditPrototype} prototype
     * @param {function(): number} boxWidth
     * MV name editing is an external engine boundary; keep its Latin-only sizing.
     */
    function installNameEdit(prototype, boxWidth) {
        var initialize = prototype.initialize;
        var charWidth = prototype.charWidth;
        if (typeof initialize !== "function" || typeof charWidth !== "function") {
            throw new Error("Expected the MV name-edit sizing methods");
        }
        prototype.charWidth = function () {
            var original = charWidth.call(this);
            return /[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]/.test(this._name) ?
                Math.max(original, this.textWidth("한")) : original;
        };
        prototype.initialize = function (actor, maxLength) {
            initialize.call(this, actor, maxLength);
            var needed = Math.ceil(this.faceWidth() + (maxLength + 1) *
                this.charWidth() + this.padding * 2);
            var width = Math.min(boxWidth(), Math.max(this.width, needed));
            if (width === this.width) { return; }
            this.move((boxWidth() - width) / 2, this.y, width, this.height);
            this.createContents();
            this.refresh();
        };
    }

    /**
     * @param {{document: Document, Window_NameEdit: {prototype: NameEditPrototype},
     * Graphics: {boxWidth: number}}} window
     * @param {{prototype: {_makeFontNameText: function(): string}}} bitmap
     */
    function install(window, bitmap) {
        installBitmapFont(bitmap.prototype, window.document);
        installNameEdit(window.Window_NameEdit.prototype, function () {
            return window.Graphics.boxWidth;
        });
    }

    return {withKoreanFamily: withKoreanFamily, installBitmapFont: installBitmapFont,
            installNameEdit: installNameEdit, load: load, install: install};
}));
