/* Storage-only overlay; fonts are handled at the separate bitmap boundary. */
(function (installRuntime) {
    "use strict";
    if (typeof window === "undefined") {
        module.exports = installRuntime;
        return;
    }
    var originalOnload = window.onload;
    if (typeof originalOnload !== "function") {
        throw new Error("NativeRuntime must load immediately after MV main.js");
    }
    window.onload = function (event) {
        var receiver = this;
        return PQNativeFont.load(document).then(function () {
            PQNativeFont.install(window, Bitmap);
            installRuntime({
                storage: StorageManager,
                fs: require("fs"),
                path: require("path"),
                process: process,
                app: nw.App
            });
            return originalOnload.call(receiver, event);
        }).catch(function (error) {
            var panel = document.createElement("pre");
            panel.style.color = "white";
            panel.style.whiteSpace = "pre-wrap";
            panel.textContent = "게임을 시작할 수 없습니다.\n" + error.message;
            document.body.appendChild(panel);
            throw error;
        });
    };
}(/**
   * @param {{storage: {localFileDirectoryPath: function(): string},
   * fs: typeof import("node:fs"), path: typeof import("node:path"),
   * process: {platform: string, arch: string, mainModule?: {filename: string}},
   * app: {dataPath: string, manifest: {name: string,
   * "pq-runtime": {schema: number, profile: string}}}}} services
   * @returns {{profile: string, saveDirectory: string}}
   */
function installRuntime(services) {
    "use strict";
    var api = services;
    if (api.process.platform !== "darwin" || api.process.arch !== "arm64") {
        throw new Error("This package requires native macOS arm64 NW.js");
    }
    var config = api.app.manifest["pq-runtime"];
    if (!config || config.schema !== 1 || config.profile !== api.app.manifest.name) {
        throw new Error("NativeRuntime profile configuration is missing or inconsistent");
    }
    if (typeof api.storage.localFileDirectoryPath !== "function") {
        throw new Error("Expected RPG Maker MV StorageManager API");
    }
    if (typeof api.app.dataPath !== "string" || !api.path.isAbsolute(api.app.dataPath)) {
        throw new Error("NW.js must provide an absolute application data path");
    }
    if (!api.process.mainModule || typeof api.process.mainModule.filename !== "string") {
        throw new Error("NW.js start-page mainModule is missing");
    }
    var entry = api.path.resolve(api.process.mainModule.filename);
    var marker = api.path.sep + "Contents/Resources/app.nw/";
    var offset = entry.indexOf(marker);
    if (offset < 0 || !entry.slice(0, offset).endsWith(".app")) {
        throw new Error("Expected an unpacked macOS app.nw payload");
    }
    var bundleRoot = api.fs.realpathSync(entry.slice(0, offset));
    var dataDirectory = api.fs.realpathSync(api.app.dataPath);
    var relative = api.path.relative(bundleRoot, dataDirectory);
    if (relative === "" || (!api.path.isAbsolute(relative) && relative.split(api.path.sep)[0] !== "..")) {
        throw new Error("Application data path must stay outside the game bundle");
    }
    var saveDirectory = api.path.join(dataDirectory, "rpg-save-nyd412-v1");
    api.fs.mkdirSync(saveDirectory, {recursive: true, mode: 0o700});
    api.storage.localFileDirectoryPath = function () {
        return saveDirectory + api.path.sep;
    };
    return {profile: config.profile, saveDirectory: saveDirectory};
}));
