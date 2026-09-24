// The drop table viewer against the real engine and the real compiled scripts: examine an npc through
// ExamineNpcHandler.examine (everything the EXAMINE_NPC packet does past its visibility gate, which a
// socketless player can never pass) and read back what the server sent - the window, every if_settext
// and the icon inv - against the rows tools/gennpcdrops.py wrote to npc_drops.dbrow.
// Run it through tools/npcdrops_battery.py, which puts it inside the engine and takes it out again.
import fs from 'fs';
import World from '#/engine/World.js';
import NpcType from '#/cache/config/NpcType.js';
import ObjType from '#/cache/config/ObjType.js';
import InvType from '#/cache/config/InvType.js';
import Component from '#/cache/config/Component.js';
import Environment from '#/util/Environment.js';
import ExamineNpcHandler from '#/network/game/client/handler/ExamineNpcHandler.js';
import * as H from './harness.js';

const TIERS = [7, 15, 30, 60, 120];

// npc -> [obj, name, amount, rarity][] as generated
const TABLES = new Map<string, string[][]>();
{
    let rows: string[][] = [];
    let npcs: string[] = [];
    const flush = () => {
        for (const n of npcs) TABLES.set(n, rows);
    };
    for (const raw of fs.readFileSync(`${Environment.BUILD_SRC_DIR}/scripts/drop_tables/configs/npc_drops.dbrow`, 'utf8').split('\n')) {
        const line = raw.trim();
        if (line.startsWith('[')) {
            flush();
            rows = [];
            npcs = [];
        } else if (line.startsWith('data=npc,')) {
            npcs.push(line.slice('data=npc,'.length));
        } else if (line.startsWith('data=drop,')) {
            rows.push(line.slice('data=drop,'.length).split(','));
        }
    }
    flush();
}

const R = { ok: 0, bad: 0 };
function check(what: string, got: unknown, want: unknown) {
    const pass = JSON.stringify(got) === JSON.stringify(want);
    if (pass) R.ok++;
    else R.bad++;
    console.log(`  ${pass ? 'ok  ' : 'FAIL'} ${what}${pass ? '' : `\n         got  ${JSON.stringify(got)}\n         want ${JSON.stringify(want)}`}`);
}

await H.boot();
H.loginOrder();
const p = H.makePlayer('looker', 3222, 3222, 1);
H.tick(2);
H.maxOut(p);
const DROPS_IF = Component.getId('npc_drops');
const INV = InvType.getId('npcdrops');

function examine(name: string) {
    const npc = H.addNpcAt(name, 3224, 3224, 0);
    H.tick(1);
    H.clearLogs();
    ExamineNpcHandler.examine(p, npc);
    H.tick(1);
    // the server's own record of the open window (a socketless Player never writes IF_OPENMAIN -
    // that is NetworkPlayer's job - so the modal state is the thing to read)
    const opened = (p as any).modalMain === DROPS_IF;
    // component name -> the last text the server sent it
    const text = new Map<string, string>();
    for (const i of H.ifaces) {
        if (i.who === 'looker' && i.kind === 'text') text.set(Component.get(i.com).comName ?? String(i.com), i.text ?? '');
    }
    const said = H.mesgs.filter(m => m.who === 'looker').map(m => m.text);
    const inv = p.getInventory(INV);
    const icons: string[] = [];
    if (inv) {
        for (let s = 0; s < inv.capacity; s++) {
            const o = inv.get(s);
            if (o) icons.push(ObjType.get(o.id).debugname ?? String(o.id));
        }
    }
    p.closeModal();
    World.removeNpc(npc, -1);
    H.tick(1);
    return { opened, text, said, icons };
}

function viewer(name: string, subtitle?: string) {
    const want = TABLES.get(name)!;
    const tier = TIERS.findIndex(n => want.length <= n) + 1;
    const size = TIERS[tier - 1];
    console.log(`${name}: ${want.length} rows, tier ${tier} (${size})`);
    const r = examine(name);
    check(`${name}: the examine text still comes first`, r.said.length > 0, true);
    check(`${name}: the drop table window opened`, r.opened, true);
    check(`${name}: titled with its name`, r.text.get('npc_drops:title'), NpcType.get(NpcType.getId(name)).name);
    if (subtitle !== undefined) check(`${name}: subtitle`, r.text.get('npc_drops:subtitle'), subtitle);
    const rows: string[][] = [];
    for (let i = 1; i <= size; i++) {
        rows.push([r.text.get(`npc_drops:name${tier}_${i}`) ?? '?', r.text.get(`npc_drops:qty${tier}_${i}`) ?? '?', r.text.get(`npc_drops:rate${tier}_${i}`) ?? '?']);
    }
    const blank = Array.from({ length: size - want.length }, () => ['', '', '']);
    check(`${name}: every row of tier ${tier} as generated, the rest blank`, rows, [...want.map(w => [w[1], w[2], w[3]]), ...blank]);
    check(`${name}: the icons`, r.icons, want.map(w => w[0]));
    for (const w of want.slice(0, 4)) console.log(`       ${w[1].padEnd(28)} ${w[2].padEnd(10)} ${w[3]}`);
    // no other tier was written to
    const other = [...r.text.keys()].filter(k => /^npc_drops:(name|qty|rate)\d+_/.test(k) && !new RegExp(`^npc_drops:(name|qty|rate)${tier}_`).test(k));
    check(`${name}: no other tier touched`, other, []);
}

console.log('DROP TABLE VIEWER');
viewer('goblin', 'Combat level 2');
viewer('chicken');
viewer('king_dragon', 'Combat level 276. Your game mode: +2 rare drop table rolls');
viewer('graardor');
viewer('superior_night_beast');

// the same window again with a SHORTER table after a long one: nothing left over
viewer('chicken');

for (const name of ['spider', 'banker1']) {
    const r = examine(name);
    check(`${name}: no table, so examine opens nothing and still describes it`, [r.opened, r.said.length > 0], [false, true]);
}

console.log(`\n${R.ok} ok, ${R.bad} failed`);
process.exit(R.bad ? 1 : 0);
