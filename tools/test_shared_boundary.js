"use strict";
// All inputs are detached; the Python driver owns transaction/replay checks.
const fs = require("node:fs");
const { createBattle, CombatMagic: M, CombatCampaignAdapter: A } = require(
  process.argv[2] + "/sdk",
);
const pack = JSON.parse(fs.readFileSync(0, "utf8")),
  mode = process.argv[3];
const scene = pack.encounters[pack.default_encounter];
Object.assign(scene, {
  kind: "story",
  battle_id: "boundary-3052-" + mode,
  source_revision: pack.revision,
  source_state_sha256: pack.source_state_sha256,
});
if (mode === "large-field") {
  scene.width = 20;
  scene.height = 12;
}
const { engine: e } = createBattle(pack);
e.s.started = true;
if (mode === "cast-aid") {
  e.unit("yar").max += 5;
  e.unit("yar").hp += 5;
  M.add(
    e,
    { actor: "lyutobor", spell: "aid", level: 2 },
    "aid",
    ["yar"],
    28800,
    { amount: 5 },
  );
  e.s.elapsed = 28794;
}
if (mode === "heroism") {
  const x = M.add(
    e,
    { actor: "lyutobor", spell: "heroism", level: 1 },
    "heroism",
    ["yar"],
    60,
    { amount: 2 },
  );
  Object.assign(e.unit("yar"), { temp: 2, tempSource: x.id });
  e.s.elapsed = 54;
}
if (mode === "goad")
  e.status("yar", "goaded", {
    source: "raider1",
    stackBySource: true,
    expiresOnSourceEnd: "raider1",
    expiresOnSourceEndTurn: 1,
  });
if (mode === "large-field") {
  const x = M.add(
    e,
    { actor: "daphne", spell: "bigbyHand", level: 5 },
    "bigbyHand",
    [],
    60,
  );
  e.s.objects[x.id] = {
    id: x.id,
    owner: "daphne",
    x: 18,
    y: 10,
    hp: 50,
    max: 50,
    ac: 20,
    dc: 19,
    createdTurn: 0,
    grappled: null,
    interposing: false,
  };
  Object.assign(e.unit("raider1"), { x: 10, y: 2 });
  M.finishSteed(e, {
    actor: "lyutobor",
    level: 2,
    steedType: "celestial",
    point: { x: 9, y: 2 },
  });
}
e.s.phase = "ended";
e.emit("battleEnded", null, "Бой завершён.");
process.stdout.write(JSON.stringify(A.outcome(e.s)));
