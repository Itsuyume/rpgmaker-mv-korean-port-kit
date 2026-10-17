"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const installRuntime = require("../addin.js");

function fixture(t) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "pq boundary "));
    t.after(() => fs.rmSync(root, {recursive: true}));
    const bundle = path.join(root, "Synthetic.app");
    const entry = path.join(bundle, "Contents/Resources/app.nw/www/index.html");
    fs.mkdirSync(path.dirname(entry), {recursive: true});
    const dataPath = path.join(root, "new isolated profile/Default");
    fs.mkdirSync(dataPath, {recursive: true});
    const oldDirectory = path.join(path.dirname(entry), "save") + path.sep;
    fs.mkdirSync(oldDirectory);
    const storage = {
        localFileDirectoryPath() { return oldDirectory; },
        save(name, bytes) { fs.writeFileSync(this.localFileDirectoryPath() + name, bytes); },
        load(name) { return fs.readFileSync(this.localFileDirectoryPath() + name); }
    };
    const app = {dataPath, manifest: {name: "synthetic-pq",
        "pq-runtime": {schema: 1, profile: "synthetic-pq"}}};
    return {root, bundle, oldDirectory, storage, services: {storage, app, fs, path,
        process: {platform: "darwin", arch: "arm64", mainModule: {filename: entry}}}};
}

test("save/load/backup use only the isolated directory and preserve opaque bytes", t => {
    const f = fixture(t);
    fs.writeFileSync(f.oldDirectory + "file1.rpgsave", "old save stays here");
    const result = installRuntime(f.services);
    const bytes = Buffer.from([0, 255, 45, 20, 0, 91]);
    f.storage.save("file1.rpgsave", bytes);
    f.storage.save("file1.rpgsave.bak", f.storage.load("file1.rpgsave"));
    f.storage.save("config.rpgsave", Buffer.from("new config"));
    assert.deepEqual(f.storage.load("file1.rpgsave.bak"), bytes);
    assert.equal(fs.readFileSync(f.oldDirectory + "file1.rpgsave", "utf8"), "old save stays here");
    assert.equal(fs.existsSync(f.oldDirectory + "config.rpgsave"), false);
    assert.equal(path.dirname(result.saveDirectory), fs.realpathSync(f.services.app.dataPath));
    assert.equal(fs.statSync(result.saveDirectory).mode & 0o777, 0o700);
});

test("a profile anywhere inside the app is rejected before making a save directory", t => {
    const f = fixture(t);
    for (const suffix of ["Contents/Resources/app.nw/profile", "Contents/OtherProfile"]) {
        const candidate = path.join(f.bundle, suffix);
        fs.mkdirSync(candidate, {recursive: true});
        f.services.app.dataPath = candidate;
        assert.throws(() => installRuntime(f.services), /outside the game bundle/);
        assert.equal(fs.existsSync(path.join(candidate, "rpg-save-nyd412-v1")), false);
    }
    assert.equal(f.storage.localFileDirectoryPath(), f.oldDirectory);
});

test("profile symlinks cannot redirect saves into the app", t => {
    const f = fixture(t);
    const alias = path.join(f.root, "profile alias");
    fs.symlinkSync(f.bundle, alias);
    f.services.app.dataPath = alias;
    assert.throws(() => installRuntime(f.services), /outside the game bundle/);
    assert.equal(fs.existsSync(path.join(f.bundle, "rpg-save-nyd412-v1")), false);
});

test("filesystem failure never falls back to the original save directory", t => {
    const f = fixture(t);
    fs.writeFileSync(path.join(f.services.app.dataPath, "rpg-save-nyd412-v1"), "collision");
    assert.throws(() => installRuntime(f.services), {code: "EEXIST"});
    assert.equal(f.storage.localFileDirectoryPath(), f.oldDirectory);
});

test("wrong architecture, missing profile and absent main module fail explicitly", t => {
    const f = fixture(t);
    f.services.process.arch = "x64";
    assert.throws(() => installRuntime(f.services), /native macOS arm64/);
    f.services.process.arch = "arm64";
    f.services.app.manifest["pq-runtime"].profile = "other";
    assert.throws(() => installRuntime(f.services), /inconsistent/);
    f.services.app.manifest["pq-runtime"].profile = "synthetic-pq";
    delete f.services.process.mainModule;
    assert.throws(() => installRuntime(f.services), /mainModule/);
    assert.equal(f.storage.localFileDirectoryPath(), f.oldDirectory);
});
