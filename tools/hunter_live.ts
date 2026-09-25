import fs from 'fs';
// Live test of box trapping against the real engine and the real compiled scripts: a socketless
// player, the real world tick (run fast), triggers fired the way the packet handlers fire them.
// Run it through tools/hunter_live_battery.py, which puts it inside the engine and takes it out.
//
// What a compile cannot see and this does: the trap loop actually springing on a wandering prey
// npc, the level gate (HLEVEL below the grey chinchompa's 53 must catch NOTHING in their clearing),
// ownership, the leash, and [logout] handing traps back.
//
// Two things about driving a socketless player, both learned the hard way:
//  - nothing refreshes its lastResponse, so the world logs it out 50 ticks after login - which runs
//    the real [logout] and quietly takes up every trap. waitTicks keeps it alive.
//  - a click made while the player is delayed is DISCARDED (Player.runScript refuses protected
//    access), exactly as the packet handler would; so every action here waits out its own delay.
import World from '#/engine/World.js';
import { PlayerLoading } from '#/engine/entity/PlayerLoading.js';
import Packet from '#/io/Packet.js';
import ScriptProvider from '#/engine/script/ScriptProvider.js';
import ScriptRunner from '#/engine/script/ScriptRunner.js';
import ServerTriggerType from '#/engine/script/ServerTriggerType.js';
import ObjType from '#/cache/config/ObjType.js';
import LocType from '#/cache/config/LocType.js';
import InvType from '#/cache/config/InvType.js';
import VarPlayerType from '#/cache/config/VarPlayerType.js';
import SeqType from '#/cache/config/SeqType.js';
import NpcType from '#/cache/config/NpcType.js';
import SpotanimType from '#/cache/config/SpotanimType.js';
import Component from '#/cache/config/Component.js';
import EnumType from '#/cache/config/EnumType.js';
const PlayerStat = { HUNTER: 22 };
import { getExpByLevel } from '#/engine/entity/Player.js';

// The login/friend/logger worker threads cannot resolve '#/' imports outside the app's own launch;
// this test needs none of them, so their failures are swallowed rather than allowed to end the process.
for (const k of ['loginThread', 'friendThread', 'loggerThread']) (World as any)[k]?.on?.('error', () => {});

const LEVEL = parseInt(process.env.HLEVEL ?? '70');
const CONST = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter.constant`, 'utf8');
const RCONST = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter_rellekka.constant`, 'utf8');
// HTRAP=box (default) lays box traps in the grey chinchompas' clearing; HTRAP=snare lays bird snares
// among the tropical wagtails. The level gate is the lowest-level prey near the traps.
const SNARE = process.env.HTRAP === 'snare';
const TRAPNAME = SNARE ? 'hunter_bird_snare' : 'hunter_box_trap';
const GATE_NAME = SNARE ? 'tropical wagtail' : 'grey chinchompa';
const GREY = parseInt((SNARE ? /\^hunter_wagtail_level = (\d+)/ : /\^hunter_chinchompa_level = (\d+)/).exec(CONST)![1]);
const CAN_CATCH = LEVEL >= GREY;
const log = (...a: unknown[]) => console.log(`[t${World.currentTick}]`, ...a);
let player: any;
const waitTicks = (n: number) => new Promise<void>(res => {
    const target = World.currentTick + n;
    const iv = setInterval(() => {
        // a socketless player is logged out 50 ticks after its last "response"; keep it alive
        if (typeof player !== 'undefined') { player.lastResponse = World.currentTick; player.lastConnected = World.currentTick; }
        if (World.currentTick >= target) { clearInterval(iv); res(); }
    }, 1);
});

let fails = 0;
const check = (ok: boolean, what: string) => { console.log((ok ? '  ok   ' : '  FAIL ') + what); if (!ok) fails++; };

await World.start(false, true);
World.tickRate = 4;

player = PlayerLoading.load('hunttest', new Packet(new Uint8Array(0)), null);
player.members = true;
for (const s of [PlayerStat.HUNTER]) {
    player.stats[s] = getExpByLevel(LEVEL);
    player.baseLevels[s] = LEVEL;
    player.levels[s] = LEVEL;
}
player.x = 2570; player.z = 2887; player.level = 0;
const msgs: string[] = [];
player.messageGame = (m: string) => { msgs.push(m); log('MES', m); };
World.newPlayers.add(player);
await waitTicks(3);
check(World.getPlayerByUsername('hunttest') !== null, 'player is in the world');
// HTRAP=cape: the Hunter skillcape instead of the traps - worn at 99, and its emote plays.
if (process.env.HTRAP === 'cape') {
    const inv0 = player.getInventory(InvType.INV)!;
    const worn = player.getInventory(InvType.WORN)!;
    const played: number[] = [], spots: number[] = [];
    const pa = player.playAnimation.bind(player); (player as any).playAnimation = (a: number, d: number) => { played.push(a); return pa(a, d); };
    const sp = player.spotanim.bind(player); (player as any).spotanim = (a: number, h: number, d: number) => { spots.push(a); return sp(a, h, d); };
    for (const cape of ['hunter_cape', 'hunter_cape_t']) {
        const id = ObjType.getId(cape);
        player.invAdd(InvType.INV, id, 1);
        const wear = () => {
            player.lastItem = id; player.lastSlot = inv0.getItemIndex(id);
            const script = ScriptProvider.getByTrigger(ServerTriggerType.OPHELD2, id, ObjType.get(id).category);
            player.executeScript(ScriptRunner.init(script!, player), true);
        };
        wear(); await waitTicks(2);
        check(worn.getItemCount(id) === 0, `${cape}: refused below 99 Hunter (level ${LEVEL})`);
        player.stats[PlayerStat.HUNTER] = getExpByLevel(99); player.baseLevels[PlayerStat.HUNTER] = 99; player.levels[PlayerStat.HUNTER] = 99;
        wear(); await waitTicks(2);
        check(worn.getItemCount(id) === 1, `${cape}: worn at 99`);
        played.length = 0; spots.length = 0;
        const com = Component.getId('emotes:skill_cape');
        const script = ScriptProvider.getByTrigger(ServerTriggerType.IF_BUTTON, com, -1);
        player.executeScript(ScriptRunner.init(script!, player), true);
        await waitTicks(2);
        check(played.includes(SeqType.getId('skillcape_hunter_emote')), `${cape}: the Skillcape emote plays skillcape_hunter_emote`);
        check(spots.includes(SpotanimType.getId('skillcape_hunter')), `${cape}: ...with the skillcape_hunter graphic`);
        check(!msgs.some(m => m.includes('need to be wearing a Skillcape')), `${cape}: ...and does not refuse`);
        // take it off again and drop back below 99 for the next one
        worn.removeAll(); inv0.remove(id, 1);
        player.stats[PlayerStat.HUNTER] = getExpByLevel(LEVEL); player.baseLevels[PlayerStat.HUNTER] = LEVEL; player.levels[PlayerStat.HUNTER] = LEVEL;
    }
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

// HTRAP=pisc_map | pisc_track | pisc_traps | falconry: the Piscatoris hunter area (hunter_piscatoris.rs2,
// hunter_falconry.rs2). pisc_map checks the imported ground: every spawn on an open tile, every tracking
// node where the enums say, the ::piscatoris landings open, a walk from the stile to every ground and every
// spawn, and the enclosure fenced but for the stile. pisc_track follows common and razor-backed kebbit
// trails to a catch. pisc_traps lays snares among the copper longtails, sets deadfalls among the prickly
// kebbits and box traps among the chinchompas, and expects a catch exactly where the level allows it.
// falconry is Matthias, the glove, the three kebbits, a miss, a retrieve, a falcon that gives up, the
// stile and a teleport out.
if (process.env.HTRAP?.startsWith('pisc') || process.env.HTRAP === 'falconry') {
    const MODE = process.env.HTRAP;
    const inv0 = player.getInventory(InvType.INV)!;
    const worn = player.getInventory(InvType.WORN)!;
    const tot = (n: string) => inv0.getItemCount(ObjType.getId(n));
    const PCONST = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter_piscatoris.constant`, 'utf8');
    const pnum = (n: string) => parseInt(new RegExp(`\\^${n} = (-?\\d+)`).exec(PCONST)![1]);
    const setLevel = (l: number) => { player.stats[PlayerStat.HUNTER] = getExpByLevel(l); player.baseLevels[PlayerStat.HUNTER] = l; player.levels[PlayerStat.HUNTER] = l; };
    const v = (n: string) => player.getVar(VarPlayerType.getId(n)) as number;
    const xz = (c: number) => ({ x: (c >> 14) & 0x3fff, z: c & 0x3fff });
    const { isMapBlocked, canTravel } = await import('#/engine/GameMap.js');
    const { CollisionType } = await import('#/engine/routefinder/index.js');
    const ScriptState = (await import('#/engine/script/ScriptState.js')).default;
    const run = (trigger: number, id: number, cat: number, target?: any) => {
        const script = ScriptProvider.getByTrigger(trigger, id, cat);
        if (!script) { log('no script for trigger', trigger, id); return; }
        player.executeScript(ScriptRunner.init(script, player, target), true);
    };
    const oploc = (op: number, loc: any) => { const t = LocType.get(loc.type); run(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category, loc); };
    const opnpc = (op: number, npc: any, ap = false) => { const t = NpcType.get(npc.type); run((ap ? ServerTriggerType.APNPC1 : ServerTriggerType.OPNPC1) + (op - 1), t.id, t.category, npc); };
    // Answer a dialogue: continue through every page, and at each choice pick the next of `picks` (1-based).
    const converse = async (picks: number[]) => {
        for (let i = 0; i < 60; i++) {
            await waitTicks(1);
            const s = player.activeScript;
            if (!s) { if (process.env.HTRACE) log('converse: no script'); return; }
            if (s.execution !== ScriptState.PAUSEBUTTON) { if (process.env.HTRACE) log('converse: state', s.execution); continue; }
            const rb = player.resumeButtons as number[];
            const chat = player.modalChat !== -1 ? Component.get(player.modalChat)?.comName ?? '' : '';
            if (process.env.HTRACE) log('converse', chat, rb.length, JSON.stringify(picks));
            if (chat.startsWith('multi')) { const k = picks.shift(); if (!k) { log('converse: no pick left at', chat); return; } player.lastCom = Component.getId(`${chat}:com_${k}`); }
            else player.lastCom = rb[0] ?? -1;
            player.executeScript(s, true, true);
        }
    };
    const npcsOf = (name: string) => { const id = NpcType.getId(name); const out: any[] = []; for (const n of World.npcs) if (n && n.type === id) out.push(n); return out; };
    const cheb = (a: any, x: number, z: number) => Math.max(Math.abs(a.x - x), Math.abs(a.z - z));
    const nearest = (name: string, x: number, z: number) => npcsOf(name).filter(n => n.isActive !== false).sort((a, b) => cheb(a, x, z) - cheb(b, x, z))[0];
    const flood = (sx: number, sz: number, box: number[]) => {
        const seenT = new Set<string>([`${sx},${sz}`]); const q = [[sx, sz]];
        while (q.length) {
            const [x, z] = q.shift()!;
            for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
                const k = `${x + dx},${z + dz}`;
                if (seenT.has(k) || x + dx < box[0] || x + dx > box[2] || z + dz < box[1] || z + dz > box[3]) continue;
                if (!canTravel(0, x, z, dx, dz, 1, 0, CollisionType.NORMAL)) continue;
                seenT.add(k); q.push([x + dx, z + dz]);
            }
        }
        return seenT;
    };
    // the falconry enclosure: ~falconry_in_area's rows (falconry_area_rows in hunter_piscatoris.enum), min*10000+max
    const ROWS = new Map([...fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter_piscatoris.enum`, 'utf8').split('[falconry_area_rows]')[1].matchAll(/val=(\d+),(\d+)/g)].map(m => [+m[1], +m[2]]));
    const AREA = [2364, 3573, 2393, 3620];
    const inArea = (x: number, z: number) => { const r = ROWS.get(z); return r !== undefined && x >= Math.floor(r / 10000) && x <= r % 10000; };
    const enumCoords = (name: string) => {
        const txt = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter_piscatoris.enum`, 'utf8');
        const sec = txt.split(`[${name}]`)[1].split('\n[')[0];
        return [...sec.matchAll(/val=\d+,0_(\d+)_(\d+)_(\d+)_(\d+)/g)].map(m => ({ x: +m[1] * 64 + +m[3], z: +m[2] * 64 + +m[4] }));
    };
    const PLANTS = ['loc474_19339', 'loc474_19340', 'loc474_19341', 'loc474_19342'].map(n => LocType.getId(n));
    const NODES = [...PLANTS, ...['loc474_19492', 'loc474_19438', 'loc474_19429', 'loc474_19428'].map(n => LocType.getId(n))];
    const nodeAt = (x: number, z: number) => { for (const t of NODES) { const l = World.getLoc(x, z, 0, t); if (l) return l; } return null; };
    const LANDINGS = [[2335, 3578], [2371, 3623], [2325, 3618], [2354, 3597]];

    if (MODE === 'pisc_map') {
        const SPAWNS: Record<string, number> = { hunter_copper_longtail: 15, hunter_prickly_kebbit: 20, hunter_spotted_kebbit: 7, hunter_dark_kebbit: 7, hunter_dashing_kebbit: 3, hunter_ruby_harvest: 22, hunter_matthias: 1 };
        for (const [name, n] of Object.entries(SPAWNS)) {
            const all = npcsOf(name);
            check(all.length === n, `${n} ${name} in the world (${all.length})`);
            const bad = all.filter(s => isMapBlocked(s.startX, s.startZ, 0)).map(s => `${s.startX},${s.startZ}`);
            check(bad.length === 0, `...every one spawned on an open tile (${bad.join(' ') || 'all'})`);
        }
        // wild kebbits and chinchompas are Feldip's npcs too; count the ones in this area
        const here = (s: any) => s.startX >= 2304 && s.startX < 2432 && s.startZ >= 3520 && s.startZ < 3648;
        for (const [name, n] of [['hunter_wild_kebbit', 20], ['hunter_chinchompa', 22]] as [string, number][]) {
            const hs = npcsOf(name).filter(here);
            check(hs.length === n, `${n} ${name} spawned in the Piscatoris area (${hs.length})`);
            const bad = hs.filter(s => isMapBlocked(s.startX, s.startZ, 0)).map(s => `${s.startX},${s.startZ}`);
            check(bad.length === 0, `...every one on an open tile (${bad.join(' ') || 'all'})`);
        }
        const fk = ['hunter_spotted_kebbit', 'hunter_dark_kebbit', 'hunter_dashing_kebbit', 'hunter_matthias'].flatMap(npcsOf).filter(s => !inArea(s.startX, s.startZ));
        check(fk.length === 0, `the falconry kebbits and Matthias all spawn inside the enclosure (${fk.map(s => `${s.startX},${s.startZ}`).join(' ') || 'all'})`);
        for (const e of ['hunter_pisc_common_nodes', 'hunter_pisc_common_bushes', 'hunter_pisc_razor_nodes', 'hunter_pisc_razor_bushes']) {
            const cs = enumCoords(e); const miss = cs.filter(c => !nodeAt(c.x, c.z));
            check(cs.length > 0 && miss.length === 0, `${e}: every one of its ${cs.length} coords holds a tracking node (${miss.map(c => `${c.x},${c.z}`).join(' ') || 'all'})`);
        }
        for (const [x, z] of LANDINGS) check(!isMapBlocked(x, z, 0), `::piscatoris lands on an open tile at ${x},${z}`);
        // walk: from outside the stile to every ground and every open-area spawn; never into the enclosure
        const outside = flood(2371, 3623, [2290, 3515, 2440, 3660]);
        const near = (x: number, z: number) => [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dz]) => outside.has(`${x + dx},${z + dz}`));
        for (const [what, x, z] of [['common kebbit burrow', 2322, 3576], ['razor-backed kebbit burrow', 2353, 3595], ['fishing colony', 2340, 3650]] as [string, number, number][])
            check(near(x, z), `on foot from the stile to the ${what} (${x},${z})`);
        const unreach = ['hunter_copper_longtail', 'hunter_prickly_kebbit', 'hunter_ruby_harvest', 'hunter_wild_kebbit', 'hunter_chinchompa'].flatMap(npcsOf).filter(here)
            .filter(s => !outside.has(`${s.startX},${s.startZ}`)).map(s => `${NpcType.get(s.type).name}@${s.startX},${s.startZ}`);
        check(unreach.length === 0, `...and to every spawn of the open hunter area (${unreach.join(' ') || 'all'})`);
        // the fence: a walk from Matthias's spot, unbounded but for the map round it, never gets out; every
        // tile it reaches is inside ~falconry_in_area's rectangles; and none of the tiles a walk from outside
        // reaches is (the rectangles take in no ground outside the fence that anybody can stand on)
        const inside = flood(2374, 3604, [2290, 3515, 2440, 3660]);
        check(!inside.has('2371,3622') && !inside.has('2322,3576') && inside.size < 1000, `the enclosure is fenced: from Matthias's spot a walk stays inside (${inside.size} tiles)`);
        const out = [...inside].filter(k => { const [x, z] = k.split(',').map(Number); return !inArea(x, z); });
        check(out.length === 0, `...and every tile of it is inside ~falconry_in_area (${out.slice(0, 5).join(' ') || 'all'})`);
        const leak = [...outside].filter(k => { const [x, z] = k.split(',').map(Number); return inArea(x, z); });
        check(leak.length === 0, `...while no tile a walk from outside reaches is (${leak.slice(0, 5).join(' ') || 'none'})`);
        const fku = ['hunter_spotted_kebbit', 'hunter_dark_kebbit', 'hunter_dashing_kebbit'].flatMap(npcsOf).filter(s => !inside.has(`${s.startX},${s.startZ}`));
        check(fku.length === 0 && inside.has('2371,3619'), `inside, Matthias's tile reaches every falconry kebbit and the stile (${fku.map(s => `${s.startX},${s.startZ}`).join(' ') || 'all'})`);
        // no dead clicks on what was imported
        for (const n of ['loc474_19222', 'loc474_19492', 'loc474_19438', 'loc474_19429', 'loc474_19428', 'loc474_19339', 'loc474_19340', 'loc474_19341', 'loc474_19342', 'hunter_snare_caught_longtail', 'hunter_deadfall_prickly']) {
            const t = LocType.get(LocType.getId(n));
            const ops = (t.op ?? []).map((o: any, i: number) => [o, i] as [any, number]).filter(([o]) => o && o !== 'hidden');
            const dead = ops.filter(([, i]) => !ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1 + i, t.id, t.category));
            check(ops.length > 0 && dead.length === 0, `${n}: every op has a handler (${ops.map(([o]) => o).join(', ')})`);
        }
        for (const n of ['hunter_matthias', 'hunter_spotted_kebbit', 'hunter_dark_kebbit', 'hunter_dashing_kebbit', 'hunter_falcon_spotted', 'hunter_falcon_dark', 'hunter_falcon_dashing']) {
            const t = NpcType.get(NpcType.getId(n));
            const ops = (t.op ?? []).map((o: any, i: number) => [o, i] as [any, number]).filter(([o]) => o && o !== 'hidden');
            const dead = ops.filter(([, i]) => !ScriptProvider.getByTrigger(ServerTriggerType.OPNPC1 + i, t.id, t.category));
            check(ops.length > 0 && dead.length === 0, `${n}: every op has a handler (${ops.map(([o]) => o).join(', ')})`);
        }
        for (const n of ['loc474_19337', 'loc474_19220', 'loc474_19221']) check(!(LocType.get(LocType.getId(n)).op ?? []).some((o: any) => o), `${n} carries no op`);
        // the ruby harvest: a small fishing net used on one, and a jar to keep it in
        {
            const NET = ObjType.getId('net');
            player.invAdd(InvType.INV, NET, 1); player.invAdd(InvType.INV, ObjType.getId('hunter_butterfly_jar'), 1);
            let got = false, xp = 0;
            for (let tries = 0; tries < 20 && !got; tries++) {
                const b = nearest('hunter_ruby_harvest', 2320, 3600);
                if (!b) { await waitTicks(20); continue; }
                player.teleport(b.x, b.z - 1, 0); await waitTicks(1);
                const x0 = player.stats[PlayerStat.HUNTER];
                player.lastUseItem = NET; player.lastUseSlot = inv0.getItemIndex(NET);
                const t = NpcType.get(b.type); run(ServerTriggerType.OPNPCU, t.id, t.category, b); await waitTicks(5);
                if (tot('hunter_jar_ruby') > 0) { got = true; xp = player.stats[PlayerStat.HUNTER] - x0; }
            }
            check(got && tot('hunter_butterfly_jar') === 0, 'a ruby harvest netted into a jar');
            check(xp === pnum('hunter_ruby_xp'), `...${xp / 10} xp`);
            const id = ObjType.getId('hunter_jar_ruby'); player.lastItem = id; player.lastSlot = inv0.getItemIndex(id);
            run(ServerTriggerType.OPHELD1, id, ObjType.get(id).category); await waitTicks(2);
            check(tot('hunter_jar_ruby') === 0 && tot('hunter_butterfly_jar') === 1, '...and released, the jar comes back');
        }
    }

    if (MODE === 'pisc_track') {
        const op = async (opn: number, loc: any) => { player.teleport(loc.x, loc.z - 1, 0); await waitTicks(1); oploc(opn, loc); await waitTicks(3); };
        const dir = (fx: number, fz: number, tx: number, tz: number) => {
            const dx = tx - fx, dz = tz - fz, ax = Math.abs(dx), az = Math.abs(dz);
            const ns = dz > 0 ? 'north' : dz < 0 ? 'south' : '', ew = dx > 0 ? 'east' : dx < 0 ? 'west' : '';
            if (ax > az * 2) return ew; if (az > ax * 2) return ns; if (!ns) return ew; if (!ew) return ns; return `${ns}-${ew}`;
        };
        player.invAdd(InvType.INV, ObjType.getId('noose_wand'), 1);
        const GROUNDS = [
            { name: 'common', bx: 2322, bz: 3576, burrow: 'loc474_19492', level: pnum('hunter_common_kebbit_level'), prize: 'common_kebbit_fur', xp: pnum('hunter_common_kebbit_xp') },
            { name: 'razor', bx: 2353, bz: 3595, burrow: 'loc474_19438', level: pnum('hunter_razorback_kebbit_level'), prize: 'long_kebbit_spike', xp: pnum('hunter_razorback_kebbit_xp') }
        ];
        for (const G of GROUNDS) {
            const B = World.getLoc(G.bx, G.bz, 0, LocType.getId(G.burrow));
            check(B !== null, `${G.name}: the burrow at ${G.bx},${G.bz} is where the map put it`);
            if (!B) continue;
            const nodes = enumCoords(`hunter_pisc_${G.name}_nodes`), bushes = enumCoords(`hunter_pisc_${G.name}_bushes`);
            setLevel(G.level - 1);
            await op(1, B);
            check(v('hunter_track_next') === -1, `${G.name}: below Hunter ${G.level} a burrow gives no trail`);
            setLevel(LEVEL);
            if (LEVEL < G.level) continue;
            let caught = false, trails = 0, hintsOk = true, hints = 0, inGround = true;
            while (!caught && trails < 10) {
                trails++;
                let n = msgs.length;
                await op(1, B);
                let from = { x: B.x, z: B.z };
                for (let hop = 0; hop < 8; hop++) {
                    const next = xz(v('hunter_track_next')), bush = xz(v('hunter_track_bush'));
                    if (!bushes.some(b => b.x === bush.x && b.z === bush.z) || !(nodes.some(c => c.x === next.x && c.z === next.z) || (next.x === bush.x && next.z === bush.z))) inGround = false;
                    const said = msgs.slice(n).reverse().find(m => m.includes('tracks'));
                    hints++; if (!said || !said.includes(dir(from.x, from.z, next.x, next.z))) { hintsOk = false; log('hint mismatch', said, from, next); }
                    if (next.x === bush.x && next.z === bush.z) break;
                    const loc = nodeAt(next.x, next.z);
                    if (!loc) { check(false, `${G.name}: the trail's next step ${next.x},${next.z} has something to inspect`); break; }
                    if (hop === 0 && trails === 1) {
                        const other = nodes.map(c => nodeAt(c.x, c.z)).find(l => l && (l.x !== next.x || l.z !== next.z) && PLANTS.includes(l.type));
                        if (other) { const m0 = msgs.length; await op(1, other); check(msgs.slice(m0).some(m => m.includes('find no tracks')) && v('hunter_track_next') === ((next.x << 14) | next.z), `${G.name}: the wrong plant finds no tracks and keeps the trail`); }
                    }
                    n = msgs.length; await op(1, loc);
                    from = next;
                }
                const bush = xz(v('hunter_track_bush'));
                const bl = nodeAt(bush.x, bush.z);
                if (!bl) { check(false, `${G.name}: the trail ends at a bush (${bush.x},${bush.z})`); break; }
                if (trails === 1) { const n0 = msgs.length; await op(1, bl); check(msgs.slice(n0).some(m => m.includes('hiding in the bush')), `${G.name}: Search on the trail's bush finds the kebbit`); }
                const b = { bones: tot('bones'), prize: tot(G.prize), xp: player.stats[PlayerStat.HUNTER] };
                await op(2, bl); await waitTicks(4);
                if (tot(G.prize) > b.prize) {
                    caught = true;
                    check(tot('bones') === b.bones + 1, `${G.name}: caught - bones and ${G.prize}`);
                    check(player.stats[PlayerStat.HUNTER] - b.xp === G.xp, `${G.name}: ...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
                }
                check(v('hunter_track_next') === -1, `${G.name}: ...the trail is spent either way (trail ${trails})`);
            }
            check(caught, `${G.name}: a kebbit caught within 10 trails (${trails})`);
            check(hintsOk, `${G.name}: every hint named the real direction of the next step (${hints} hints)`);
            check(inGround, `${G.name}: every step and every bush was one of this ground's own`);
        }
    }

    if (MODE === 'pisc_traps') {
        const TYPES = ['hunter_snare_laid', 'hunter_snare_springing', 'hunter_snare_collapsed', 'hunter_snare_catching_longtail', 'hunter_snare_caught_longtail',
            'hunter_deadfall_set', 'hunter_deadfall_collapsed', 'hunter_deadfall_prickly', 'hunter_deadfall_wild',
            'hunter_boxtrap_laid', 'hunter_boxtrap_collapsed', 'hunter_boxtrap_catching_chinchompa', 'hunter_boxtrap_shaking_chinchompa'];
        const at = (x: number, z: number) => { for (const n of TYPES) { const l = World.getLoc(x, z, 0, LocType.getId(n)); if (l) return { name: n, loc: l }; } return null; };
        const slots = () => [1, 2, 3, 4, 5].map(i => player.getVar(VarPlayerType.getId(`hunter_trap${i}`)) as number).filter(c => c !== -1).map(xz);
        const max = Math.min(5, 1 + Math.floor(LEVEL / 20));
        const opheld = (n: string) => { const id = ObjType.getId(n); const s = inv0.getItemIndex(id); if (s === -1) return; player.lastItem = id; player.lastSlot = s; run(ServerTriggerType.OPHELD1, id, ObjType.get(id).category); };
        // take every trap up; one caught mid-spring (a state with no op of its own) is waited out
        const takeAll = async () => {
            for (let round = 0; round < 10 && slots().length; round++) {
                for (const c of slots()) {
                    const t = at(c.x, c.z);
                    if (!t || !ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1, t.loc.type, LocType.get(t.loc.type).category)) continue;
                    player.teleport(c.x, c.z - 1, 0); await waitTicks(1); oploc(1, t.loc); await waitTicks(3);
                }
                if (slots().length) await waitTicks(2);
            }
        };
        const watch = async (ticks: number, want: string[], collapsed: string[], reset: (x: number, z: number) => Promise<void>, home: number[]) => {
            for (let t = 0; t < ticks; t++) {
                await waitTicks(1);
                for (const c of slots()) {
                    const s = at(c.x, c.z)?.name;
                    if (s && want.includes(s)) return { ...c, s };
                    if (s && collapsed.includes(s)) { player.teleport(c.x, c.z - 1, 0); await waitTicks(1); oploc(1, at(c.x, c.z)!.loc); await waitTicks(3); await reset(c.x, c.z); player.teleport(home[0], home[1], 0); }
                }
            }
            return null;
        };
        // 1. snares among the copper longtails, east of the razor-backs' ground
        {
            const LT = pnum('hunter_longtail_level'), can = LEVEL >= LT;
            player.invAdd(InvType.INV, ObjType.getId('hunter_bird_snare'), 5);
            const lay = async (x: number, z: number) => { player.teleport(x, z, 0); await waitTicks(2); opheld('hunter_bird_snare'); await waitTicks(5); };
            const CAND = [[2361, 3589], [2363, 3589], [2359, 3589], [2361, 3591], [2363, 3587], [2356, 3586], [2354, 3585], [2358, 3587], [2360, 3587], [2362, 3585]].filter(([x, z]) => !isMapBlocked(x, z, 0));
            for (const [x, z] of CAND) if (slots().length < max) await lay(x, z);
            check(slots().length === max, `snares: ${max} laid among the copper longtails at level ${LEVEL} (${slots().length})`);
            player.teleport(2361, 3588, 0);
            const got = await watch(can ? 900 : 300, ['hunter_snare_caught_longtail'], ['hunter_snare_collapsed'], lay, [2361, 3588]);
            if (can) {
                check(got !== null, 'snares: a copper longtail caught off the loop within 900 ticks');
                if (got) {
                    const b = { bones: tot('bones'), meat: tot('raw_bird_meat'), fea: tot('orange_feather'), xp: player.stats[PlayerStat.HUNTER] };
                    player.teleport(got.x, got.z - 1, 0); await waitTicks(1); oploc(1, at(got.x, got.z)!.loc); await waitTicks(3);
                    check(tot('bones') === b.bones + 1 && tot('raw_bird_meat') === b.meat + 1 && tot('orange_feather') === b.fea + parseInt(/\^hunter_bird_feathers = (\d+)/.exec(CONST)![1]), '...Check pays bones, raw bird meat and orange feathers');
                    check(player.stats[PlayerStat.HUNTER] - b.xp === pnum('hunter_longtail_xp'), `...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
                }
            } else check(got === null, `snares: below Hunter ${LT}, no copper longtail comes (${got?.s ?? 'none'})`);
            await takeAll();
            check(slots().length === 0, 'snares: all taken up again');
        }
        // 2. deadfalls on the boulders among the prickly kebbits (the north)
        if (LEVEL >= 23) {
            const PK = pnum('hunter_prickly_kebbit_level'), can = LEVEL >= PK;
            player.invAdd(InvType.INV, ObjType.getId('knife'), 1); player.invAdd(InvType.INV, ObjType.getId('logs'), 15);
            const BOULDER = LocType.getId('loc474_19205');
            // four boulders within the leash of each other, among the northern prickly kebbits
            const B = [[2323, 3627], [2327, 3636], [2337, 3631], [2322, 3643]];
            check(B.every(([x, z]) => World.getLoc(x, z, 0, BOULDER) !== null), 'deadfalls: the boulders are where the map put them');
            const set = async (x: number, z: number) => { const b = World.getLoc(x, z, 0, BOULDER); if (!b) return; player.teleport(x, z - 1, 0); await waitTicks(2); oploc(1, b); await waitTicks(5); };
            for (const [x, z] of B) if (slots().length < max) await set(x, z);
            check(slots().length === Math.min(max, B.length), `deadfalls: ${Math.min(max, B.length)} set among the prickly kebbits (${slots().length})`);
            player.teleport(2328, 3634, 0);
            const got = await watch(can ? 900 : 300, ['hunter_deadfall_prickly', 'hunter_deadfall_wild'], ['hunter_deadfall_collapsed'], set, [2328, 3634]);
            if (can) {
                check(got?.s === 'hunter_deadfall_prickly', `deadfalls: a prickly kebbit caught within 900 ticks (${got?.s ?? 'none'})`);
                if (got?.s === 'hunter_deadfall_prickly') {
                    const b = { bones: tot('bones'), spike: tot('kebbit_spike'), xp: player.stats[PlayerStat.HUNTER] };
                    player.teleport(got.x, got.z - 1, 0); await waitTicks(1); oploc(1, at(got.x, got.z)!.loc); await waitTicks(3);
                    check(tot('bones') === b.bones + 1 && tot('kebbit_spike') === b.spike + 1, '...Check pays bones and a kebbit spike');
                    check(player.stats[PlayerStat.HUNTER] - b.xp === pnum('hunter_prickly_kebbit_xp'), `...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
                    check(World.getLoc(got.x, got.z, 0, BOULDER) !== null, '...and the boulder is a boulder again');
                }
            } else check(got === null, `deadfalls: below Hunter ${PK}, no prickly kebbit comes (${got?.s ?? 'none'})`);
            await takeAll();
        }
        // 3. box traps among the chinchompas in the south-east
        if (LEVEL >= 27) {
            const CH = parseInt(/\^hunter_chinchompa_level = (\d+)/.exec(CONST)![1]), can = LEVEL >= CH;
            player.invAdd(InvType.INV, ObjType.getId('hunter_box_trap'), 5);
            const lay = async (x: number, z: number) => { player.teleport(x, z, 0); await waitTicks(2); opheld('hunter_box_trap'); await waitTicks(5); };
            const CAND = [[2361, 3565], [2363, 3563], [2359, 3563], [2362, 3567], [2360, 3561], [2364, 3561], [2358, 3566], [2362, 3569]].filter(([x, z]) => !isMapBlocked(x, z, 0));
            for (const [x, z] of CAND) if (slots().length < max) await lay(x, z);
            check(slots().length === max, `box traps: ${max} laid among the chinchompas (${slots().length})`);
            player.teleport(2361, 3564, 0);
            const got = await watch(can ? 900 : 300, ['hunter_boxtrap_shaking_chinchompa'], [], lay, [2361, 3564]);
            if (can) check(got !== null, 'box traps: a chinchompa caught within 900 ticks');
            else check(got === null, `box traps: below Hunter ${CH}, no chinchompa comes`);
            await takeAll();
        }
    }

    if (MODE === 'falconry') {
        const GLOVE = ObjType.getId('falconers_glove'), GLOVEF = ObjType.getId('falconers_glove_falcon');
        const hand = () => worn.get(3)?.id ?? -1;
        const MATTHIAS = npcsOf('hunter_matthias')[0];
        check(MATTHIAS !== undefined, 'Matthias is in the world');
        const talk = async (picks: number[]) => { player.teleport(MATTHIAS.x, MATTHIAS.z - 1, 0); await waitTicks(1); opnpc(1, MATTHIAS); await converse(picks); };
        // the stile, without a glove: over and back
        const STILE = World.getLoc(2371, 3620, 0, LocType.getId('loc474_19222'));
        check(STILE !== null, 'the stile is in the north wall of the hut');
        player.teleport(2371, 3622, 0); await waitTicks(1); oploc(1, STILE); await waitTicks(5);
        check(player.x === 2371 && player.z === 3619, `the stile takes you in (${player.x},${player.z})`);
        oploc(1, STILE); await waitTicks(5);
        check(player.x === 2371 && player.z === 3622, `...and out again (${player.x},${player.z})`);
        // the hire: the gates first
        setLevel(pnum('falconry_level') - 1);
        await talk([2]);
        check(hand() === -1, `below Hunter ${pnum('falconry_level')} Matthias lends nothing`);
        setLevel(LEVEL);
        await talk([2, 1]);
        check(hand() === -1, 'no coins, no falcon');
        player.invAdd(InvType.INV, ObjType.getId('coins'), 1000);
        worn.set(3, { id: ObjType.getId('bronze_sword'), count: 1 });
        await talk([2, 1]);
        check(hand() === ObjType.getId('bronze_sword') && tot('coins') === 1000, 'a sword in hand: no glove, and no charge');
        worn.delete(3); player.invAdd(InvType.INV, ObjType.getId('bronze_sword'), 1);
        await talk([2, 1]);
        check(hand() === GLOVEF && tot('coins') === 500, `hired: the glove with the falcon on it, for 500 coins (${tot('coins')} left)`);
        await waitTicks(1);
        check(player.readyanim === SeqType.getId('osrs_seq_5160'), `...and you stand holding the bird up, as Matthias does (readyanim ${player.readyanim})`);
        // the glove stays on, and nothing goes on over it
        { const n = msgs.length; player.lastSlot = 3; player.lastItem = GLOVEF;
          run(ServerTriggerType.INV_BUTTON1, Component.getId('wornitems:worn'), -1); await waitTicks(2);
          check(hand() === GLOVEF && msgs.slice(n).some(m => m.includes('speak to Matthias')), 'the glove will not come off'); }
        { const n = msgs.length; const id = ObjType.getId('bronze_sword'); player.lastItem = id; player.lastSlot = inv0.getItemIndex(id);
          run(ServerTriggerType.OPHELD2, id, ObjType.get(id).category); await waitTicks(2);
          check(hand() === GLOVEF && tot('bronze_sword') === 1 && msgs.slice(n).some(m => m.includes('falconer')), 'nothing is wielded over it'); }
        // the stile will not let you out with it
        player.teleport(2371, 3619, 0); await waitTicks(1); oploc(1, STILE); await converse([]); await waitTicks(3);
        check(player.z === 3619 && hand() === GLOVEF, 'the stile will not let you leave with the glove on');
        // catching
        const K = [
            { npc: 'hunter_spotted_kebbit', falcon: 'hunter_falcon_spotted', fur: 'spotted_kebbit_fur', key: 'spotted_kebbit' },
            { npc: 'hunter_dark_kebbit', falcon: 'hunter_falcon_dark', fur: 'dark_kebbit_fur', key: 'dark_kebbit' },
            { npc: 'hunter_dashing_kebbit', falcon: 'hunter_falcon_dashing', fur: 'dashing_kebbit_fur', key: 'dashing_kebbit' }
        ];
        const liveFalcons = (name: string) => npcsOf(name).filter(f => f.isActive !== false);
        // walk up to it from inside the fence: a tile beside it that is open and in the enclosure (a teleport
        // outside it would, rightly, send the falcon home)
        const besideInside = (n: any) => { for (const [dx, dz] of [[0, -1], [0, 1], [-1, 0], [1, 0], [-1, -1], [1, 1], [-1, 1], [1, -1]]) if (inArea(n.x + dx, n.z + dz) && !isMapBlocked(n.x + dx, n.z + dz, 0)) return [n.x + dx, n.z + dz]; return [n.x, n.z]; };
        const send = async (k: any) => {
            const kb = nearest(k.npc, 2378, 3590);
            if (!kb) return null;
            // stand a few tiles off it, on an open tile: the falcon is sent from range
            let sx = kb.x, sz = kb.z;
            for (const [dx, dz] of [[4, 0], [-4, 0], [0, 4], [0, -4], [3, 3], [-3, -3], [3, -3], [-3, 3], [2, 0], [-2, 0]]) if (!isMapBlocked(kb.x + dx, kb.z + dz, 0) && inArea(kb.x + dx, kb.z + dz)) { sx = kb.x + dx; sz = kb.z + dz; break; }
            player.teleport(sx, sz, 0); await waitTicks(1);
            const was = { x: kb.x, z: kb.z }, dist = cheb(kb, sx, sz);
            opnpc(1, kb, true); await waitTicks(1);
            const flying = hand() === GLOVE;
            await waitTicks(8);
            return { kb, was, flying, dist };
        };
        let missSeen = false;
        for (const k of K) {
            const L = pnum(`hunter_${k.key}_level`);
            if (LEVEL < L) {
                await send(k); await converse([]);
                check(hand() === GLOVEF && liveFalcons(k.falcon).length === 0, `${k.npc}: below Hunter ${L} the falcon is not sent`);
                continue;
            }
            // keep sending until a catch - and, where the level makes a miss likely (below 57), a miss too
            let caught = false;
            const wantMiss = LEVEL < 57 && k === K[0];
            for (let tries = 0; tries < 40 && (!caught || (wantMiss && !missSeen)); tries++) {
                const n = msgs.length;
                const r = await send(k);
                if (!r) { await waitTicks(20); continue; }
                if (tries === 0) check(r.flying, `${k.npc}: sent from ${r.dist} tiles, the falcon leaves the glove`);
                const falcons = liveFalcons(k.falcon);
                if (falcons.length) {
                    const f = falcons[0];
                    if (caught) { { const [bx, bz] = besideInside(f); player.teleport(bx, bz, 0); } await waitTicks(1); opnpc(1, f); await waitTicks(3); continue; }
                    caught = true;
                    check(v('falconry_falcon') !== -1 && hand() === GLOVE, `${k.npc}: caught - a falcon sits on the kill and the glove is empty`);
                    // the kebbit runs on while she flies, so she comes down near where it was sent from, not on it
                    check(cheb(f, r.was.x, r.was.z) <= 6, `${k.npc}: ...where the kebbit ran to (${f.x},${f.z}; kebbit when she was sent: ${r.was.x},${r.was.z})`);
                    if (k === K[0]) {
                        const n2 = msgs.length; const other = nearest(k.npc, f.x, f.z);
                        if (other) { const [bx, bz] = besideInside(other); player.teleport(bx, bz, 0); await waitTicks(1); opnpc(1, other, true); await waitTicks(2); check(msgs.slice(n2).some(m => m.includes('still out')), '...and no second falcon while it is out'); }
                    }
                    const b = { bones: tot('bones'), fur: tot(k.fur), xp: player.stats[PlayerStat.HUNTER] };
                    { const [bx, bz] = besideInside(f); player.teleport(bx, bz, 0); } await waitTicks(1); opnpc(1, f); await waitTicks(3);
                    check(tot('bones') === b.bones + 1 && tot(k.fur) === b.fur + 1, `${k.npc}: Retrieve pays bones and ${k.fur}`);
                    check(player.stats[PlayerStat.HUNTER] - b.xp === pnum(`hunter_${k.key}_xp`), `${k.npc}: ...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
                    check(hand() === GLOVEF && v('falconry_falcon') === -1 && liveFalcons(k.falcon).length === 0, `${k.npc}: ...and the falcon is back on the glove`);
                } else if (msgs.slice(n).some(m => m.includes('just misses'))) {
                    if (!missSeen) { missSeen = true; check(hand() === GLOVEF, `a miss: the falcon comes back to the glove (${k.npc})`); }
                }
            }
            check(caught, `${k.npc}: caught within 40 sends`);
        }
        // at 50 a spotted kebbit is caught about two times in three, so a miss turns up; at 70 it may not
        if (LEVEL < 57) check(missSeen, 'a miss was seen, and the falcon came back to the glove');
        // a falcon left on its catch gives up
        let gaveUp = false;
        for (let tries = 0; tries < 20 && !gaveUp; tries++) {
            const r = await send(K[0]);
            if (!r || liveFalcons(K[0].falcon).length === 0) { await waitTicks(3); continue; }
            gaveUp = true;
            const n = msgs.length;
            await waitTicks(pnum('falconry_wait') + 6);
            check(msgs.slice(n).some(m => m.includes('left its prey')) && hand() === GLOVE && v('falconry_falcon') === -1 && liveFalcons(K[0].falcon).length === 0, 'left on its catch, the falcon gives up and flies home; the glove stays empty');
            const n2 = msgs.length; const r2 = nearest(K[0].npc, 2378, 3590);
            if (r2) { const [bx, bz] = besideInside(r2); player.teleport(bx, bz, 0); await waitTicks(1); opnpc(1, r2, true); await waitTicks(2); }
            check(msgs.slice(n2).some(m => m.includes('flown back to Matthias')), '...a kebbit cannot be caught with the empty glove');
            await talk([]);
            check(hand() === GLOVEF, '...and Matthias gives it back');
        }
        check(gaveUp, 'a falcon was left on a catch to see it give up');
        // a teleport out takes the glove off
        { const n = msgs.length; player.teleport(2335, 3578, 0); await waitTicks(6);
          check(hand() === -1 && msgs.slice(n).some(m => m.includes('flies back to him')), 'a teleport out of the enclosure sends the falcon home and the glove comes off'); }
        // hire again, and hand it back
        await talk([2, 1]);
        check(hand() === GLOVEF && tot('coins') === 0, 'hired again, for another 500');
        await talk([2]);
        check(hand() === -1, 'handed back to Matthias, the glove comes off');
        player.teleport(2371, 3619, 0); await waitTicks(1); oploc(1, STILE); await waitTicks(5);
        check(player.z === 3622, '...and the stile lets you out');
    }
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

// HTRAP=net, HAREA=canifis|uzer|ourania|boneyard: net traps on the area's young trees. Every tree is set
// and taken down once; both geometries (a tree facing north/east holds its sprung net on its own tile, one
// facing south/west on the net's) are sprung by hand and checked; then a real catch off the real loop,
// the cap, standing on the net, ownership, the leash, a fall-over, [logout] and Release.
if (process.env.HTRAP === 'net') {
    const AREA = process.env.HAREA ?? 'canifis';
    const A = ({
        canifis: { colour: 'swamp', npc: 'hunter_swamp_lizard', key: 'swamp_lizard', box: [3520, 3425, 3575, 3460], trees: 12, spawns: 12, start: [3547, 3442] },
        uzer: { colour: 'orange', npc: 'hunter_orange_salamander', key: 'orange_salamander', box: [3392, 3066, 3425, 3140], trees: 10, spawns: 11, start: [3408, 3088] },
        ourania: { colour: 'red', npc: 'hunter_red_salamander', key: 'red_salamander', box: [2440, 3212, 2485, 3256], trees: 12, spawns: 9, start: [2468, 3242] },
        boneyard: { colour: 'black', npc: 'hunter_black_salamander', key: 'black_salamander', box: [3285, 3655, 3325, 3685], trees: 4, spawns: 6, start: [3299, 3664] }
    } as any)[AREA];
    const cnum = (n: string) => parseInt(new RegExp(`\\^${n} = (-?\\d+)`).exec(CONST)![1]);
    const CLEVEL = cnum(`hunter_${A.key}_level`), CXP = cnum(`hunter_${A.key}_xp`), NETLEVEL = cnum('hunter_nettrap_level');
    const CAN_CATCH = LEVEL >= CLEVEL;
    const inv0 = player.getInventory(InvType.INV)!;
    const tot = (n: string) => inv0.getItemCount(ObjType.getId(n));
    const setLevel = (l: number) => { player.stats[PlayerStat.HUNTER] = getExpByLevel(l); player.baseLevels[PlayerStat.HUNTER] = l; player.levels[PlayerStat.HUNTER] = l; };
    const L = (n: string) => LocType.getId(n);
    const TREE = L(`hunter_young_tree_${A.colour}`), NET = L('hunter_nettrap_net'), GONE = L('hunter_nettrap_tree_gone');
    const ST: Record<string, number> = {};
    for (const s of ['bending', 'set', 'catching', 'caught', 'escaping', 'escaped']) ST[s] = L(`hunter_nettrap_${A.colour}_${s}`);
    const NAMES: [number, string][] = [[TREE, 'tree'], [NET, 'net'], [GONE, 'gone'], ...Object.entries(ST).map(([k, v]) => [v, k] as [number, string])];
    const at = (x: number, z: number) => { for (const [id, n] of NAMES) { const l = World.getLoc(x, z, 0, id); if (l) return { n, l }; } return null; };
    const DIR = [[0, 1], [1, 0], [0, -1], [-1, 0]];
    const { isMapBlocked, reachedLoc } = await import('#/engine/GameMap.js');
    const trees: any[] = [];
    for (let x = A.box[0]; x <= A.box[2]; x++) for (let z = A.box[1]; z <= A.box[3]; z++) {
        const l = World.getLoc(x, z, 0, TREE);
        if (l) trees.push({ x, z, a: l.angle, nx: x + DIR[l.angle][0], nz: z + DIR[l.angle][1] });
    }
    const state = (t: any) => `${at(t.x, t.z)?.n ?? '-'}/${at(t.nx, t.nz)?.n ?? '-'}`;
    const sprung = (t: any) => (t.a < 2 ? at(t.x, t.z) : at(t.nx, t.nz))!;
    const slots = () => [1, 2, 3, 4, 5].map(i => player.getVar(VarPlayerType.getId(`hunter_trap${i}`)) as number).filter(c => c !== -1);
    const oploc = (op: number, loc: any) => {
        const t = LocType.get(loc.type);
        const s = ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category);
        if (!s) { log('no script for op', op, t.debugname); return; }
        player.executeScript(ScriptRunner.init(s, player, loc), true);
    };
    const setTree = async (t: any) => { player.teleport(t.nx, t.nz, 0); await waitTicks(1); const l = World.getLoc(t.x, t.z, 0, TREE); if (l) oploc(1, l); await waitTicks(5); return state(t) === 'set/net'; };
    // straight into a sprung state, as the loop's own spring puts it there - checked at once, before the
    // owner's timer (every 2 ticks) moves a catching/escaping state on
    const spring = (t: any, s: string) => {
        const sc = ScriptProvider.getByName('[proc,hunter_net_spring]')!;
        player.executeScript(ScriptRunner.init(sc, player, null, [(t.x << 14) | t.z, t.a, ST[s]]), true);
    };
    const onGround = (x: number, z: number, n: string) => World.getObj(x, z, 0, ObjType.getId(n), player.hash64) !== null;
    const kit = () => {
        if (tot('net') < 5) player.invAdd(InvType.INV, ObjType.getId('net'), 5 - tot('net'));
        if (tot('rope') < 5) player.invAdd(InvType.INV, ObjType.getId('rope'), 5 - tot('rope'));
    };

    // ---- the map
    check(trees.length === A.trees, `${A.trees} ${A.colour} young trees on the map at ${AREA} (${trees.length})`);
    const netBlocked = trees.filter(t => isMapBlocked(t.nx, t.nz, 0));
    check(netBlocked.length === 0, `every tree's net tile is open ground (${netBlocked.map(t => `${t.nx},${t.nz}`).join(' ') || 'all'})`);
    const fa = LocType.get(TREE).forceapproach;
    const noReach = trees.filter(t => !reachedLoc(0, t.nx, t.nz, t.x, t.z, 1, 1, 1, t.a, 10, fa));
    check(noReach.length === 0, `...and it is the tile the tree is set from (${noReach.map(t => `${t.x},${t.z}`).join(' ') || 'all'})`);
    // and it joins the rest of the area: a walk (a flood fill over the engine's own collision, 40 tiles
    // round the area) from the landing tile of ::nettrap reaches every net tile
    const cut: string[] = [];
    {
        const { canTravel } = await import('#/engine/GameMap.js');
        const { CollisionType } = await import('#/engine/routefinder/index.js');
        const seenT = new Set<string>([`${A.start[0]},${A.start[1]}`]); const q = [[A.start[0], A.start[1]]];
        while (q.length) {
            const [x, z] = q.shift()!;
            for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
                const k = `${x + dx},${z + dz}`;
                if (seenT.has(k) || x + dx < A.box[0] - 40 || x + dx > A.box[2] + 40 || z + dz < A.box[1] - 40 || z + dz > A.box[3] + 40) continue;
                if (!canTravel(0, x, z, dx, dz, 1, 0, CollisionType.NORMAL)) continue;
                seenT.add(k); q.push([x + dx, z + dz]);
            }
        }
        for (const t of trees) if (!seenT.has(`${t.nx},${t.nz}`)) cut.push(`${t.x},${t.z}`);
    }
    check(cut.length === 0, `...and a player can walk from the ::nettrap landing tile to every one of them (${cut.join(' ') || 'all'})`);
    const NPC = NpcType.getId(A.npc);
    let spawns = 0;
    for (const n of World.npcs) if (n && n.type === NPC) spawns++;
    check(spawns === A.spawns, `${A.spawns} ${A.npc} in the world (${spawns})`);

    // ---- the gates
    kit();
    const T0 = trees.slice().sort((p, q) => Math.hypot(p.nx - A.start[0], p.nz - A.start[1]) - Math.hypot(q.nx - A.start[0], q.nz - A.start[1]));
    setLevel(NETLEVEL - 1);
    await setTree(T0[0]);
    check(slots().length === 0 && state(T0[0]) === 'tree/-' && tot('net') === 5, `below Hunter ${NETLEVEL} a young tree cannot be set`);
    setLevel(Math.max(LEVEL, NETLEVEL));
    inv0.remove(ObjType.getId('rope'), 5);
    { const n = msgs.length; await setTree(T0[0]); check(msgs.slice(n).some(m => m.includes('small fishing net and a rope')) && slots().length === 0 && state(T0[0]) === 'tree/-', 'no net trap without a rope'); }
    kit();

    // ---- every tree takes a trap, and gives it back (Dismantle from the net on some, the tree on others)
    let every = 0;
    for (const [i, t] of trees.entries()) {
        const ok = await setTree(t);
        const kinds = player.getVar(VarPlayerType.getId('hunter_trap_kinds')) as number;
        if (!ok || slots().length !== 1 || tot('net') !== 4 || tot('rope') !== 4 || (kinds & 7) !== 4 || ((kinds >> 15) & 3) !== t.a) { log('set failed', t, state(t), slots(), kinds); continue; }
        if (i === 0) { const n = msgs.length; oploc(2, at(t.nx, t.nz)!.l); await waitTicks(1); check(msgs.slice(n).some(m => m.includes('Nothing has run into it')), 'Investigate on the net: the trap is set'); }
        oploc(1, (i % 2 ? at(t.nx, t.nz) : at(t.x, t.z))!.l); await waitTicks(3);
        if (state(t) === 'tree/-' && slots().length === 0 && tot('net') === 5 && tot('rope') === 5) every++;
        else log('dismantle failed', t, state(t), slots(), tot('net'), tot('rope'));
    }
    check(every === trees.length, `every tree sets (bent, the net on its facing tile, one slot holding kind and angle, a net and a rope spent) and dismantles back (${every}/${trees.length})`);

    // ---- both geometries, sprung by hand: a catch and an escape on each
    const byAngle = [trees.find(t => t.a < 2), trees.find(t => t.a >= 2)].filter(Boolean);
    for (const t of byAngle) {
        const g = t.a < 2 ? 'facing north/east' : 'facing south/west';
        await setTree(t);
        spring(t, 'catching');
        check(state(t) === (t.a < 2 ? 'catching/-' : 'gone/catching'), `${g} (${t.x},${t.z}): sprung, the net hangs from the tree (${state(t)})`);
        await waitTicks(4);
        check(state(t) === (t.a < 2 ? 'caught/-' : 'gone/caught'), `...and the loop moves it on to caught (${state(t)})`);
        const b = { c: tot(A.key), n: tot('net'), r: tot('rope'), xp: player.stats[PlayerStat.HUNTER] };
        player.teleport(t.nx, t.nz, 0); await waitTicks(1);
        oploc(1, sprung(t).l); await waitTicks(3);
        check(tot(A.key) === b.c + 1 && tot('net') === b.n + 1 && tot('rope') === b.r + 1, `...Check pays the ${A.key} and gives the net and rope back`);
        check(player.stats[PlayerStat.HUNTER] - b.xp === CXP, `...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
        check(state(t) === 'tree/-' && slots().length === 0, `...and the young tree stands there again, the slot free (${state(t)})`);
        await setTree(t);
        spring(t, 'escaping'); await waitTicks(4);
        check(state(t) === (t.a < 2 ? 'escaped/-' : 'gone/escaped'), `${g}: an escape leaves the net empty (${state(t)})`);
        const e = { c: tot(A.key), n: tot('net'), r: tot('rope'), xp: player.stats[PlayerStat.HUNTER] };
        oploc(1, sprung(t).l); await waitTicks(3);
        check(tot(A.key) === e.c && tot('net') === e.n + 1 && tot('rope') === e.r + 1 && player.stats[PlayerStat.HUNTER] === e.xp && state(t) === 'tree/-', '...Dismantle gives the net and rope back, and nothing else');
    }

    // ---- somebody else's trap
    {
        const t = T0[0];
        await setTree(t);
        const c = slots()[0]; const vid = VarPlayerType.getId('hunter_trap1');
        const n = msgs.length;
        player.setVar(vid, -1); oploc(1, at(t.x, t.z)!.l); player.setVar(vid, c);
        await waitTicks(2);
        check(msgs.slice(n).some(m => m.includes("isn't your trap")) && state(t) === 'set/net', "a net trap not in your varps is not yours, and stays set");
        oploc(1, at(t.x, t.z)!.l); await waitTicks(3);
    }

    // ---- standing on the net: nothing is caught
    if (CAN_CATCH) {
        const t = T0[0];
        await setTree(t);
        player.teleport(t.nx, t.nz, 0);
        let near = 0, sprang = false;
        for (let i = 0; i < 150; i++) {
            await waitTicks(1);
            for (const n of World.npcs) if (n && n.type === NPC && Math.max(Math.abs(n.x - t.nx), Math.abs(n.z - t.nz)) <= 3) { near++; break; }
            if (state(t) !== 'set/net') sprang = true;
        }
        check(!sprang, `standing on the net for 150 ticks, nothing is caught (${near} of them with a ${A.npc} within 3 tiles)`);
        oploc(1, at(t.x, t.z)!.l); await waitTicks(3);
    }

    // ---- the real loop: as many traps as the level allows, the player standing off the nets
    const max = Math.min(5, 1 + Math.floor(Math.max(LEVEL, NETLEVEL) / 20));
    // trees all within the leash of one another - the Bone Yard's fourth tree is 24 tiles from its first,
    // and walking to it collapses the first trap, as it should
    const LEASH = cnum('hunter_trap_leash');
    const near: any[] = [];
    for (const t of T0) if (near.every(u => Math.max(Math.abs(t.nx - u.x), Math.abs(t.nz - u.z)) <= LEASH)) near.push(t);
    const used: any[] = [];
    for (const t of near) { if (used.length >= max) break; if (await setTree(t)) used.push(t); }
    check(used.length === Math.min(max, near.length) && slots().length === used.length, `${used.length} net traps set at level ${LEVEL} (cap ${max}; ${near.length} trees within the leash of each other)`);
    if (used.length < near.length) {
        const extra = near.find(t => !used.includes(t))!;
        const n = msgs.length; await setTree(extra);
        check(msgs.slice(n).some(m => m.includes('more than')) && state(extra) === 'tree/-', `a net trap over the cap of ${max} is refused`);
    }
    // an open tile off every net, near the first trap
    const nets = new Set(trees.map(t => `${t.nx},${t.nz}`)), treeTiles = new Set(trees.map(t => `${t.x},${t.z}`));
    let stand = [used[0].nx, used[0].nz];
    search: for (let r = 1; r < 5; r++) for (let dx = -r; dx <= r; dx++) for (let dz = -r; dz <= r; dz++) {
        const x = used[0].nx + dx, z = used[0].nz + dz;
        if (!nets.has(`${x},${z}`) && !treeTiles.has(`${x},${z}`) && !isMapBlocked(x, z, 0)) { stand = [x, z]; break search; }
    }
    player.teleport(stand[0], stand[1], 0); await waitTicks(1);
    let caught: any = null; const seen = new Map<string, string>();
    const LIMIT = CAN_CATCH ? 1500 : 300;
    for (let i = 0; i < LIMIT && !caught; i++) {
        await waitTicks(1);
        for (const t of used) {
            const s = state(t);
            if (seen.get(`${t.x},${t.z}`) !== s) { log('net trap', t.x, t.z, 'a', t.a, '->', s); seen.set(`${t.x},${t.z}`, s); }
            if (s.includes('caught')) { caught = t; break; }
            if (s.includes('escaped')) {
                const n0 = tot('net');
                player.teleport(t.nx, t.nz, 0); await waitTicks(1);
                oploc(1, sprung(t).l); await waitTicks(3);
                check(tot('net') === n0 + 1 && state(t) === 'tree/-', `an escaped net trap dismantles (${t.x},${t.z})`);
                await setTree(t);
                player.teleport(stand[0], stand[1], 0); await waitTicks(1);
            }
        }
    }
    if (CAN_CATCH) {
        check(caught !== null, `a ${A.npc} ran into a net trap within ${LIMIT} ticks`);
        if (caught) {
            const b = { c: tot(A.key), xp: player.stats[PlayerStat.HUNTER] };
            player.teleport(caught.nx, caught.nz, 0); await waitTicks(1);
            oploc(1, sprung(caught).l); await waitTicks(3);
            check(tot(A.key) === b.c + 1 && player.stats[PlayerStat.HUNTER] - b.xp === CXP && state(caught) === 'tree/-', `...Checked: a ${A.key} and ${CXP / 10} xp (a tree facing ${['north', 'east', 'south', 'west'][caught.a]})`);
            await setTree(caught);
        }
    } else {
        check([...seen.values()].every(s => !/catching|escaping|caught|escaped/.test(s)), `at level ${LEVEL}, below the ${A.npc}'s ${CLEVEL}, nothing runs into a net trap`);
        check(slots().length === 0 && used.every(t => state(t) === 'tree/-'), '...and traps left past their duration fall over: every tree stands up, every slot is free');
        check(used.every(t => onGround(t.nx, t.nz, 'net') && onGround(t.nx, t.nz, 'rope')) && msgs.some(m => m.includes('fallen over')), '...with the net and the rope on the ground where each net was');
        kit();
        for (const t of used) await setTree(t);
    }

    // ---- the leash
    {
        const held = used.filter(t => state(t) !== 'tree/-');
        player.teleport(stand[0], stand[1] + 30, 0);
        await waitTicks(6);
        check(held.length > 0 && slots().length === 0 && held.every(t => state(t) === 'tree/-'), `walking 30 tiles away collapses every net trap (${held.length}) and stands its tree up`);
        check(held.every(t => onGround(t.nx, t.nz, 'net') && onGround(t.nx, t.nz, 'rope')), '...leaving the net and rope on the ground');
    }

    // ---- [logout]
    {
        kit();
        const two = T0.slice(0, 2);
        for (const t of two) await setTree(t);
        const n = tot('net'), r = tot('rope'), held = slots().length;
        const lo = ScriptProvider.getByTrigger(ServerTriggerType.LOGOUT, -1, -1);
        player.executeScript(ScriptRunner.init(lo!, player), true); await waitTicks(2);
        check(held === 2 && slots().length === 0 && two.every(t => state(t) === 'tree/-'), '[logout] takes both net traps down and stands the trees up');
        check(tot('net') === n + 2 && tot('rope') === r + 2, '...and gives back both nets and both ropes');
    }

    // ---- Release
    {
        if (tot(A.key) === 0) player.invAdd(InvType.INV, ObjType.getId(A.key), 1);
        const c = tot(A.key), id = ObjType.getId(A.key);
        player.lastItem = id; player.lastSlot = inv0.getItemIndex(id);
        const s = ScriptProvider.getByTrigger(ServerTriggerType.OPHELD5, id, ObjType.get(id).category);
        player.executeScript(ScriptRunner.init(s!, player), true); await waitTicks(1);
        check(tot(A.key) === c - 1 && msgs.some(m => m.includes('scurries away')), `Release lets a ${A.key} go`);
    }
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

// HTRAP=imp: magic boxes among the imps north-east of Yanille (m40_48), where ::imps lands - the gate,
// laying, bait, Deactivate, standing on the box, a real catch off the real loop, Retrieve, the imp's
// respawn, the cap, the leash and [logout]; then the imp-in-a-box: Talk-to, an item used on it, its
// Bank interface, its own box, the Wilderness, and the deposit box and bank being left alone. Below
// Hunter 71 (HLEVEL=65) only the gate and the imp-in-a-box run.
// HTRAP=emporium: Aleck's Hunter Emporium in Yanille - the refit, Aleck and Leon, both shops and a
// purchase, the butterfly net, and the hunters' crossbow's level and ammunition.
if (process.env.HTRAP === 'imp' || process.env.HTRAP === 'emporium') {
    const { default: ScriptState } = await import('#/engine/script/ScriptState.js');
    const { isMapBlocked } = await import('#/engine/GameMap.js');
    const inv0 = player.getInventory(InvType.INV)!;
    const bank = player.getInventory(InvType.getId('bank'))!;
    const tot = (n: string) => inv0.getItemCount(ObjType.getId(n));
    const inBank = (n: string) => bank.getItemCount(ObjType.getId(n));
    const IMPCONST = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter_imps.constant`, 'utf8');
    const cnum = (n: string) => parseInt(new RegExp(`\\^${n} = (-?\\d+)`).exec(IMPCONST)![1]);
    const setStat = (s: number, l: number) => { player.stats[s] = getExpByLevel(l); player.baseLevels[s] = l; player.levels[s] = l; };
    const setLevel = (l: number) => setStat(PlayerStat.HUNTER, l);
    const v = (n: string) => player.getVar(VarPlayerType.getId(n)) as number;
    const slots = () => [1, 2, 3, 4, 5].map(i => v(`hunter_trap${i}`)).filter(c => c !== -1);
    // every if_settext the scripts send, so dialogue and titles can be read
    const texts: string[] = [];
    const w = player.write.bind(player);
    player.write = (m: any) => { if (m?.constructor?.name === 'IfSetText') texts.push(m.text); return w(m); };
    const run = (trigger: number, id: number, cat: number, target: any = null, args: any[] = []) => {
        const script = ScriptProvider.getByTrigger(trigger, id, cat);
        if (!script) { log('no script', trigger, id); return false; }
        player.executeScript(ScriptRunner.init(script, player, target, args), true);
        return true;
    };
    const opheld = (op: number, name: string) => {
        const id = ObjType.getId(name), slot = inv0.getItemIndex(id);
        if (slot === -1) { log('opheld: no', name); return false; }
        player.lastItem = id; player.lastSlot = slot;
        return run(ServerTriggerType.OPHELD1 + (op - 1), id, ObjType.get(id).category);
    };
    // [opheldu,<target>], as OpHeldUHandler finds it first
    const opheldu = (target: string, used: string) => {
        const t = ObjType.getId(target), u = ObjType.getId(used);
        player.lastItem = t; player.lastSlot = inv0.getItemIndex(t); player.lastUseItem = u; player.lastUseSlot = inv0.getItemIndex(u);
        const s = ScriptProvider.getByTriggerSpecific(ServerTriggerType.OPHELDU, t, -1);
        if (s) player.executeScript(ScriptRunner.init(s, player), true);
        return !!s;
    };
    const oploc = (op: number, loc: any) => { const t = LocType.get(loc.type); return run(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category, loc); };
    const oplocu = (loc: any, used: string) => {
        const u = ObjType.getId(used); player.lastUseItem = u; player.lastUseSlot = inv0.getItemIndex(u);
        const t = LocType.get(loc.type); return run(ServerTriggerType.OPLOCU, t.id, t.category, loc);
    };
    const opnpc = (op: number, npc: any) => { const t = NpcType.get(npc.type); return run(ServerTriggerType.OPNPC1 + (op - 1), t.id, t.category, npc); };
    const invButton = (op: number, com: string, slot: number) => {
        player.lastSlot = slot; player.lastItem = inv0.get(slot)?.id ?? -1;
        return run(ServerTriggerType.INV_BUTTON1 + (op - 1), Component.getId(com), -1);
    };
    // step a dialogue on: a Continue, or the given option of a multi
    const paused = () => player.activeScript?.execution === ScriptState.PAUSEBUTTON;
    const resume = async (com?: string) => {
        if (!paused()) return false;
        if (com) player.lastCom = Component.getId(com);
        player.executeScript(player.activeScript, true, true); await waitTicks(1); return true;
    };
    const talkThrough = async () => { let n = 0; while (paused() && n++ < 20) await resume(); };
    const proc = (name: string, args: any[]) => {
        const st = ScriptRunner.init(ScriptProvider.getByName(`[proc,${name}]`)!, player, null, args);
        ScriptRunner.execute(st); return st.popInt();
    };

    if (process.env.HTRAP === 'emporium') {
        // ---- the building
        const L = (n: string) => LocType.getId(n);
        const locAtXZ = (x: number, z: number, n: string) => World.getLoc(x, z, 0, L(n));
        check(locAtXZ(2567, 3081, 'hunter_emporium_counter') !== null, "the Emporium's counter at 2567,3081 (OSRS's)");
        // the shelves have no name and no op, so the server keeps no loc for them - they are read off the map
        const JM2 = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/maps/m40_48.jm2`, 'utf8');
        const onMap = (lx: number, lz: number, n: string) => new RegExp(`^0 ${lx} ${lz}: ${L(n)} 4\\b`, 'm').test(JM2);
        check(onMap(4, 9, 'hunter_emporium_shelf') && onMap(4, 11, 'hunter_emporium_shelf') && onMap(7, 7, 'hunter_emporium_shelf_jars') && onMap(7, 13, 'hunter_emporium_shelf_snare'), '...and its shelves of Hunter gear on the walls (m40_48)');
        check(locAtXZ(2568, 3085, 'grandfatherclock') === null && locAtXZ(2566, 3082, 'greenrugmiddle') === null && locAtXZ(2568, 3082, 'bigtable2') === null, "...and none of the house's old furniture");
        const ALECK = NpcType.getId('aleck'), LEON = NpcType.getId('leon');
        const find = (t: number) => { for (const n of World.npcs) if (n && n.type === t) return n; return null; };
        const aleck = find(ALECK), leon = find(LEON);
        check(aleck !== null && Math.max(Math.abs(aleck.x - 2567), Math.abs(aleck.z - 3083)) <= 1, `Aleck is in the shop, at 2567,3083 (${aleck?.x},${aleck?.z})`);
        check(leon !== null && Math.max(Math.abs(leon.x - 2565), Math.abs(leon.z - 3084)) <= 1, `Leon is in the shop too (${leon?.x},${leon?.z})`);
        const openNext = (n: any) => [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dz]) => !isMapBlocked(n.x + dx, n.z + dz, 0));
        check(!!aleck && !!leon && openNext(aleck) && openNext(leon), '...each with open ground beside them');
        player.teleport(2565, 3082, 0); await waitTicks(2);
        player.invAdd(InvType.INV, ObjType.getId('coins'), 5000);
        // ---- Aleck: Talk-to, the three answers, the shop
        texts.length = 0;
        opnpc(1, aleck); await waitTicks(1);
        check(paused() && texts.some(t => t.includes('Hunter Emporium')), 'Aleck: Talk-to greets you to the Emporium');
        await resume();
        check(texts.includes("Who's that guy over there?"), '...and offers the three answers');
        await resume('multi3:com_3'); await talkThrough();
        check(texts.some(t => t.includes('Leon')), '..."Who\'s that guy?" is Leon');
        texts.length = 0; opnpc(1, aleck); await waitTicks(1); await resume(); await resume('multi3:com_1'); await talkThrough();
        const SHOP = InvType.getId('hunter_aleck_shop');
        check(v('shop') === SHOP && player.modalMain === Component.getId('shop_template') && texts.includes("Aleck's Hunter Emporium"), '..."let\'s see what you\'ve got" opens Aleck\'s Hunter Emporium');
        player.closeModal(); await waitTicks(1);
        opnpc(5, aleck); await waitTicks(1);
        check(v('shop') === SHOP && player.modalMain === Component.getId('shop_template'), 'Trade (op5) opens it straight away');
        const shop = World.getInventory(SHOP)!;
        const STOCK: [string, number][] = [['butterfly_net', 5], ['hunter_butterfly_jar', 100], ['magic_box', 30], ['noose_wand', 50], ['hunter_bird_snare', 50], ['hunter_box_trap', 25], ['teasing_stick', 5], ['torch_unlit', 20]];
        const bad = STOCK.filter(([n, c]) => shop.getItemCount(ObjType.getId(n)) !== c);
        check(bad.length === 0, `...stocked as OSRS's: ${STOCK.map(([n, c]) => `${c} ${n}`).join(', ')}${bad.length ? ' - wrong: ' + bad.join(' ') : ''}`);
        // buy one magic box: 600 at 120% is 720 coins
        {
            const c0 = tot('coins'), b0 = tot('magic_box');
            player.lastSlot = shop.getItemIndex(ObjType.getId('magic_box')); player.lastItem = ObjType.getId('magic_box');
            run(ServerTriggerType.INV_BUTTON2, Component.getId('shop_template:inv'), -1); await waitTicks(2);
            check(tot('magic_box') === b0 + 1 && c0 - tot('coins') === 720, `Buy 1 magic box: one in the pack for ${c0 - tot('coins')} coins (OSRS 720)`);
        }
        player.closeModal(); await waitTicks(1);
        // ---- Leon
        texts.length = 0;
        opnpc(3, leon); await waitTicks(1);
        const LSHOP = InvType.getId('hunter_leon_shop');
        check(v('shop') === LSHOP && World.getInventory(LSHOP)!.getItemCount(ObjType.getId('hunters_crossbow')) === 2 && texts.includes("Leon's Prototype Crossbow"), "Leon's Trade opens Leon's Prototype Crossbow: two hunters' crossbows");
        player.closeModal(); await waitTicks(1);
        texts.length = 0; opnpc(4, leon); await waitTicks(1); await talkThrough();
        check(texts.some(t => t.includes('kebbit')) && texts.some(t => t.includes('20 coins')) && texts.some(t => t.includes('40 coins')), 'Ammo: Leon names his price - a spike and 20 coins, a long spike and 40');
        // with spikes: every spike you can pay for, six bolts each (20 coins a kebbit spike)
        player.invAdd(InvType.INV, ObjType.getId('kebbit_spike'), 3);
        player.invDel(InvType.INV, ObjType.getId('coins'), tot('coins'));
        player.invAdd(InvType.INV, ObjType.getId('coins'), 50);
        texts.length = 0; opnpc(4, leon); await waitTicks(1); await resume(); await resume('multi2:com_1'); await talkThrough();
        check(tot('kebbit_bolts') === 12 && tot('kebbit_spike') === 1 && tot('coins') === 10, `Ammo with 3 spikes and 50 coins: two spikes made into 12 kebbit bolts for 40 coins, the third waiting for the money (${tot('kebbit_bolts')} bolts, ${tot('kebbit_spike')} spike, ${tot('coins')} coins)`);
        texts.length = 0; opnpc(1, leon); await waitTicks(1); await resume(); await resume('multi3:com_1'); await talkThrough();
        check(v('shop') === LSHOP && player.modalMain === Component.getId('shop_template'), 'Talk-to, "What are you selling?", opens his shop');
        player.closeModal(); await waitTicks(1);
        // ---- the hunters' crossbow: Ranged 50, and kebbit bolts only
        {
            const worn = player.getInventory(InvType.WORN)!;
            const xb = ObjType.getId('hunters_crossbow');
            player.invAdd(InvType.INV, xb, 1);
            setStat(4, 49); opheld(2, 'hunters_crossbow'); await waitTicks(2);
            check(worn.getItemCount(xb) === 0 && tot('hunters_crossbow') === 1, "Ranged 49: the hunters' crossbow will not wield");
            setStat(4, 50); opheld(2, 'hunters_crossbow'); await waitTicks(2);
            check(worn.getItemCount(xb) === 1, '...Ranged 50: it does');
            const ok = (wp: string, a: string) => proc('hunter_crossbow_ammo_ok', [ObjType.getId(wp), ObjType.getId(a)]) === 1;
            check(ok('hunters_crossbow', 'kebbit_bolts') && ok('hunters_crossbow', 'long_kebbit_bolts'), '...it fires kebbit bolts and long kebbit bolts');
            check(!ok('hunters_crossbow', 'bolt') && !ok('hunters_crossbow', 'mithril_bolts'), '...and no other bolts');
            check(!ok('rune_crossbow', 'kebbit_bolts') && ok('rune_crossbow', 'mithril_bolts'), '...and kebbit bolts fire from nothing else');
            // through the real check the combat code makes
            for (const [a, want] of [['bolt', false], ['kebbit_bolts', true]] as [string, boolean][]) {
                worn.set(13, { id: ObjType.getId(a), count: 50 });
                const r = proc('player_ranged_check_ammo', [xb]);
                check((r === ObjType.getId(a)) === want, `~player_ranged_check_ammo, hunters' crossbow with ${a} in the quiver: ${want ? 'fires' : 'refused'}`);
            }
            worn.removeAll();
        }
        // ---- the butterfly net: used on a butterfly, as the small fishing net is
        {
            const BF = ['butterfly', 'butterfly2'].map(n => NpcType.getId(n));
            const pick = () => { for (const n of World.npcs) if (n && n.isActive && BF.includes(n.type)) return n; return null; };
            let bf: any = pick();
            check(bf !== null, 'a butterfly to net');
            player.invAdd(InvType.INV, ObjType.getId('butterfly_net'), 1);
            setLevel(99);
            const xp0 = player.stats[PlayerStat.HUNTER];
            let tries = 0;
            while (player.stats[PlayerStat.HUNTER] === xp0 && tries++ < 12 && (bf = pick())) {
                player.teleport(bf.x + 1, bf.z, bf.level); await waitTicks(1);
                player.lastUseItem = ObjType.getId('butterfly_net'); player.lastUseSlot = inv0.getItemIndex(player.lastUseItem);
                const t = NpcType.get(bf.type); run(ServerTriggerType.OPNPCU, t.id, t.category, bf); await waitTicks(4);
            }
            check(player.stats[PlayerStat.HUNTER] > xp0, `a butterfly net catches a butterfly (${tries} swing(s), +${(player.stats[PlayerStat.HUNTER] - xp0) / 10} xp)`);
        }
        console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
        process.exit(fails ? 1 : 0);
    }

    // ================================================================ HTRAP=imp
    const BOXLEVEL = cnum('hunter_magicbox_level'), IMPXP = cnum('hunter_imp_xp');
    const ST: [string, number][] = ['laid', 'failed', 'catching', 'caught'].map(s => [s, LocType.getId(`hunter_magicbox_${s}`)]);
    const boxAt = (x: number, z: number) => { for (const [s, id] of ST) { const l = World.getLoc(x, z, 0, id); if (l) return { s, l }; } return null; };
    const IMP = NpcType.getId('imp');
    const START = [2610, 3124];
    const imps = (r = 40) => { const o: any[] = []; for (const n of World.npcs) if (n && n.isActive && n.type === IMP && Math.max(Math.abs(n.x - START[0]), Math.abs(n.z - START[1])) <= r) o.push(n); return o; };
    // an imp within 2 tiles of (x,z): the nearest one is brought over if none has wandered there - the
    // imps here roam 27 tiles and teleport themselves, so the loop is watched with one kept in reach
    const keepImpNear = (x: number, z: number) => {
        const all = imps(60);
        if (all.some(n => Math.max(Math.abs(n.x - x), Math.abs(n.z - z)) <= 2)) return;
        if (!all.length) return;
        const spots = [[x + 2, z], [x - 2, z], [x, z + 2], [x, z - 2], [x + 1, z + 1]].filter(([a, b]) => !isMapBlocked(a, b, 0) && !(a === player.x && b === player.z));
        if (spots.length) all[0].teleport(spots[0][0], spots[0][1], 0);
    };
    const kinds = () => v('hunter_trap_kinds');

    check(!isMapBlocked(START[0], START[1], 0), `::imps lands on open ground (${START})`);
    const n0 = imps().length;
    check(n0 >= 6, `imps roam round it (${n0} within 40 tiles)`);
    {
        const s = ScriptProvider.getByName('[debugproc,imps]')!;
        player.executeScript(ScriptRunner.init(s, player), true); await waitTicks(2);
        check(tot('magic_box') === 5 && ['black_bead', 'red_bead', 'white_bead', 'yellow_bead'].every(b => tot(b) === 1) && player.x === START[0] && player.z === START[1],
            '::imps: five magic boxes, a bead of each colour, and there');
    }
    check(!ObjType.get(ObjType.getId('magic_box')).stackable, 'a magic box does not stack (2006; OSRS made it stack in 2025)');

    // laying steps you off the box afterwards (~push_player), so every lay starts from its own tile
    const layAt = async (x: number, z: number) => { player.teleport(x, z, 0); await waitTicks(1); opheld(1, 'magic_box'); await waitTicks(5); };

    // ---- the gate
    const GATE = Math.min(LEVEL, BOXLEVEL - 1);
    setLevel(GATE);
    { texts.length = 0; opheld(1, 'magic_box'); await waitTicks(4);
      check(slots().length === 0 && tot('magic_box') === 5 && texts.some(m => m.includes(`Hunter level of ${BOXLEVEL}`)), `Hunter ${GATE}: a magic box cannot be laid`);
      await talkThrough(); }
    setLevel(LEVEL);

    if (LEVEL >= BOXLEVEL) {
        // ---- one box: kind 7, Investigate, bait, Deactivate
        await layAt(START[0], START[1]);
        const b = boxAt(START[0], START[1]);
        check(b?.s === 'laid' && slots().length === 1 && (kinds() & 7) === 7 && tot('magic_box') === 4, `Activate lays the box at your feet: trap kind ${kinds() & 7}, one slot, one box spent`);
        { const n = msgs.length; oploc(2, b!.l); await waitTicks(1); check(msgs.slice(n).some(m => m.includes('Nothing has wandered')), 'Investigate: nothing in it yet'); }
        oplocu(b!.l, 'red_bead'); await waitTicks(1);
        check((v('hunter_imp_bait') & 1) === 1 && tot('red_bead') === 0, 'a red bead baits it (the bead is used)');
        { const n = msgs.length; oplocu(b!.l, 'black_bead'); await waitTicks(1);
          check(tot('black_bead') === 1 && msgs.slice(n).some(m => m.includes('already baited')), '...once'); }
        { const n = msgs.length; oplocu(b!.l, 'magic_box'); await waitTicks(1); check(tot('magic_box') === 4 && msgs.slice(n).some(m => m.includes('Nothing interesting')), '...and only with a bead'); }
        oploc(1, b!.l); await waitTicks(3);
        check(boxAt(START[0], START[1]) === null && slots().length === 0 && tot('magic_box') === 5, 'Deactivate takes it up and gives the box back');
        await layAt(START[0], START[1]);
        check(v('hunter_imp_bait') === 0 && boxAt(START[0], START[1])?.s === 'laid', 'laying a box again leaves no bait over from the last one');

        // ---- standing on the box: nothing goes in
        {
            let near = 0, sprang = false;
            player.teleport(START[0], START[1], 0);
            for (let i = 0; i < 150; i++) {
                keepImpNear(START[0], START[1]); await waitTicks(1);
                if (imps(60).some(n => Math.max(Math.abs(n.x - START[0]), Math.abs(n.z - START[1])) <= 3)) near++;
                if (boxAt(START[0], START[1])?.s !== 'laid') sprang = true;
            }
            check(!sprang && near > 100, `standing on the box for 150 ticks, no imp goes in (one within 3 tiles for ${near} of them)`);
        }

        // ---- the real loop, one tile off: a catch
        const OFF = [START[0] - 1, START[1]];
        player.teleport(OFF[0], OFF[1], 0);
        let caught = false, failed = 0; const seen: string[] = [];
        const gone = () => { const o: any[] = []; for (const n of World.npcs) if (n && n.type === IMP && !n.isActive) o.push(n); return o; };
        const gone0 = gone().length; let taken: any[] = [];
        for (let i = 0; i < 1500 && !caught; i++) {
            keepImpNear(START[0], START[1]);
            await waitTicks(1);
            const s = boxAt(START[0], START[1])?.s ?? '-';
            if (seen[seen.length - 1] !== s) { seen.push(s); log('magic box ->', s); }
            if (s === 'failed') {
                failed++;
                const m0 = tot('magic_box');
                oploc(1, boxAt(START[0], START[1])!.l); await waitTicks(3);
                check(tot('magic_box') === m0 + 1 && boxAt(START[0], START[1]) === null, 'an imp got away: Deactivate on the failed box gives it back');
                await layAt(START[0], START[1]); player.teleport(OFF[0], OFF[1], 0);
            }
            if (s === 'catching' && !taken.length) taken = gone().filter(n => Math.max(Math.abs(n.x - START[0]), Math.abs(n.z - START[1])) <= 3);
            if (s === 'caught') caught = true;
        }
        check(caught, `an imp went into the box within 1500 ticks (${failed} got away first; ${seen.join(' -> ')})`);
        check(seen.includes('catching'), '...through the catching state, the loop then moving it on to caught');
        if (caught) {
            const x0 = player.stats[PlayerStat.HUNTER], m0 = tot('magic_box'), held = slots().length;
            const n = msgs.length;
            oploc(1, boxAt(START[0], START[1])!.l); await waitTicks(3);
            check(tot('imp_box_2') === 1 && tot('magic_box') === m0 && boxAt(START[0], START[1]) === null && slots().length === held - 1,
                'Retrieve: an Imp-in-a-box(2) - the box itself, not the box back as well - and the slot is free');
            check(player.stats[PlayerStat.HUNTER] - x0 === IMPXP && msgs.slice(n).some(m => m.includes('caught an imp')), `...and ${IMPXP / 10} xp`);
        }
        // the caught imp was npc_del'd, not killed, and respawns: Imp Catcher's imps are all still there
        {
            check(taken.length === 1 && gone().length === gone0 + 1, `the imp that went in left the world as the box closed (${taken.length} beside the box, ${gone0} -> ${gone().length} gone)`);
            let back = false, t = 0;
            for (; t < 400 && !back; t++) { await waitTicks(1); if (taken.length && taken[0].isActive) back = true; }
            check(back, `...and respawned where it lives, ${t} ticks later (${taken[0]?.x},${taken[0]?.z})`);
        }

        // ---- the cap, the leash, [logout]
        const max = Math.min(5, 1 + Math.floor(LEVEL / 20));
        const TILES = [[0, 0], [2, 0], [-2, 0], [0, 2], [0, -2], [2, 2], [-2, -2], [2, -2], [-2, 2]].map(([a, c]) => [START[0] + a, START[1] + c]).filter(([a, c]) => !isMapBlocked(a, c, 0));
        if (tot('magic_box') < 5) player.invAdd(InvType.INV, ObjType.getId('magic_box'), 5 - tot('magic_box'));
        const laid: number[][] = [];
        for (const [x, z] of TILES) {
            if (slots().length >= max) break;
            if (boxAt(x, z)) { laid.push([x, z]); continue; }
            await layAt(x, z);
            if (boxAt(x, z)) laid.push([x, z]);
        }
        check(slots().length === max, `${max} boxes laid at level ${LEVEL}`);
        { const extra = TILES.find(t => !laid.some(l => l[0] === t[0] && l[1] === t[1]))!;
          const n = msgs.length; player.teleport(extra[0], extra[1], 0); await waitTicks(1); opheld(1, 'magic_box'); await waitTicks(5);
          check(msgs.slice(n).some(m => m.includes('more than')) && boxAt(extra[0], extra[1]) === null, `...and a box over the cap of ${max} is refused`); }
        player.teleport(START[0], START[1] + 30, 0); await waitTicks(6);
        check(slots().length === 0 && laid.every(([x, z]) => boxAt(x, z) === null), 'walking 30 tiles off collapses every box');
        const onGround = laid.filter(([x, z]) => World.getObj(x, z, 0, ObjType.getId('magic_box'), player.hash64) !== null).length;
        check(onGround === laid.length, `...and leaves each magic box on the ground where it stood (${onGround}/${laid.length})`);
        if (tot('magic_box') < 5) player.invAdd(InvType.INV, ObjType.getId('magic_box'), 5 - tot('magic_box'));
        const two = TILES.slice(0, 2);
        for (const [x, z] of two) await layAt(x, z);
        { const m0 = tot('magic_box'), held = slots().length;
          const lo = ScriptProvider.getByTrigger(ServerTriggerType.LOGOUT, -1, -1);
          player.executeScript(ScriptRunner.init(lo!, player), true); await waitTicks(2);
          check(held === 2 && slots().length === 0 && tot('magic_box') === m0 + 2 && two.every(([x, z]) => boxAt(x, z) === null), '[logout] takes both boxes up and gives them back'); }
    }

    // ---- the imp-in-a-box
    player.teleport(START[0], START[1], 0); await waitTicks(1);
    if (tot('imp_box_2') === 0) player.invAdd(InvType.INV, ObjType.getId('imp_box_2'), 1);
    texts.length = 0;
    opheld(1, 'imp_box_2'); await waitTicks(1);
    check(paused() && texts.includes('Imp'), 'Talk-to: the imp speaks (a chathead named Imp)');
    await resume(); await resume('multi2:com_1'); await talkThrough();
    check(texts.some(t => t.includes('your bank')), '..."What can you do for me?" - it offers to bank for you');
    // an item used on it
    player.invAdd(InvType.INV, ObjType.getId('logs'), 1);
    { const n = msgs.length; const had = inBank('logs');
      check(opheldu('imp_box_2', 'logs'), '[opheldu,imp_box_2] exists'); await waitTicks(2);
      check(tot('logs') === 0 && inBank('logs') === had + 1, 'logs used on an Imp-in-a-box(2) go to the bank');
      check(tot('imp_box_2') === 0 && tot('imp_box_1') === 1 && msgs.slice(n).some(m => m.includes('teleports away')), '...and it is an Imp-in-a-box(1)'); }
    // the Bank op: the deposit box, the imp's
    texts.length = 0;
    opheld(2, 'imp_box_1'); await waitTicks(1);
    check(player.modalMain === Component.getId('inter_95') && v('hunter_imp_bank') === 1 && texts.some(t => t.startsWith('Imp-in-a-box')), 'Bank opens the deposit box interface, titled for the imp');
    player.invAdd(InvType.INV, ObjType.getId('coins'), 777);
    { const cb = inBank('coins'), m0 = tot('magic_box');
      invButton(1, 'inter_95:com_62', inv0.getItemIndex(ObjType.getId('coins'))); await waitTicks(2);
      check(tot('coins') === 0 && inBank('coins') === cb + 777, 'clicking a stack there banks the whole stack (777 coins)');
      check(tot('imp_box_1') === 0 && tot('magic_box') === m0 + 1 && player.modalMain === -1 && msgs.some(m => m.includes('does not come back')), '...the second charge: the imp is gone, the box is a magic box again, and the interface shuts'); }
    // its own box, and the Wilderness
    player.invAdd(InvType.INV, ObjType.getId('imp_box_2'), 1);
    opheld(2, 'imp_box_2'); await waitTicks(1);
    { const n = msgs.length; invButton(1, 'inter_95:com_62', inv0.getItemIndex(ObjType.getId('imp_box_2'))); await waitTicks(2);
      check(tot('imp_box_2') === 1 && msgs.slice(n).some(m => m.includes('its own box')), "the imp won't bank its own box"); }
    player.closeModal(); await waitTicks(1);
    player.teleport(3200, 3810, 0); await waitTicks(2);
    { const n = msgs.length; opheld(2, 'imp_box_2'); await waitTicks(1);
      player.invAdd(InvType.INV, ObjType.getId('logs'), 1); opheldu('imp_box_2', 'logs'); await waitTicks(2);
      check(player.modalMain === -1 && tot('logs') === 1 && tot('imp_box_2') === 1 && msgs.slice(n).filter(m => m.includes('this deep in the Wilderness')).length === 2, 'deep in the Wilderness (level 37): no Bank, and nothing used on it is banked'); }
    player.teleport(START[0], START[1], 0); await waitTicks(2);
    // a real deposit box takes the interface back; the bank's own deposit side never looks at the flag
    player.setVar(VarPlayerType.getId('hunter_imp_bank'), 1);
    texts.length = 0;
    run(ServerTriggerType.OPLOC1, LocType.getId('loc_9398'), -1); await waitTicks(1);
    check(v('hunter_imp_bank') === 0 && texts.includes('The Bank of Gielinor - Deposit Box'), "a real deposit box clears the imp's flag and puts its own title back");
    player.closeModal(); await waitTicks(1);
    player.setVar(VarPlayerType.getId('hunter_imp_bank'), 1);
    { const lb = inBank('logs'), ib = tot('imp_box_2');
      player.lastSlot = inv0.getItemIndex(ObjType.getId('logs')); player.lastItem = ObjType.getId('logs');
      run(ServerTriggerType.INV_BUTTON2, Component.getId('bank_side:inv'), -1); await waitTicks(2);
      check(inBank('logs') === lb + 1 && tot('imp_box_2') === ib, "the bank's own deposit ignores it: the logs go in and no imp charge is spent"); }
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

// HTRAP=tracking: Feldip weasel trails from the burrow at 2525,2889, followed to the bush.
if (process.env.HTRAP === 'tracking') {
    const inv0 = player.getInventory(InvType.INV)!;
    const tot = (n: string) => inv0.getItemCount(ObjType.getId(n));
    const NODE_TYPES = [...Array.from({ length: 15 }, (_, i) => `loc474_${19403 + i}`), 'loc474_19593', 'loc474_19594'].map(n => LocType.getId(n));
    const BUSH = LocType.getId('loc474_19427');
    const locAtXZ = (x: number, z: number) => { for (const t of [...NODE_TYPES, BUSH]) { const l = World.getLoc(x, z, 0, t); if (l) return l; } return null; };
    const v = (n: string) => player.getVar(VarPlayerType.getId(n)) as number;
    const xz = (c: number) => ({ x: (c >> 14) & 0x3fff, z: c & 0x3fff });
    const op = async (opn: number, loc: any) => {
        player.teleport(loc.x, loc.z - 1, 0); await waitTicks(1);
        const t = LocType.get(loc.type);
        const script = ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1 + (opn - 1), t.id, t.category);
        player.executeScript(ScriptRunner.init(script!, player, loc), true);
        await waitTicks(3);
    };
    // the same compass the script uses, to check each hint against the real bearing
    const dir = (fx: number, fz: number, tx: number, tz: number) => {
        const dx = tx - fx, dz = tz - fz, ax = Math.abs(dx), az = Math.abs(dz);
        const ns = dz > 0 ? 'north' : dz < 0 ? 'south' : '', ew = dx > 0 ? 'east' : dx < 0 ? 'west' : '';
        if (ax > az * 2) return ew; if (az > ax * 2) return ns; if (!ns) return ew; if (!ew) return ns; return `${ns}-${ew}`;
    };
    const BURROW = World.getLoc(2525, 2889, 0, LocType.getId('loc474_19594')) ?? World.getLoc(2525, 2889, 0, LocType.getId('loc474_19593'));
    check(BURROW !== null, 'the burrow at 2525,2889 is where the map put it');
    // level gate
    player.stats[PlayerStat.HUNTER] = getExpByLevel(5); player.baseLevels[PlayerStat.HUNTER] = 5; player.levels[PlayerStat.HUNTER] = 5;
    await op(1, BURROW);
    check(v('hunter_track_next') === -1, 'below Hunter 7 a burrow gives no trail');
    player.stats[PlayerStat.HUNTER] = getExpByLevel(LEVEL); player.baseLevels[PlayerStat.HUNTER] = LEVEL; player.levels[PlayerStat.HUNTER] = LEVEL;
    // a bush with no trail
    { const b = locAtXZ(2531, 2890)!; const n = msgs.length; player.invAdd(InvType.INV, ObjType.getId('noose_wand'), 1);
      await op(2, b); check(msgs.slice(n).some(m => m.includes('nothing in there')), 'Attack on a bush with no trail finds nothing'); inv0.remove(ObjType.getId('noose_wand'), 1); }
    let caught = false, trails = 0, hintsOk = true, hints = 0, steps = 0;
    while (!caught && trails < 10) {
        trails++;
        let n = msgs.length;
        await op(1, BURROW);
        check(trails > 1 || v('hunter_track_next') !== -1, 'a burrow starts a trail');
        let from = { x: BURROW!.x, z: BURROW!.z };
        for (let hop = 0; hop < 8; hop++) {
            const next = xz(v('hunter_track_next')), bush = xz(v('hunter_track_bush'));
            const said = msgs.slice(n).reverse().find(m => m.includes('tracks'));
            hints++; if (!said || !said.includes(dir(from.x, from.z, next.x, next.z))) { hintsOk = false; log('hint mismatch', said, from, next, dir(from.x, from.z, next.x, next.z)); }
            if (next.x === bush.x && next.z === bush.z) break;
            const loc = locAtXZ(next.x, next.z);
            if (!loc) { check(false, `the trail's next step ${next.x},${next.z} has something to inspect`); break; }
            if (hop === 0 && trails === 1) {
                // a node that is not the next step: no tracks, and the trail is unchanged
                const other = [[2522, 2881], [2524, 2891], [2555, 2881]].map(([x, z]) => locAtXZ(x, z)).find(l => l && (l.x !== next.x || l.z !== next.z));
                if (other) { const m0 = msgs.length; await op(1, other); check(msgs.slice(m0).some(m => m.includes('find no tracks')) && v('hunter_track_next') === ((next.x << 14) | next.z), 'inspecting the wrong plant finds no tracks and keeps the trail'); }
            }
            n = msgs.length; await op(1, loc); steps++;
            from = next;
        }
        const bush = xz(v('hunter_track_bush'));
        const bl = locAtXZ(bush.x, bush.z);
        check(bl !== null, `the trail ends at a bush (${bush.x},${bush.z})`);
        if (!bl) break;
        if (trails === 1) {
            const n0 = msgs.length; await op(1, bl); check(msgs.slice(n0).some(m => m.includes('weasel hiding')), '...Search on it finds the weasel');
            const n1 = msgs.length; await op(2, bl); check(msgs.slice(n1).some(m => m.includes('need a noose wand')), '...which needs a noose wand to catch');
            player.invAdd(InvType.INV, ObjType.getId('noose_wand'), 1);
        }
        const b = { bones: tot('bones'), fur: tot('feldip_weasel_fur'), xp: player.stats[PlayerStat.HUNTER] };
        await op(2, bl);
        await waitTicks(4); // the noose is an anim and a two-tick delay before the roll resolves
        if (tot('feldip_weasel_fur') > b.fur) {
            caught = true;
            check(tot('bones') === b.bones + 1, '...caught: bones and Feldip weasel fur');
            check(player.stats[PlayerStat.HUNTER] - b.xp === parseInt(/\^hunter_weasel_xp = (\d+)/.exec(CONST)![1]), `...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
        }
        check(v('hunter_track_next') === -1, `...and the trail is spent either way (trail ${trails})`);
    }
    check(caught, `a weasel caught within 10 trails (${trails})`);
    check(hintsOk, `every hint named the real direction of the next step (${hints} hints, ${steps} plants)`);
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

// HTRAP=desert: the Kharidian desert (hunter_desert.rs2). HAREA=devil - desert devil tracking in the Uzer
// hunter area: the ground (every trail node and hiding spot where the enum says, with an op behind it, and
// walkable to from ::desert), the level gate, and trails followed to a catch with every hint checked.
// HAREA=warbler - bird snares among the golden warblers, and at HLEVEL below their 5 nothing comes.
// HAREA=shop - Artimeus and the Nardah Hunter Shop.
if (process.env.HTRAP === 'desert') {
    const AREA = process.env.HAREA ?? 'devil';
    const DCONST = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter_desert.constant`, 'utf8');
    const dnum = (n: string) => parseInt(new RegExp(`\\^${n} = (-?\\d+)`).exec(DCONST)![1]);
    const inv0 = player.getInventory(InvType.INV)!;
    const tot = (n: string) => inv0.getItemCount(ObjType.getId(n));
    const setLevel = (l: number) => { player.stats[PlayerStat.HUNTER] = getExpByLevel(l); player.baseLevels[PlayerStat.HUNTER] = l; player.levels[PlayerStat.HUNTER] = l; };
    const v = (n: string) => player.getVar(VarPlayerType.getId(n)) as number;
    const xz = (c: number) => ({ x: (c >> 14) & 0x3fff, z: c & 0x3fff });
    const oploc = (op: number, loc: any) => {
        const t = LocType.get(loc.type);
        const s = ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category);
        if (!s) { log('no script for op', op, t.debugname); return false; }
        player.executeScript(ScriptRunner.init(s, player, loc), true);
        return true;
    };
    const { isMapBlocked, reachedLoc, canTravel } = await import('#/engine/GameMap.js');
    const { CollisionType } = await import('#/engine/routefinder/index.js');
    // a walk: a flood fill over the engine's own collision from a tile, within a box
    const flood = (sx: number, sz: number, box: number[]) => {
        const seenT = new Set<string>([`${sx},${sz}`]); const q = [[sx, sz]];
        while (q.length) {
            const [x, z] = q.shift()!;
            for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
                const k = `${x + dx},${z + dz}`;
                if (seenT.has(k) || x + dx < box[0] || x + dx > box[2] || z + dz < box[1] || z + dz > box[3]) continue;
                if (!canTravel(0, x, z, dx, dz, 1, 0, CollisionType.NORMAL)) continue;
                seenT.add(k); q.push([x + dx, z + dz]);
            }
        }
        return seenT;
    };
    // can a player standing somewhere in `walk` interact with this loc?
    const reachable = (walk: Set<string>, loc: any) => {
        if (!loc) return false;
        const t = LocType.get(loc.type);
        const w = loc.angle & 1 ? t.length : t.width, l = loc.angle & 1 ? t.width : t.length;
        for (let x = loc.x - 1; x <= loc.x + w; x++) for (let z = loc.z - 1; z <= loc.z + l; z++) {
            if (!walk.has(`${x},${z}`)) continue;
            if (loc.shape === 22 || reachedLoc(0, x, z, loc.x, loc.z, t.width, t.length, 1, loc.angle, loc.shape, t.forceapproach)) return true;
        }
        return false;
    };
    const npcsOf = (name: string) => { const id = NpcType.getId(name); const out: any[] = []; for (const n of World.npcs) if (n && n.type === id) out.push(n); return out; };
    const debugTele = async (spot: number) => {
        const s = ScriptProvider.getByName('[debugproc,desert]')!;
        player.executeScript(ScriptRunner.init(s, player, null, [spot]), true);
        await waitTicks(2);
    };

    if (AREA === 'devil') {
        const ENUM = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter_desert.enum`, 'utf8');
        const coords = (name: string) => {
            const body = ENUM.split(`[${name}]`)[1].split('\n[')[0];
            return [...body.matchAll(/val=\d+,0_(\d+)_(\d+)_(\d+)_(\d+)/g)].map(m => ({ x: +m[1] * 64 + +m[3], z: +m[2] * 64 + +m[4] }));
        };
        const NODES = coords('hunter_devil_nodes'), SANDS = coords('hunter_devil_sands');
        const NODE_TYPES = ['hunter_desert_cactus4', 'hunter_desert_cactus5', 'hunter_desert_rockslide1', 'hunter_desert_rockslide2', 'hunter_desert_rockslide3', 'hunter_desert_rockslide4', 'loc474_19552'].map(n => LocType.getId(n));
        const BURROW = LocType.getId('loc474_19552'), SAND = LocType.getId('loc474_19430');
        const nodeAt = (x: number, z: number) => { for (const t of NODE_TYPES) { const l = World.getLoc(x, z, 0, t); if (l) return l; } return null; };
        const sandAt = (x: number, z: number) => World.getLoc(x, z, 0, SAND);
        const locAtXZ = (x: number, z: number) => nodeAt(x, z) ?? sandAt(x, z);

        // ---- the ground
        check(NODES.length === 17 && SANDS.length === 6, `the enum lists 17 nodes (15 cacti and rockslides, 2 burrows) and 6 hiding spots (${NODES.length}, ${SANDS.length})`);
        const noNode = NODES.filter(c => !nodeAt(c.x, c.z)), noSand = SANDS.filter(c => !sandAt(c.x, c.z));
        check(noNode.length === 0, `every node coord has a tracking cactus, rockslide or burrow on it (${noNode.map(c => `${c.x},${c.z}`).join(' ') || 'all'})`);
        check(noSand.length === 0, `every hiding-spot coord has disturbed sand on it (${noSand.map(c => `${c.x},${c.z}`).join(' ') || 'all'})`);
        // and nothing else in the square is a node the enum does not know about (a dead end of a trail)
        const extra: string[] = [];
        for (let x = 3392; x < 3392 + 64; x++) for (let z = 3072; z < 3072 + 64; z++) {
            if (nodeAt(x, z) && !NODES.some(c => c.x === x && c.z === z)) extra.push(`${x},${z}`);
            if (sandAt(x, z) && !SANDS.some(c => c.x === x && c.z === z)) extra.push(`sand ${x},${z}`);
        }
        check(extra.length === 0, `...and no tracking loc on the map that the enum leaves out (${extra.join(' ') || 'none'})`);
        const dead: string[] = [];
        for (const t of NODE_TYPES) if (!ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1, t, LocType.get(t).category)) dead.push(LocType.get(t).debugname!);
        for (const op of [1, 2]) if (!ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1 + op - 1, SAND, LocType.get(SAND).category)) dead.push(`sand op${op}`);
        check(dead.length === 0, `Inspect on every node type, and Search and Attack on the sand, have a script (${dead.join(' ') || 'all'})`);
        await debugTele(1);
        const start = { x: player.x, z: player.z };
        check(start.x === 3400 && start.z === 3118 && tot('noose_wand') === 1 && tot('hunter_bird_snare') === 5, `::desert lands in the tracking ground (${start.x},${start.z}) with a noose wand and five snares`);
        const walk = flood(start.x, start.z, [3392 - 20, 3072 - 20, 3392 + 64 + 20, 3136 + 20]);
        const cut = [...NODES, ...SANDS].filter(c => !reachable(walk, locAtXZ(c.x, c.z)));
        check(cut.length === 0, `...and a player can walk from there to every node and every hiding spot (${cut.map(c => `${c.x},${c.z}`).join(' ') || 'all'})`);
        inv0.remove(ObjType.getId('noose_wand'), 1);

        const dir = (fx: number, fz: number, tx: number, tz: number) => {
            const dx = tx - fx, dz = tz - fz, ax = Math.abs(dx), az = Math.abs(dz);
            const ns = dz > 0 ? 'north' : dz < 0 ? 'south' : '', ew = dx > 0 ? 'east' : dx < 0 ? 'west' : '';
            if (ax > az * 2) return ew; if (az > ax * 2) return ns; if (!ns) return ew; if (!ew) return ns; return `${ns}-${ew}`;
        };
        const op = async (opn: number, loc: any) => { player.teleport(loc.x, loc.z - 1, 0); await waitTicks(1); oploc(opn, loc); await waitTicks(3); };
        const burrows = NODES.map(c => World.getLoc(c.x, c.z, 0, BURROW)).filter(Boolean) as any[];
        check(burrows.length === 2, `two burrows (${burrows.map(b => `${b.x},${b.z}`).join(' ')})`);
        // the level gate
        const LVL = dnum('hunter_devil_level');
        setLevel(LVL - 1);
        await op(1, burrows[0]);
        check(v('hunter_track_next') === -1, `below Hunter ${LVL} a burrow gives no trail`);
        setLevel(LEVEL);
        { const s = sandAt(SANDS[0].x, SANDS[0].z)!; const n = msgs.length; player.invAdd(InvType.INV, ObjType.getId('noose_wand'), 1);
          await op(2, s); check(msgs.slice(n).some(m => m.includes('nothing in there')), 'Attack on disturbed sand with no trail finds nothing'); inv0.remove(ObjType.getId('noose_wand'), 1); }
        let caught = false, trails = 0, hintsOk = true, hints = 0, steps = 0, ends = true;
        const lengths: number[] = [];
        // at least four trails, from both burrows, however soon the first catch comes
        while ((!caught || trails < 4) && trails < 12) {
            trails++;
            const burrow = burrows[trails % 2];
            let n = msgs.length;
            await op(1, burrow);
            check(trails > 1 || v('hunter_track_next') !== -1, 'a burrow starts a trail');
            const bushC = xz(v('hunter_track_bush'));
            if (!SANDS.some(c => c.x === bushC.x && c.z === bushC.z)) { ends = false; log('trail ends off the sands', bushC); }
            let from = { x: burrow.x, z: burrow.z }, len = 0;
            for (let hop = 0; hop < 10; hop++) {
                const next = xz(v('hunter_track_next')), bush = xz(v('hunter_track_bush'));
                const said = msgs.slice(n).reverse().find(m => m.includes('tracks'));
                hints++; if (!said || !said.includes(dir(from.x, from.z, next.x, next.z))) { hintsOk = false; log('hint mismatch', said, from, next, dir(from.x, from.z, next.x, next.z)); }
                if (next.x === bush.x && next.z === bush.z) { if (!said?.includes('disturbed sand')) { hintsOk = false; log('the last hint does not name the sand', said); } break; }
                const loc = nodeAt(next.x, next.z);
                if (!loc) { check(false, `the trail's next step ${next.x},${next.z} has something to inspect`); break; }
                if (hop === 0 && trails === 1) {
                    const other = NODES.map(c => nodeAt(c.x, c.z)).find(l => l && l.type !== BURROW && (l.x !== next.x || l.z !== next.z));
                    if (other) { const m0 = msgs.length; await op(1, other); check(msgs.slice(m0).some(m => m.includes('find no tracks')) && v('hunter_track_next') === ((next.x << 14) | next.z), `inspecting the wrong ${LocType.get(other.type).name!.toLowerCase()} finds no tracks and keeps the trail`); }
                }
                n = msgs.length; await op(1, loc); steps++; len++;
                from = next;
            }
            lengths.push(len);
            const bush = xz(v('hunter_track_bush'));
            const bl = sandAt(bush.x, bush.z);
            check(trails > 1 || bl !== null, `the trail ends at disturbed sand (${bush.x},${bush.z})`);
            if (!bl) break;
            if (trails === 1) {
                const n0 = msgs.length; await op(1, bl); check(msgs.slice(n0).some(m => m.includes('desert devil hiding')), '...Search on it finds the desert devil');
                const n1 = msgs.length; await op(2, bl); check(msgs.slice(n1).some(m => m.includes('need a noose wand')), '...which needs a noose wand to catch');
                player.invAdd(InvType.INV, ObjType.getId('noose_wand'), 1);
            }
            const b = { bones: tot('bones'), fur: tot('desert_devil_fur'), xp: player.stats[PlayerStat.HUNTER] };
            await op(2, bl);
            await waitTicks(4);
            if (tot('desert_devil_fur') > b.fur) {
                caught = true;
                check(tot('bones') === b.bones + 1 && tot('desert_devil_fur') === b.fur + 1, '...caught: bones and desert devil fur');
                check(player.stats[PlayerStat.HUNTER] - b.xp === dnum('hunter_devil_xp'), `...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
            }
            check(v('hunter_track_next') === -1 && v('hunter_track_bush') === -1, `...and the trail is spent either way (trail ${trails})`);
        }
        check(caught, `a desert devil caught within 12 trails (${trails})`);
        check(ends, "every trail ended in the desert's disturbed sand, never at a Feldip bush");
        check(hintsOk, `every hint named the real direction of the next step, the last one the sand (${hints} hints, ${steps} cacti and rockslides; trails ${lengths.join(',')} long)`);
    }

    if (AREA === 'warbler') {
        const LVL = dnum('hunter_warbler_level'), XP = dnum('hunter_warbler_xp');
        const CAN = LEVEL >= LVL;
        const birds = npcsOf('hunter_golden_warbler');
        check(birds.length === 10, `10 golden warblers in the world (${birds.length})`);
        check(birds.every(b => b.x >= 3392 && b.x < 3456 && b.z >= 3072 && b.z < 3200), '...all in the Uzer hunter area');
        const TYPES = ['hunter_snare_laid', 'hunter_snare_springing', 'hunter_snare_collapsed', 'hunter_snare_catching_warbler', 'hunter_snare_caught_warbler'];
        const locAt = (x: number, z: number) => { for (const t of TYPES) { const l = World.getLoc(x, z, 0, LocType.getId(t)); if (l) return { name: t, loc: l }; } return null; };
        const slots = () => [1, 2, 3, 4, 5].map(i => player.getVar(VarPlayerType.getId(`hunter_trap${i}`)) as number).filter(c => c !== -1);
        const lay = async (x: number, z: number) => {
            player.teleport(x, z, 0); await waitTicks(2);
            const id = ObjType.getId('hunter_bird_snare'); player.lastItem = id; player.lastSlot = inv0.getItemIndex(id);
            if (player.lastSlot === -1) return;
            player.executeScript(ScriptRunner.init(ScriptProvider.getByTrigger(ServerTriggerType.OPHELD1, id, ObjType.get(id).category)!, player), true);
            await waitTicks(6);
        };
        await debugTele(2);
        const north = { x: player.x, z: player.z };
        const walkN = flood(north.x, north.z, [3370, 3110, 3450, 3190]);
        await debugTele(3);
        const south = { x: player.x, z: player.z };
        const walkS = flood(south.x, south.z, [3370, 3050, 3450, 3130]);
        const lost = birds.filter(b => !walkN.has(`${b.x},${b.z}`) && !walkS.has(`${b.x},${b.z}`));
        check(lost.length === 0, `every warbler is on ground a player can walk to from ::desert 2 or 3 (${lost.map(b => `${b.x},${b.z}`).join(' ') || 'all'})`);
        // lay round the north flock's middle, on open tiles
        const max = Math.min(5, 1 + Math.floor(LEVEL / 20));
        const cands: number[][] = [];
        for (let r = 0; r < 4 && cands.length < 12; r++) for (let dx = -r; dx <= r; dx++) for (let dz = -r; dz <= r; dz++) {
            const x = 3402 + dx * 2, z = 3150 + dz * 2;
            if (Math.max(Math.abs(dx), Math.abs(dz)) === r && walkN.has(`${x},${z}`) && !isMapBlocked(x, z, 0)) cands.push([x, z]);
        }
        for (const [x, z] of cands) { if (slots().length >= max) break; await lay(x, z); }
        const laid = slots();
        check(laid.length === max && tot('hunter_bird_snare') === 5 - max, `${max} snares laid among the warblers at level ${LEVEL} (${laid.length})`);
        let caught: any = null; const seen = new Map<string, string>();
        const LIMIT = CAN ? 1500 : 300;
        for (let t = 0; t < LIMIT && !caught; t++) {
            await waitTicks(1);
            for (const c of slots()) {
                const { x, z } = xz(c); const s = locAt(x, z)?.name ?? '(none)';
                if (seen.get(`${x},${z}`) !== s) { log('snare', x, z, '->', s); seen.set(`${x},${z}`, s); }
                if (s === 'hunter_snare_caught_warbler') { caught = { x, z }; break; }
                if (s === 'hunter_snare_collapsed') { oploc(1, locAt(x, z)!.loc); await waitTicks(2); await lay(x, z); }
            }
        }
        if (CAN) {
            check(caught !== null, `a golden warbler flew into a snare within ${LIMIT} ticks`);
            if (caught) {
                const b: any = { snare: tot('hunter_bird_snare'), xp: player.stats[PlayerStat.HUNTER] };
                const LOOT = ['bones', 'raw_bird_meat', 'yellow_feather', 'red_feather', 'stripy_feather'];
                for (const n of LOOT) b[n] = tot(n);
                oploc(1, locAt(caught.x, caught.z)!.loc); await waitTicks(2);
                const got = Object.fromEntries(LOOT.map(n => [n, tot(n) - b[n]]).filter(([, d]) => d !== 0));
                const f = parseInt(/\^hunter_bird_feathers = (\d+)/.exec(CONST)![1]);
                check(JSON.stringify(got) === JSON.stringify({ bones: 1, raw_bird_meat: 1, yellow_feather: f }), `...Check pays bones, raw bird meat and ${f} yellow feathers, and nothing else (${JSON.stringify(got)})`);
                check(player.stats[PlayerStat.HUNTER] - b.xp === XP, `...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
                check(tot('hunter_bird_snare') === b.snare + 1 && locAt(caught.x, caught.z) === null, '...gives the snare back and clears the tile');
            }
        } else {
            check([...seen.values()].every(s => !/catching|caught/.test(s)), `at level ${LEVEL}, below the golden warbler's ${LVL}, nothing flies into a snare`);
            check(slots().length === 0 && msgs.some(m => m.includes('fallen over')), '...and the snares left there fall over');
        }
        // [logout] hands back whatever is still laid
        const lo = ScriptProvider.getByTrigger(ServerTriggerType.LOGOUT, -1, -1);
        player.executeScript(ScriptRunner.init(lo!, player), true); await waitTicks(2);
        check(slots().length === 0, '[logout] frees every slot');
    }

    if (AREA === 'shop') {
        const art = npcsOf('artimeus');
        check(art.length === 1 && Math.abs(art[0].x - 3441) <= 3 && Math.abs(art[0].z - 2902) <= 3, `Artimeus is in Nardah, at the OSRS wiki's 3441,2902 (${art.map(a => `${a.x},${a.z}`).join(' ')})`);
        const t = NpcType.get(art[0].type);
        const talk = ScriptProvider.getByTrigger(ServerTriggerType.OPNPC1, t.id, t.category);
        check(talk !== undefined && talk.name.includes('artimeus'), `Talk-to is his own dialogue (${talk?.name})`);
        await debugTele(4);
        const walk = flood(player.x, player.z, [3392 + 10, 2880 - 10, 3392 + 70, 2880 + 60]);
        check([[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dz]) => walk.has(`${art[0].x + dx},${art[0].z + dz}`)), `...and he can be walked up to from ::desert 4 (${player.x},${player.z})`);
        check(walk.size > 400, `...which is not a sealed room (${walk.size} tiles reachable)`);
        const trade = ScriptProvider.getByTrigger(ServerTriggerType.OPNPC3, t.id, t.category)!;
        player.executeScript(ScriptRunner.init(trade, player, art[0]), true); await waitTicks(2);
        const SHOP = InvType.getId('nardah_hunter_shop');
        check(player.getVar(VarPlayerType.getId('shop')) === SHOP, 'Trade opens the Nardah Hunter Shop');
        const shop = player.getInventory(SHOP)!;
        const want: Record<string, number> = { net: 5, noose_wand: 50, hunter_bird_snare: 50, hunter_box_trap: 25, teasing_stick: 5, torch_unlit: 20 };
        const off = Object.entries(want).filter(([n, q]) => shop.getItemCount(ObjType.getId(n)) !== q);
        check(off.length === 0, `...stocked as the wiki has it (${off.map(([n]) => `${n} ${shop.getItemCount(ObjType.getId(n))}`).join(' ') || Object.keys(want).join(', ')})`);
    }
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

// HTRAP=pitfall: spiked logs over the pit at 2543,2908 (reached only from 2543,2907, south), a
// tease, and the jump north to 2543,2910 with the larupia behind.
if (process.env.HTRAP === 'pitfall') {
    const inv0 = player.getInventory(InvType.INV)!;
    const tot = (n: string) => inv0.getItemCount(ObjType.getId(n));
    const PIT = LocType.getId('loc474_19227');
    const ST = ['hunter_pit_spiked', 'hunter_pit_collapsed', 'hunter_pit_larupia'];
    const [PX, PZ] = [2543, 2908], [SX, SZ] = [2543, 2907], [LX, LZ] = [2543, 2910];
    const pitAt = () => { for (const n of ST) { const l = World.getLoc(PX, PZ, 0, LocType.getId(n)); if (l) return { name: n, loc: l }; } return null; };
    const plainPit = () => World.getLoc(PX, PZ, 0, PIT);
    const run = (trigger: number, id: number, cat: number, target: any) => {
        const script = ScriptProvider.getByTrigger(trigger, id, cat);
        player.executeScript(ScriptRunner.init(script!, player, target), true);
    };
    const oploc = (op: number, loc: any) => { const t = LocType.get(loc.type); run(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category, loc); };
    const LARUPIA = NpcType.getId('hunter_spined_larupia');
    const nearestLarupia = () => { let best: any = null, bd = 99; for (const n of World.npcs) if (n && n.type === LARUPIA) { const d = Math.max(Math.abs(n.x - SX), Math.abs(n.z - SZ)); if (d < bd) { bd = d; best = n; } } return best; };
    const tease = (npc: any) => { const t = NpcType.get(npc.type); run(ServerTriggerType.OPNPC1, t.id, t.category, npc); };
    const teased = () => player.getVar(VarPlayerType.getId('hunter_tease_npc')) as number;
    const setPit = async () => { player.teleport(SX, SZ, 0); await waitTicks(2); oploc(3, plainPit()); await waitTicks(5); };
    const jump = async () => { player.teleport(SX, SZ, 0); await waitTicks(1); oploc(1, pitAt()!.loc); await waitTicks(4); };

    player.invAdd(InvType.INV, ObjType.getId('knife'), 1);
    // Fifteen, not five: each failed jump spends a log and each re-set another, and a run of bad rolls
    // used to leave the last re-set with none ("You need some logs") - one flake in five runs.
    player.invAdd(InvType.INV, ObjType.getId('logs'), 15);
    check(plainPit() !== null, 'the pit is where the map put it, on the ground floor (a linkbelow bridge tile)');
    await setPit();
    check(pitAt()?.name === 'hunter_pit_spiked' && tot('logs') === 14, 'spiked logs laid over the pit, for one log');
    await jump();
    check(player.x === LX && player.z === LZ, `a jump from ${SX},${SZ} lands across the trench at ${LX},${LZ} (${player.x},${player.z})`);
    check(pitAt()?.name === 'hunter_pit_spiked', '...and with nothing chasing, the pit is untouched');
    // the tease level gate
    player.stats[PlayerStat.HUNTER] = getExpByLevel(25); player.baseLevels[PlayerStat.HUNTER] = 25; player.levels[PlayerStat.HUNTER] = 25;
    player.teleport(SX, SZ, 0); await waitTicks(1);
    tease(nearestLarupia()); await waitTicks(2);
    check(teased() === -1, 'below Hunter 31 the larupia cannot be teased');
    player.stats[PlayerStat.HUNTER] = getExpByLevel(LEVEL); player.baseLevels[PlayerStat.HUNTER] = LEVEL; player.levels[PlayerStat.HUNTER] = LEVEL;
    { const n = msgs.length; tease(nearestLarupia()); await waitTicks(1); check(msgs.slice(n).some(m => m.includes('need a teasing stick')) && teased() === -1, 'no tease without a teasing stick'); }
    player.invAdd(InvType.INV, ObjType.getId('teasing_stick'), 1);
    let fell = false;
    for (let attempt = 0; attempt < 12 && !fell; attempt++) {
        if (pitAt() === null) await setPit(); // a spiked pit untouched for its duration reverts to the plain pit
        if (pitAt()?.name !== 'hunter_pit_spiked') {
            if (pitAt()?.name === 'hunter_pit_collapsed') {
                const logs = tot('logs');
                oploc(2, pitAt()!.loc); await waitTicks(2);
                check(plainPit() !== null && tot('logs') === logs, 'a collapsed pit dismantles back to the pit, and the log is spent');
            }
            await setPit();
        }
        player.teleport(SX, SZ, 0); await waitTicks(1);
        const npc = nearestLarupia();
        if (!npc) { await waitTicks(60); continue; }
        tease(npc); await waitTicks(1);
        if (attempt === 0) {
            // It FOLLOWS: its mode is PLAYERFOLLOW (4), and when the player steps away it moves after them.
            check(teased() !== -1 && npc.targetOp === 4, `a teased larupia is set to follow (targetOp ${npc.targetOp})`);
            const [nx, nz] = [npc.x, npc.z];
            // stand on the take-off tile and let it come: it must actually move to be behind you
            for (let i = 0; i < 8; i++) { await waitTicks(1); if (process.env.HTRACE) log('larupia', npc.x, npc.z, 'op', npc.targetOp, 'player', player.x, player.z); }
            if (process.env.HTRACE) {
                const n: any = npc;
                const { findNaivePath } = await import('#/engine/GameMap.js');
                const wp = findNaivePath(0, n.x, n.z, player.x, player.z, n.width, n.length, 1, 1, 0, 0);
                log('moveStrategy', n.moveStrategy, 'collisionStrategy', n.getCollisionStrategy?.(), 'blockWalkFlag', n.blockWalkFlag?.(), 'size', n.width, n.length, 'moveRestrict', (NpcType.get(n.type) as any).moverestrict);
                log('naive waypoints', Array.from(wp as any).map((c: any) => `${(c >> 14) & 0x3fff},${c & 0x3fff}`).join(' '));
                const { isMapBlocked } = await import('#/engine/GameMap.js');
                for (let z = n.z + 3; z >= n.z - 1; z--) { let row = `${z} `; for (let x = n.x - 2; x <= n.x + 3; x++) row += isMapBlocked(x, z, 0) ? '#' : '.'; log(row); }
            }
            const wasBehind = Math.max(Math.abs(nx - SX), Math.abs(nz - SZ)) <= 2;
            check(npc.x !== nx || npc.z !== nz || wasBehind, `...and moves after the player, unless it was already at their heels (${nx},${nz} -> ${npc.x},${npc.z})`);
            check(Math.max(Math.abs(npc.x - SX), Math.abs(npc.z - SZ)) <= 3, `...until it is right behind them (${npc.x},${npc.z})`);
        } else await waitTicks(3);
        await jump();
        log('jump', attempt, '->', pitAt()?.name);
        if (pitAt()?.name === 'hunter_pit_larupia') fell = true;
    }
    check(fell, 'the larupia followed the jump into the pit within 12 tries');
    if (fell) {
        const b = { bones: tot('big_bones'), fur: tot('larupia_fur'), logs: tot('logs'), xp: player.stats[PlayerStat.HUNTER] };
        player.teleport(SX, SZ, 0); await waitTicks(1);
        oploc(2, pitAt()!.loc); await waitTicks(2);
        check(tot('big_bones') === b.bones + 1 && tot('larupia_fur') === b.fur + 1, '...Dismantle pays big bones and larupia fur');
        check(player.stats[PlayerStat.HUNTER] - b.xp === parseInt(/\^hunter_larupia_xp = (\d+)/.exec(CONST)![1]), `...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
        check(tot('logs') === b.logs && plainPit() !== null, '...no log back, and the pit is a pit again');
    }
    { const n = msgs.length; await setPit();
      if (pitAt()?.name !== 'hunter_pit_spiked') check(false, `re-setting the pit took (${pitAt()?.name ?? (plainPit() ? 'plain pit' : 'nothing')}; delayed ${player.delayed}, protect ${player.protect}, at ${player.x},${player.z}; said: ${JSON.stringify(msgs.slice(n))})`); }
    if (pitAt()?.name === 'hunter_pit_spiked') { const logs = tot('logs'); oploc(2, pitAt()!.loc); await waitTicks(2); check(tot('logs') === logs + 1 && plainPit() !== null, 'Dismantle on an unsprung pit gives its log back'); }
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

// HTRAP=graahk: the Karamja hunter area (m43_46/m43_47, imported from 474) - its five pits, four horned
// graahks and the teasing stick on the ground. Every pit: on the ground floor, a take-off tile with a
// landing across it, reached on foot from ::karamja's tile, and spiked logs set and dismantled on it.
// Every graahk: teased from the take-off of the pit nearest it, it must come to your heels (a 2x2 npc
// moves naively; a boxed-in spawn never arrives). Then the tease's level gate and a real catch.
if (process.env.HTRAP === 'graahk') {
    const inv0 = player.getInventory(InvType.INV)!;
    const tot = (n: string) => inv0.getItemCount(ObjType.getId(n));
    const setLevel = (l: number) => { player.stats[PlayerStat.HUNTER] = getExpByLevel(l); player.baseLevels[PlayerStat.HUNTER] = l; player.levels[PlayerStat.HUNTER] = l; };
    const { isMapBlocked, findPath } = await import('#/engine/GameMap.js');
    const PIT = LocType.getId('loc474_19227');
    const ST = ['hunter_pit_spiked', 'hunter_pit_collapsed', 'hunter_pit_graahk'];
    const GRAAHK = NpcType.getId('hunter_horned_graahk');
    const START = [2777, 3000]; // ::karamja lands here
    const PITS = [[2762, 3005], [2766, 3010], [2771, 3004], [2777, 3001], [2784, 3001]];
    const cnum = (n: string) => parseInt(new RegExp(`\\^${n} = (-?\\d+)`).exec(CONST + fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter_karamja.constant`, 'utf8'))![1]);
    const GLEVEL = cnum('hunter_graahk_level');
    const pitAt = (x: number, z: number) => { for (const n of ST) { const l = World.getLoc(x, z, 0, LocType.getId(n)); if (l) return { name: n, loc: l }; } return null; };
    const plainPit = (x: number, z: number) => World.getLoc(x, z, 0, PIT);
    const run = (trigger: number, id: number, cat: number, target: any) => {
        const script = ScriptProvider.getByTrigger(trigger, id, cat);
        player.executeScript(ScriptRunner.init(script!, player, target), true);
    };
    const oploc = (op: number, loc: any) => { const t = LocType.get(loc.type); run(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category, loc); };
    const tease = (npc: any) => { const t = NpcType.get(npc.type); run(ServerTriggerType.OPNPC1, t.id, t.category, npc); };
    const teased = () => player.getVar(VarPlayerType.getId('hunter_tease_npc')) as number;
    // the script's own landing rule: straight across, the first open tile 2-4 past the take-off
    const landing = (fx: number, fz: number, px: number, pz: number) => {
        const sx = Math.sign(px - fx), sz = Math.sign(pz - fz);
        for (let k = 2; k <= 4; k++) if (!isMapBlocked(fx + sx * k, fz + sz * k, 0)) return [fx + sx * k, fz + sz * k];
        return null;
    };
    const walks = (fx: number, fz: number, tx: number, tz: number) => {
        const wp = findPath(0, fx, fz, tx, tz);
        if (wp.length === 0) return fx === tx && fz === tz;
        const last = wp[wp.length - 1];
        return ((last >> 14) & 0x3fff) === tx && (last & 0x3fff) === tz;
    };
    const takeoffs = new Map<string, number[][]>();
    player.teleport(START[0], START[1], 0); await waitTicks(2);
    player.invAdd(InvType.INV, ObjType.getId('knife'), 1);
    player.invAdd(InvType.INV, ObjType.getId('logs'), 15);

    for (const [px, pz] of PITS) {
        check(plainPit(px, pz) !== null, `the pit at ${px},${pz} is on the ground floor (a linkbelow bridge tile, as at Feldip)`);
        const offs = [[0, -1], [0, 1], [-1, 0], [1, 0]].map(([dx, dz]) => [px + dx, pz + dz])
            .filter(([x, z]) => !isMapBlocked(x, z, 0) && landing(x, z, px, pz) !== null && walks(START[0], START[1], x, z));
        takeoffs.set(`${px},${pz}`, offs);
        check(offs.length > 0, `...it has a take-off tile with a landing across it, reached on foot from ::karamja's tile (${offs.map(o => o.join(',')).join(' ')})`);
        if (!offs.length) continue;
        player.teleport(offs[0][0], offs[0][1], 0); await waitTicks(2);
        oploc(3, plainPit(px, pz)); await waitTicks(5);
        const logs = tot('logs');
        check(pitAt(px, pz)?.name === 'hunter_pit_spiked', '...spiked logs set over it');
        if (pitAt(px, pz)) { oploc(2, pitAt(px, pz)!.loc); await waitTicks(2); }
        check(plainPit(px, pz) !== null && tot('logs') === logs + 1, '...and dismantled: the pit is back, and so is the log');
    }

    // spread first: NpcList is an Array subclass, so its own .filter returns another NpcList, whose
    // iterator walks an id table that copy never filled - a for..of over it would see no graahks at all
    const graahks = [...World.npcs].filter((n: any) => n && n.type === GRAAHK) as any[];
    check(graahks.length === 4, `four horned graahks, as the wiki places them (${graahks.map(g => `${g.x},${g.z}`).join(' ')})`);
    const stick = World.getObj(2774, 2994, 0, ObjType.getId('teasing_stick'), -1n);
    check(stick !== null && !isMapBlocked(2774, 2994, 0) && walks(START[0], START[1], 2774, 2994), 'a teasing stick lies on an open tile south of the pits, reached on foot');

    // the tease's level gate, and no tease without a stick
    const nearest = (x: number, z: number) => graahks.filter(g => g.isActive).sort((a, b) => Math.max(Math.abs(a.x - x), Math.abs(a.z - z)) - Math.max(Math.abs(b.x - x), Math.abs(b.z - z)))[0];
    setLevel(GLEVEL - 1);
    player.invAdd(InvType.INV, ObjType.getId('teasing_stick'), 1);
    tease(nearest(START[0], START[1])); await waitTicks(2);
    check(teased() === -1, `below Hunter ${GLEVEL} a graahk cannot be teased`);
    setLevel(LEVEL);
    inv0.remove(ObjType.getId('teasing_stick'), 1);
    { const n = msgs.length; tease(nearest(START[0], START[1])); await waitTicks(1); check(msgs.slice(n).some(m => m.includes('need a teasing stick')) && teased() === -1, 'no tease without a teasing stick'); }
    player.invAdd(InvType.INV, ObjType.getId('teasing_stick'), 1);

    // every graahk comes to the take-off tile of the pit nearest it
    const reset = async (g: any) => { g.resetDefaults(); g.teleport(g.startX, g.startZ, 0); await waitTicks(2); };
    for (const g of graahks) {
        const [sx, sz] = [g.startX, g.startZ];
        const byDist = PITS.slice().sort((a, b) => Math.max(Math.abs(a[0] - sx), Math.abs(a[1] - sz)) - Math.max(Math.abs(b[0] - sx), Math.abs(b[1] - sz)));
        let came: string | null = null;
        for (const [ox, oz] of takeoffs.get(`${byDist[0][0]},${byDist[0][1]}`) ?? []) {
            await reset(g);
            player.teleport(ox, oz, 0); await waitTicks(1);
            tease(g);
            for (let i = 0; i < 10 && Math.max(Math.abs(g.x - ox), Math.abs(g.z - oz)) > 2; i++) await waitTicks(1);
            if (Math.max(Math.abs(g.x - ox), Math.abs(g.z - oz)) <= 3) { came = `${ox},${oz}`; break; }
        }
        check(came !== null, `the graahk from ${sx},${sz} follows a tease to the take-off of its nearest pit, ${byDist[0].join(',')} (${came ?? 'never came'})`);
        await reset(g);
    }

    // a real catch: tease, jump, and the graahk in the pit
    const [PX, PZ] = [2777, 3001];
    const [SX, SZ] = takeoffs.get(`${PX},${PZ}`)![0];
    const [LX, LZ] = landing(SX, SZ, PX, PZ)!;
    const setPit = async () => { player.teleport(SX, SZ, 0); await waitTicks(2); oploc(3, plainPit(PX, PZ)); await waitTicks(5); };
    const jump = async () => { player.teleport(SX, SZ, 0); await waitTicks(1); oploc(1, pitAt(PX, PZ)!.loc); await waitTicks(4); };
    await setPit();
    await jump();
    check(player.x === LX && player.z === LZ && pitAt(PX, PZ)?.name === 'hunter_pit_spiked', `a jump from ${SX},${SZ} lands across at ${LX},${LZ}, and with nothing chasing the pit is untouched`);
    let fell = false;
    for (let attempt = 0; attempt < 12 && !fell; attempt++) {
        if (pitAt(PX, PZ)?.name === 'hunter_pit_collapsed') {
            const logs = tot('logs');
            oploc(2, pitAt(PX, PZ)!.loc); await waitTicks(2);
            check(plainPit(PX, PZ) !== null && tot('logs') === logs, 'a collapsed pit dismantles back to the pit, and the log is spent');
        }
        if (pitAt(PX, PZ) === null) await setPit();
        player.teleport(SX, SZ, 0); await waitTicks(1);
        const g = nearest(SX, SZ);
        if (!g || !g.isActive) { await waitTicks(60); continue; }
        tease(g);
        for (let i = 0; i < 10 && Math.max(Math.abs(g.x - SX), Math.abs(g.z - SZ)) > 2; i++) await waitTicks(1);
        await jump();
        log('jump', attempt, '->', pitAt(PX, PZ)?.name);
        if (pitAt(PX, PZ)?.name === 'hunter_pit_graahk') fell = true;
    }
    check(fell, 'a teased graahk followed the jump into the pit within 12 tries');
    if (fell) {
        const b = { bones: tot('big_bones'), fur: tot('graahk_fur'), logs: tot('logs'), xp: player.stats[PlayerStat.HUNTER] };
        player.teleport(SX, SZ, 0); await waitTicks(1);
        oploc(2, pitAt(PX, PZ)!.loc); await waitTicks(2);
        check(tot('big_bones') === b.bones + 1 && tot('graahk_fur') === b.fur + 1, '...Dismantle pays big bones and graahk fur');
        check(player.stats[PlayerStat.HUNTER] - b.xp === cnum('hunter_graahk_xp'), `...${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
        check(tot('logs') === b.logs && plainPit(PX, PZ) !== null, '...no log back, and the pit is a pit again');
    }
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

// HTRAP=deadfall: deadfalls on the four northern boulders, where only barb-tailed kebbits (33) live.
if (process.env.HTRAP === 'deadfall') {
    const inv0 = player.getInventory(InvType.INV)!;
    const tot = (n: string) => inv0.getItemCount(ObjType.getId(n));
    const BOULDER = LocType.getId('loc474_19205');
    const DF = ['hunter_deadfall_set', 'hunter_deadfall_collapsed', 'hunter_deadfall_wild', 'hunter_deadfall_barbtailed'];
    const dfAt = (x: number, z: number) => { for (const n of DF) { const l = World.getLoc(x, z, 0, LocType.getId(n)); if (l) return { name: n, loc: l }; } return null; };
    const boulderAt = (x: number, z: number) => World.getLoc(x, z, 0, BOULDER);
    const slotsN = () => [1, 2, 3, 4, 5].map(i => player.getVar(VarPlayerType.getId(`hunter_trap${i}`)) as number).filter(c => c !== -1);
    const oploc = (op: number, loc: any) => {
        const t = LocType.get(loc.type);
        const script = ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category);
        player.executeScript(ScriptRunner.init(script!, player, loc), true);
    };
    // Far north first: the wild kebbits wander up from the boulder at 2574,2910 and can reach the one
    // at 2574,2916 (the live test caught one there at level 30), but not these two - so the level-30
    // gate pass, which gets two traps, only ever sees barb-tailed kebbits.
    const NORTH = [[2576, 2925], [2572, 2930], [2574, 2916], [2583, 2913]];
    const CATCHES = LEVEL >= parseInt(/\^hunter_barbtailed_kebbit_level = (\d+)/.exec(CONST)![1]);
    const set = async (x: number, z: number) => { player.teleport(x, z - 1, 0); await waitTicks(2); oploc(1, boulderAt(x, z)); await waitTicks(5); };

    player.invAdd(InvType.INV, ObjType.getId('logs'), 5);
    check(boulderAt(NORTH[0][0], NORTH[0][1]) !== null, 'the boulders are where the map put them');
    { const n = msgs.length; await set(NORTH[0][0], NORTH[0][1]); check(msgs.slice(n).some(m => m.includes('need a knife')) && slotsN().length === 0, 'no deadfall without a knife'); }
    player.invAdd(InvType.INV, ObjType.getId('knife'), 1);
    const max = Math.min(5, 1 + Math.floor(LEVEL / 20));
    for (const [x, z] of NORTH.slice(0, max)) await set(x, z);
    check(slotsN().length === max, `${max} deadfalls set at level ${LEVEL} (${slotsN().length})`);
    check(tot('logs') === 5 - max, `...one log each (${tot('logs')} left)`);
    // any deadfall state: a kebbit can walk into one in the ticks between setting it and this look
    for (const [x, z] of NORTH.slice(0, max)) check(dfAt(x, z) !== null, `...the boulder at ${x},${z} is a deadfall (${dfAt(x, z)?.name})`);

    let caught: any = null; const seen = new Map<string, string>();
    for (let t = 0; t < (CATCHES ? 900 : 300) && !caught; t++) {
        await waitTicks(1);
        for (const [x, z] of NORTH.slice(0, max)) {
            const st = dfAt(x, z)?.name ?? (boulderAt(x, z) ? 'boulder' : '(none)');
            if (seen.get(`${x},${z}`) !== st) { log('deadfall', x, z, '->', st); seen.set(`${x},${z}`, st); }
            if (st === 'hunter_deadfall_barbtailed' || st === 'hunter_deadfall_wild') { caught = { x, z, st }; break; }
            if (st === 'hunter_deadfall_collapsed') {
                const logs = tot('logs');
                oploc(1, dfAt(x, z)!.loc); await waitTicks(3);
                check(dfAt(x, z) === null && boulderAt(x, z) !== null && tot('logs') === logs, `a collapsed deadfall dismantles to the boulder, and the log is spent (${x},${z})`);
                await set(x, z);
            }
        }
    }
    if (!caught) {
        // where the barb-tailed kebbits are, if nothing came - so a miss says whether they wandered off
        const kid = NpcType.getId('hunter_barbtailed_kebbit');
        const where: string[] = [];
        for (const npc of World.npcs) if (npc && npc.type === kid) where.push(`${npc.x},${npc.z}`);
        log('barb-tailed kebbits at', where.join(' '));
    }
    if (CATCHES) {
        check(caught !== null, 'a kebbit was caught within 900 ticks');
        if (caught) {
            const b = { bones: tot('bones'), harpoon: tot('barbtail_harpoon'), claws: tot('kebbit_claws'), logs: tot('logs'), xp: player.stats[PlayerStat.HUNTER] };
            oploc(1, dfAt(caught.x, caught.z)!.loc); await waitTicks(3);
            const barb = caught.st === 'hunter_deadfall_barbtailed';
            check(barb ? tot('barbtail_harpoon') === b.harpoon + 1 && tot('kebbit_claws') === b.claws
                       : tot('kebbit_claws') === b.claws + 1 && tot('barbtail_harpoon') === b.harpoon,
                `...Check pays the ${barb ? 'barb-tail harpoon' : 'kebbit claws'} for a ${caught.st}`);
            check(tot('bones') === b.bones + 1, '...and bones');
            check(tot('logs') === b.logs, '...gives no log back - it came down');
            const xpc = barb ? /\^hunter_barbtailed_kebbit_xp = (\d+)/ : /\^hunter_wild_kebbit_xp = (\d+)/;
            check(player.stats[PlayerStat.HUNTER] - b.xp === parseInt(xpc.exec(CONST)![1]), `...and ${(player.stats[PlayerStat.HUNTER] - b.xp) / 10} xp`);
            check(dfAt(caught.x, caught.z) === null && boulderAt(caught.x, caught.z) !== null, '...and the boulder is a boulder again');
        }
    } else {
        check(caught === null, `at level ${LEVEL}, below the barb-tailed kebbit's level, nothing comes to the far-north boulders (${caught?.st ?? 'none'})`);
    }
    // an unsprung deadfall gives its log back, and so does [logout]
    const live = NORTH.slice(0, max).filter(([x, z]) => dfAt(x, z)?.name === 'hunter_deadfall_set');
    if (live.length) {
        const [x, z] = live[0]; const logs = tot('logs');
        oploc(1, dfAt(x, z)!.loc); await waitTicks(3);
        check(tot('logs') === logs + 1 && boulderAt(x, z) !== null, 'Dismantle on an unsprung deadfall gives its log back and leaves the boulder');
    }
    for (const [x, z] of NORTH.slice(0, max)) if (boulderAt(x, z) && slotsN().length < max && tot('logs') > 0) await set(x, z);
    const held = slotsN().length, logs = tot('logs');
    const unsprung = NORTH.slice(0, max).filter(([x, z]) => dfAt(x, z)?.name === 'hunter_deadfall_set').length;
    const lo = ScriptProvider.getByTrigger(ServerTriggerType.LOGOUT, -1, -1);
    player.executeScript(ScriptRunner.init(lo!, player), true); await waitTicks(3);
    check(slotsN().length === 0, `[logout] frees every slot (${held} held)`);
    check(NORTH.slice(0, max).every(([x, z]) => boulderAt(x, z) !== null), '...every boulder is a boulder again');
    check(tot('logs') === logs + unsprung, `...and each unsprung deadfall's log comes back (${unsprung}: ${logs} -> ${tot('logs')})`);
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

// HTRAP=rellekka: the Rellekka hunting grounds (hunter_rellekka.rs2), at HLEVEL. The map first - every
// spawn, boulder, pit, hole, tunnel, log and drift where it should be, the ground walkable from the pass
// by the Keldagrim entrance, the plateau reached by its steps and back - then each creature the level
// allows, caught off the real loop: a polar kebbit trail to a drift, a cerulean twitch in a snare, a
// sabre-toothed kebbit under a deadfall, a kyatt teased into a pit, and both butterflies netted into jars
// and let out again. Below a creature's level, the gate: nothing comes to that trap, or it refuses.
if (process.env.HTRAP === 'rellekka') {
    const inv0 = player.getInventory(InvType.INV)!;
    const tot = (n: string) => inv0.getItemCount(ObjType.getId(n));
    const cnum = (n: string) => { const m = new RegExp(`\\^${n} = (-?\\d+)`).exec(CONST + RCONST); if (!m) throw new Error(n); return parseInt(m[1]); };
    const setLevel = (l: number) => { player.stats[PlayerStat.HUNTER] = getExpByLevel(l); player.baseLevels[PlayerStat.HUNTER] = l; player.levels[PlayerStat.HUNTER] = l; };
    const xp = () => player.stats[PlayerStat.HUNTER];
    const v = (n: string) => player.getVar(VarPlayerType.getId(n)) as number;
    const slotsN = () => [1, 2, 3, 4, 5].map(i => v(`hunter_trap${i}`)).filter(c => c !== -1);
    const L = (n: string) => LocType.getId(n);
    const run = (trigger: number, id: number, cat: number, target: any) => {
        const script = ScriptProvider.getByTrigger(trigger, id, cat);
        if (!script) { log('no script', trigger, id); return false; }
        player.executeScript(ScriptRunner.init(script, player, target), true);
        return true;
    };
    const oploc = (op: number, loc: any) => { const t = LocType.get(loc.type); return run(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category, loc); };
    const opnpc = (op: number, npc: any) => { const t = NpcType.get(npc.type); return run(ServerTriggerType.OPNPC1 + (op - 1), t.id, t.category, npc); };
    const opheld = (op: number, name: string) => {
        const id = ObjType.getId(name); const slot = inv0.getItemIndex(id);
        if (slot === -1) return false;
        player.lastItem = id; player.lastSlot = slot;
        return run(ServerTriggerType.OPHELD1 + (op - 1), id, ObjType.get(id).category, null);
    };
    const npcsOf = (name: string) => { const id = NpcType.getId(name); const out: any[] = []; for (const n of World.npcs) if (n && n.type === id) out.push(n); return out; };
    const nearest = (name: string, x: number, z: number, lv = 0) => { let b: any = null, bd = 999; for (const n of npcsOf(name)) { if (n.level !== lv) continue; const d = Math.max(Math.abs(n.x - x), Math.abs(n.z - z)); if (d < bd) { bd = d; b = n; } } return b; };
    const scan = (names: string[], lv: number, box = [2688, 3712, 2751, 3839]) => {
        const out: any[] = []; const ids = names.map(L);
        for (let x = box[0]; x <= box[2]; x++) for (let z = box[1]; z <= box[3]; z++) for (const id of ids) { const l = World.getLoc(x, z, lv, id); if (l) out.push(l); }
        return out;
    };
    const { canTravel, isMapBlocked, reachedLoc } = await import('#/engine/GameMap.js');
    const { CollisionType } = await import('#/engine/routefinder/index.js');
    const flood = (lv: number, sx: number, sz: number, box: number[]) => {
        const seen = new Set<string>([`${sx},${sz}`]); const q = [[sx, sz]];
        while (q.length) { const [x, z] = q.shift()!;
            for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const nx = x + dx, nz = z + dz, k = `${nx},${nz}`;
                if (seen.has(k) || nx < box[0] || nx > box[2] || nz < box[1] || nz > box[3]) continue;
                if (!canTravel(lv, x, z, dx, dz, 1, 0, CollisionType.NORMAL)) continue; seen.add(k); q.push([nx, nz]); } }
        return seen;
    };
    // a reachable tile from which the player can operate the loc (as the route finder would end a walk)
    const standFor = (loc: any, seen: Set<string>) => {
        const t = LocType.get(loc.type);
        for (let r = 1; r <= 3; r++) for (let dx = -r; dx <= r + t.width; dx++) for (let dz = -r; dz <= r + t.length; dz++) {
            const x = loc.x + dx, z = loc.z + dz;
            if (!seen.has(`${x},${z}`)) continue;
            if (reachedLoc(loc.level, x, z, loc.x, loc.z, t.width, t.length, 1, loc.angle, loc.shape, t.forceapproach)) return [x, z];
        }
        return null;
    };
    const LANDING = [2715, 3797];
    const BOX0 = [2600, 3640, 2760, 3839];

    // ---------------------------------------------------------------- the map
    const want: Record<string, number> = { hunter_sabretooth_kebbit: 12, hunter_sabretooth_kyatt: 6, hunter_cerulean_twitch: 13, hunter_sapphire_glacialis: 12, hunter_snowy_knight: 9, hunting_expert_rellekka: 1 };
    for (const [n, c] of Object.entries(want)) check(npcsOf(n).length === c, `${c} ${n} in the world (${npcsOf(n).length})`);
    const ground = flood(0, LANDING[0], LANDING[1], BOX0);
    check(ground.has('2725,3720') && ground.has('2700,3710'), `the grounds are walkable from the pass by the Keldagrim entrance and from Rellekka's north-east shore (${ground.size} tiles)`);
    const boulders = scan(['loc474_19205'], 0, [2688, 3740, 2751, 3800]);
    check(boulders.length === 10, `10 deadfall boulders on the ground (${boulders.length})`);
    const pits = scan(['loc474_19227'], 0, [2688, 3776, 2751, 3810]);
    check(pits.length === 6, `6 pits, on the ground floor (linkbelow bridge tiles) (${pits.length})`);
    const unreach = [...boulders, ...pits].filter(l => standFor(l, ground) === null);
    check(unreach.length === 0, `...each one reachable on foot from the ::rellekka landing (${unreach.map(l => `${l.x},${l.z}`).join(' ') || 'all'})`);
    const ascend = scan(['loc474_19690'], 0), descend = scan(['loc474_19691'], 1);
    check(ascend.length === 2 && descend.length === 2, `two flights of steps up to the plateau and two down (${ascend.length}/${descend.length})`);
    // the steps
    let plateau = new Set<string>();
    for (const s of ascend) {
        const st = standFor(s, ground);
        if (!st) { check(false, `steps at ${s.x},${s.z}: no tile to climb them from`); continue; }
        player.teleport(st[0], st[1], 0); await waitTicks(1);
        oploc(1, s); await waitTicks(3);
        const up = player.level === 1 && !isMapBlocked(player.x, player.z, 1);
        check(up, `Ascend the steps at ${s.x},${s.z} from ${st[0]},${st[1]}: on the plateau at ${player.x},${player.z},${player.level}`);
        if (up) plateau = flood(1, player.x, player.z, [2688, 3776, 2751, 3839]);
        const d = descend.find(q => Math.abs(q.x - s.x) <= 1 && Math.abs(q.z - s.z) <= 2);
        const ds = d && standFor(d, plateau);
        if (!d || !ds) { check(false, `...and the steps down beside them are reachable from there`); continue; }
        player.teleport(ds[0], ds[1], 1); await waitTicks(1);
        oploc(1, d); await waitTicks(3);
        check(player.level === 0 && ground.has(`${player.x},${player.z}`), `...Descend comes back down onto the walkable ground (${player.x},${player.z},${player.level})`);
    }
    check(plateau.has('2710,3829'), `the Hunting expert's tile is on the plateau the steps lead to (${plateau.size} tiles)`);
    const NODE = ['loc474_19640', 'loc474_19641', ...[19418, 19419, 19420, 19421, 19422, 19423, 19424, 19425, 19426].map(i => `loc474_${i}`)];
    const nodes = scan(NODE, 1, [2688, 3776, 2751, 3839]);
    const drifts = scan(['loc474_19435'], 1, [2688, 3776, 2751, 3839]);
    check(nodes.length === 11 && drifts.length === 4, `11 holes, tunnels and hollow logs and 4 snow drifts on the plateau (${nodes.length}, ${drifts.length})`);
    const cenum = (name: string) => { const e = (EnumType as any).get(EnumType.getId(name)); return [...e.values.values()].map((c: number) => ({ x: (c >> 14) & 0x3fff, z: c & 0x3fff, y: c >> 28 })); };
    const enodes = cenum('hunter_polar_track_nodes'), edrifts = cenum('hunter_polar_track_drifts');
    check(enodes.length === nodes.length && enodes.every((c: any) => nodes.some(l => l.x === c.x && l.z === c.z)), `every node the trail enum lists has its loc on the map, and every one on the map is listed (${enodes.length})`);
    check(edrifts.length === drifts.length && edrifts.every((c: any) => drifts.some(l => l.x === c.x && l.z === c.z)), `...and the same for the snow drifts (${edrifts.length})`);
    const cantReach = [...nodes, ...drifts].filter(l => standFor(l, plateau) === null);
    check(cantReach.length === 0, `...every one of them reachable on the plateau (${cantReach.map(l => `${l.x},${l.z}`).join(' ') || 'all'})`);
    const opsLive = [...boulders, ...pits, ...nodes, ...drifts, ...ascend, ...descend].filter(l => {
        const t = LocType.get(l.type);
        return (t.op ?? []).some((o: any, i: number) => o && !ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1 + i, t.id, t.category));
    });
    check(opsLive.length === 0, `every op on the grounds' hunter locs has a handler (${opsLive.map(l => LocType.get(l.type).debugname).join(' ') || 'all'})`);

    // ---------------------------------------------------------------- polar kebbit tracking
    player.invAdd(InvType.INV, ObjType.getId('noose_wand'), 1);
    {
        const at = (x: number, z: number) => [...nodes, ...drifts].find(l => l.x === x && l.z === z) ?? null;
        const xz = (c: number) => ({ x: (c >> 14) & 0x3fff, z: c & 0x3fff });
        const dir = (fx: number, fz: number, tx: number, tz: number) => {
            const dx = tx - fx, dz = tz - fz, ax = Math.abs(dx), az = Math.abs(dz);
            const ns = dz > 0 ? 'north' : dz < 0 ? 'south' : '', ew = dx > 0 ? 'east' : dx < 0 ? 'west' : '';
            if (ax > az * 2) return ew; if (az > ax * 2) return ns; if (!ns) return ew; if (!ew) return ns; return `${ns}-${ew}`;
        };
        const op = async (o: number, l: any) => { const st = standFor(l, plateau)!; player.teleport(st[0], st[1], 1); await waitTicks(1); oploc(o, l); await waitTicks(3); };
        const holes = nodes.filter(l => LocType.get(l.type).debugname!.match(/19640|19641/));
        check(holes.length === 2, 'two holes to start a trail from');
        { const n = msgs.length; await op(1, drifts[0]); check(msgs.slice(n).some(m => m.includes('nothing but snow')), 'Search on a drift with no trail finds nothing'); }
        let caught = false, trails = 0, hints = 0, hintsOk = true, wrongOk = false;
        // four trails at least, from both holes, and on until a kebbit is caught
        while ((!caught || trails < 4) && trails < 10) {
            const hole = holes[trails % 2]; trails++;
            let n = msgs.length; await op(1, hole);
            let from = { x: hole.x, z: hole.z };
            for (let hop = 0; hop < 8; hop++) {
                const next = xz(v('hunter_track_next')), end = xz(v('hunter_track_bush'));
                const said = msgs.slice(n).reverse().find(m => m.includes('tracks'));
                hints++; if (!said || !said.includes(dir(from.x, from.z, next.x, next.z))) { hintsOk = false; log('hint', said, from, next); }
                if (next.x === end.x && next.z === end.z) break;
                const l = at(next.x, next.z);
                if (!l) { check(false, `the trail's next step ${next.x},${next.z} has something to inspect`); break; }
                if (!wrongOk) {
                    const other = nodes.find(q => (q.x !== next.x || q.z !== next.z) && !holes.includes(q))!;
                    const m0 = msgs.length; await op(1, other);
                    wrongOk = msgs.slice(m0).some(m => m.includes('find no tracks')) && (v('hunter_track_next') & 0xfffffff) === ((next.x << 14) | next.z);
                    check(wrongOk, 'inspecting the wrong tunnel or log finds no tracks and keeps the trail');
                }
                n = msgs.length; await op(1, l); from = next;
            }
            const end = xz(v('hunter_track_bush')); const d = at(end.x, end.z);
            check(d !== null && LocType.get(d.type).debugname === 'loc474_19435', `trail ${trails} ends at a snow drift (${end.x},${end.z})`);
            if (!d) break;
            if (trails === 1) { const m0 = msgs.length; await op(1, d); check(msgs.slice(m0).some(m => m.includes('polar kebbit hiding')), '...Search on it finds the polar kebbit'); }
            const b = { bones: tot('bones'), fur: tot('polar_kebbit_fur'), xp: xp() };
            await op(2, d); await waitTicks(3);
            if (tot('polar_kebbit_fur') > b.fur) {
                caught = true;
                check(tot('bones') === b.bones + 1, '...Attack with the noose wand: a polar kebbit - bones and polar kebbit fur');
                check(xp() - b.xp === cnum('hunter_polar_kebbit_xp'), `...${(xp() - b.xp) / 10} xp`);
            }
            check(v('hunter_track_next') === -1, `...and the trail is spent either way (trail ${trails})`);
        }
        check(caught, `a polar kebbit caught within 10 trails (${trails})`);
        check(hintsOk, `every hint named the real direction of the next step (${hints})`);
    }

    // ---------------------------------------------------------------- butterflies, netted into jars
    {
        player.invAdd(InvType.INV, ObjType.getId('net'), 1);
        const NETID = ObjType.getId('net');
        for (const [npcName, jar, key] of [['hunter_sapphire_glacialis', 'sapphire_glacialis', 'glacialis'], ['hunter_snowy_knight', 'snowy_knight', 'snowyknight']]) {
            const lvl = cnum(`hunter_${key}_level`);
            if (tot('hunter_butterfly_jar') === 0) player.invAdd(InvType.INV, ObjType.getId('hunter_butterfly_jar'), 1);
            let got = false, tries = 0, refused = false;
            for (; tries < 40 && !got; tries++) {
                const b = npcsOf(npcName).find((n: any) => n.isActive)!;
                if (!b) { await waitTicks(10); continue; }
                player.teleport(b.x, b.z - 1 < 0 ? b.z + 1 : b.z - 1, b.level); await waitTicks(1);
                const b0 = { j: tot(jar), xp: xp() }; const n0 = msgs.length;
                player.lastUseItem = NETID; player.lastUseSlot = inv0.getItemIndex(NETID);
                run(ServerTriggerType.OPNPCU, b.type, NpcType.get(b.type).category, b); await waitTicks(4);
                // the refusal is a mesbox, not a chat line: what shows it is that nothing was caught or paid
                if (LEVEL < lvl) { refused = tot(jar) === b0.j && xp() === b0.xp && b.isActive && !msgs.slice(n0).some(m => m.includes('swing the net')); break; }
                if (tot(jar) > b0.j) { got = true; check(xp() - b0.xp === cnum(`hunter_${key}_xp`) && tot('hunter_butterfly_jar') === 0, `a ${jar} netted into its jar (${tries + 1} swings), ${(xp() - b0.xp) / 10} xp`); }
            }
            if (LEVEL < lvl) { check(refused, `below Hunter ${lvl} a ${jar} cannot be netted`); continue; }
            check(got, `a ${jar} caught within 40 swings`);
            if (!got) continue;
            if (jar === 'snowy_knight') {
                player.levels[3] = Math.max(1, player.baseLevels[3] - 20); const hp = player.levels[3];
                opheld(4, jar); await waitTicks(1);
                check(player.levels[3] === Math.min(player.baseLevels[3], hp + cnum('hunter_snowyknight_heal')) && tot(jar) === 0 && tot('hunter_butterfly_jar') === 1, `Release: the snowy knight heals ${cnum('hunter_snowyknight_heal')} (${hp} -> ${player.levels[3]}) and the jar comes back`);
            } else {
                const def = player.levels[1];
                opheld(4, jar); await waitTicks(1);
                const want = player.baseLevels[1] + 4 + Math.floor(player.baseLevels[1] * 15 / 100);
                check(player.levels[1] === want && tot(jar) === 0 && tot('hunter_butterfly_jar') === 1, `Release: the sapphire glacialis boosts Defence by 4 + 15% (${def} -> ${player.levels[1]}) and the jar comes back`);
                player.levels[1] = player.baseLevels[1];
            }
        }
    }

    // ---------------------------------------------------------------- bird snares: cerulean twitches
    {
        const TW = cnum('hunter_twitch_level');
        const S = ['hunter_snare_laid', 'hunter_snare_springing', 'hunter_snare_collapsed', 'hunter_snare_catching_twitch', 'hunter_snare_caught_twitch', 'hunter_snare_catching_swift', 'hunter_snare_caught_swift'];
        const snAt = (x: number, z: number) => { for (const n of S) { const l = World.getLoc(x, z, 0, L(n)); if (l) return { n, l }; } return null; };
        if (tot('hunter_bird_snare') < 5) player.invAdd(InvType.INV, ObjType.getId('hunter_bird_snare'), 5 - tot('hunter_bird_snare'));
        const max = Math.min(5, 1 + Math.floor(LEVEL / 20));
        // open ground tiles beside the ground twitches' spawns
        const spots: number[][] = [];
        for (const [x, z] of [[2716, 3775], [2727, 3772], [2719, 3769], [2731, 3767], [2733, 3775]]) {
            for (const [dx, dz] of [[1, 0], [0, 1], [-1, 0], [0, -1], [1, 1]]) { const k = `${x + dx},${z + dz}`; if (ground.has(k) && !spots.some(s => s[0] === x + dx && s[1] === z + dz)) { spots.push([x + dx, z + dz]); break; } }
        }
        for (const [x, z] of spots) { if (slotsN().length >= max) break; player.teleport(x, z, 0); await waitTicks(1); opheld(1, 'hunter_bird_snare'); await waitTicks(6); }
        check(slotsN().length === max, `${max} bird snares laid among the cerulean twitches (${slotsN().length})`);
        const home = spots[0];
        let caught: any = null; const seen = new Map<string, string>();
        for (let t = 0; t < (LEVEL >= TW ? 900 : 300) && !caught; t++) {
            await waitTicks(1);
            for (const c of slotsN()) {
                const x = (c >> 14) & 0x3fff, z = c & 0x3fff; const s = snAt(x, z)?.n ?? '(none)';
                if (seen.get(`${x},${z}`) !== s) { log('snare', x, z, '->', s); seen.set(`${x},${z}`, s); }
                if (s === 'hunter_snare_caught_twitch' || s === 'hunter_snare_caught_swift') { caught = { x, z, s }; break; }
                if (s === 'hunter_snare_collapsed') { oploc(1, snAt(x, z)!.l); await waitTicks(2); player.teleport(x, z, 0); await waitTicks(1); opheld(1, 'hunter_bird_snare'); await waitTicks(6); player.teleport(home[0], home[1], 0); }
            }
        }
        if (LEVEL >= TW) {
            check(caught?.s === 'hunter_snare_caught_twitch', `a cerulean twitch caught within 900 ticks (${caught?.s ?? 'none'})`);
            if (caught) {
                const b = { bones: tot('bones'), meat: tot('raw_bird_meat'), f: tot('blue_feather'), xp: xp(), sn: tot('hunter_bird_snare') };
                player.teleport(caught.x, caught.z, 0); await waitTicks(1);
                oploc(1, snAt(caught.x, caught.z)!.l); await waitTicks(3);
                check(tot('bones') === b.bones + 1 && tot('raw_bird_meat') === b.meat + 1 && tot('blue_feather') === b.f + cnum('hunter_bird_feathers') && tot('hunter_bird_snare') === b.sn + 1,
                    `...Check: bones, raw bird meat, ${cnum('hunter_bird_feathers')} blue feathers and the snare back`);
                check(xp() - b.xp === cnum('hunter_twitch_xp'), `...${(xp() - b.xp) / 10} xp`);
            }
        } else check(caught === null, `at level ${LEVEL}, below the twitch's ${TW}, nothing flies into a snare`);
        const lo = ScriptProvider.getByTrigger(ServerTriggerType.LOGOUT, -1, -1);
        player.executeScript(ScriptRunner.init(lo!, player), true); await waitTicks(2);
        check(slotsN().length === 0, '[logout] takes every snare up');
    }

    // ---------------------------------------------------------------- deadfalls: sabre-toothed kebbits
    {
        const KL = cnum('hunter_sabretooth_kebbit_level');
        const DF = ['hunter_deadfall_set', 'hunter_deadfall_collapsed', 'hunter_deadfall_sabretooth', 'hunter_deadfall_wild', 'hunter_deadfall_barbtailed'];
        const dfAt = (x: number, z: number) => { for (const n of DF) { const l = World.getLoc(x, z, 0, L(n)); if (l) return { n, l }; } return null; };
        const boulderAt = (x: number, z: number) => World.getLoc(x, z, 0, L('loc474_19205'));
        player.invAdd(InvType.INV, ObjType.getId('knife'), 1);
        player.invAdd(InvType.INV, ObjType.getId('logs'), 10);
        const max = Math.min(5, 1 + Math.floor(LEVEL / 20));
        const use = boulders.slice(0, max);
        const set = async (b: any) => { const st = standFor(b, ground)!; player.teleport(st[0], st[1], 0); await waitTicks(1); oploc(1, boulderAt(b.x, b.z)); await waitTicks(5); };
        for (const b of use) await set(b);
        if (LEVEL < cnum('hunter_deadfall_level')) {
            check(slotsN().length === 0 && use.every(b => boulderAt(b.x, b.z) !== null), `below Hunter ${cnum('hunter_deadfall_level')} no deadfall can be set`);
        } else {
        check(slotsN().length === max && use.every(b => dfAt(b.x, b.z) !== null), `${max} deadfalls set on the boulders (${slotsN().length})`);
        const home = standFor(use[0], ground)!;
        player.teleport(home[0], home[1], 0);
        let caught: any = null; const seen = new Map<string, string>();
        for (let t = 0; t < (LEVEL >= KL ? 1200 : 300) && !caught; t++) {
            await waitTicks(1);
            for (const b of use) {
                const s = dfAt(b.x, b.z)?.n ?? (boulderAt(b.x, b.z) ? 'boulder' : '(none)');
                if (seen.get(`${b.x},${b.z}`) !== s) { log('deadfall', b.x, b.z, '->', s); seen.set(`${b.x},${b.z}`, s); }
                if (s === 'hunter_deadfall_sabretooth' || s === 'hunter_deadfall_wild' || s === 'hunter_deadfall_barbtailed') { caught = { b, s }; break; }
                if (s === 'hunter_deadfall_collapsed') { oploc(1, dfAt(b.x, b.z)!.l); await waitTicks(3); await set(b); player.teleport(home[0], home[1], 0); }
                if (s === 'boulder' && tot('logs') > 0) { await set(b); player.teleport(home[0], home[1], 0); }
            }
        }
        if (LEVEL >= KL) {
            check(caught?.s === 'hunter_deadfall_sabretooth', `a sabre-toothed kebbit caught under a deadfall within 1200 ticks (${caught?.s ?? 'none'})`);
            if (caught) {
                const b = { bones: tot('bones'), teeth: tot('kebbit_teeth'), logs: tot('logs'), xp: xp() };
                oploc(1, dfAt(caught.b.x, caught.b.z)!.l); await waitTicks(3);
                check(tot('bones') === b.bones + 1 && tot('kebbit_teeth') === b.teeth + 1 && tot('logs') === b.logs, '...Check: bones and kebbit teeth, and no log back');
                check(xp() - b.xp === cnum('hunter_sabretooth_kebbit_xp'), `...${(xp() - b.xp) / 10} xp`);
                check(boulderAt(caught.b.x, caught.b.z) !== null, '...and the boulder is a boulder again');
            }
        } else check(caught === null, `at level ${LEVEL}, below the sabre-toothed kebbit's ${KL}, nothing comes to a deadfall here`);
        const lo = ScriptProvider.getByTrigger(ServerTriggerType.LOGOUT, -1, -1);
        player.executeScript(ScriptRunner.init(lo!, player), true); await waitTicks(3);
        check(slotsN().length === 0 && use.every(b => boulderAt(b.x, b.z) !== null), '[logout] frees every slot and hands every boulder back');
        }
    }

    // ---------------------------------------------------------------- pitfalls: sabre-toothed kyatts
    {
        const KY = cnum('hunter_kyatt_level');
        const ST = ['hunter_pit_spiked', 'hunter_pit_collapsed', 'hunter_pit_kyatt', 'hunter_pit_larupia'];
        const pitAt = (p: any) => { for (const n of ST) { const l = World.getLoc(p.x, p.z, 0, L(n)); if (l) return { n, l }; } return null; };
        const plain = (p: any) => World.getLoc(p.x, p.z, 0, L('loc474_19227'));
        player.invAdd(InvType.INV, ObjType.getId('teasing_stick'), 1);
        if (tot('logs') < 15) player.invAdd(InvType.INV, ObjType.getId('logs'), 15 - tot('logs'));
        // each pit's take-off tiles: open ground straight beside it with open ground 2-4 tiles on past it
        const takeoffs = (p: any) => {
            const out: any[] = [];
            for (const [dx, dz] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
                const sx = p.x - dx, sz = p.z - dz;
                if (!ground.has(`${sx},${sz}`)) continue;
                for (let k = 2; k <= 4; k++) { const lx = sx + dx * k, lz = sz + dz * k; if (!isMapBlocked(lx, lz, 0)) { out.push({ sx, sz, lx, lz }); break; } }
            }
            return out;
        };
        const noTake = pits.filter(p => takeoffs(p).length === 0);
        check(noTake.length === 0, `every pit has a take-off tile and a landing past it (${noTake.map(p => `${p.x},${p.z}`).join(' ') || 'all'})`);
        const kyattOf = (t: any) => nearest('hunter_sabretooth_kyatt', t.sx, t.sz);
        // the kyatts near a take-off tile, nearest home first: a player picks which one to tease
        const kyattsFor = (t: any) => npcsOf('hunter_sabretooth_kyatt').filter((k: any) => Math.max(Math.abs(k.startX - t.sx), Math.abs(k.startZ - t.sz)) <= 10)
            .sort((a: any, b: any) => Math.max(Math.abs(a.startX - t.sx), Math.abs(a.startZ - t.sz)) - Math.max(Math.abs(b.startX - t.sx), Math.abs(b.startZ - t.sz)));
        const home = (k: any) => { k.targetOp = 0; k.teleport(k.startX, k.startZ, 0); };
        if (LEVEL < KY) {
            const p = pits[0], t = takeoffs(p)[0];
            player.teleport(t.sx, t.sz, 0); await waitTicks(1);
            const n = msgs.length; opnpc(1, kyattOf(t)); await waitTicks(2);
            check(v('hunter_tease_npc') === -1, `below Hunter ${KY} a kyatt cannot be teased`);
        } else {
            // every pit: its nearest kyatt, teased from the take-off tile, comes to heel
            const follows: string[] = [], stuck: string[] = []; const pair = new Map<any, any>();
            for (const p of pits) {
                let ok = false;
                for (const t of takeoffs(p)) {
                    for (const k of kyattsFor(t)) {
                        home(k); player.teleport(t.sx, t.sz, 0); await waitTicks(1);
                        opnpc(1, k); await waitTicks(10);
                        const came = Math.max(Math.abs(k.x - t.sx), Math.abs(k.z - t.sz)) <= cnum('hunter_pit_reach');
                        home(k); player.setVar(VarPlayerType.getId('hunter_tease_npc'), -1);
                        if (came) { ok = true; pair.set(p, { t, k }); break; }
                        log('kyatt did not come', p.x, p.z, 'takeoff', t.sx, t.sz, 'kyatt from', k.startX, k.startZ);
                    }
                    if (ok) break;
                }
                (ok ? follows : stuck).push(`${p.x},${p.z}${ok ? ` (from ${pair.get(p).k.startX},${pair.get(p).k.startZ})` : ''}`);
                player.teleport(LANDING[0], LANDING[1], 0); await waitTicks(2);
            }
            check(stuck.length === 0, `at every pit a kyatt teased from a take-off tile follows to it: ${follows.join(', ')}${stuck.length ? '; not: ' + stuck.join(' ') : ''}`);
            let fell: any = null;
            const usable = pits.filter(p => pair.has(p));
            for (let attempt = 0; attempt < 16 && !fell && usable.length; attempt++) {
                const p = usable[attempt % usable.length]; const { t, k: kk } = pair.get(p);
                player.teleport(t.sx, t.sz, 0); await waitTicks(1);
                if (pitAt(p)?.n === 'hunter_pit_collapsed') { oploc(2, pitAt(p)!.l); await waitTicks(2); }
                if (!pitAt(p)) { oploc(3, plain(p)); await waitTicks(5); }
                if (pitAt(p)?.n !== 'hunter_pit_spiked') { log('pit not spiked', p.x, p.z, pitAt(p)?.n); continue; }
                const k = kk; if (!k.isActive) { await waitTicks(60); continue; }
                home(k); await waitTicks(1);
                opnpc(1, k); await waitTicks(8);
                player.teleport(t.sx, t.sz, 0); await waitTicks(1);
                oploc(1, pitAt(p)!.l); await waitTicks(4);
                log('jump', attempt, p.x, p.z, '->', pitAt(p)?.n, 'player', player.x, player.z);
                if (pitAt(p)?.n === 'hunter_pit_kyatt') fell = p;
            }
            check(fell !== null, 'a kyatt followed the jump into a pit within 16 tries');
            if (fell) {
                const b = { bones: tot('big_bones'), fur: tot('kyatt_fur'), logs: tot('logs'), xp: xp() };
                oploc(2, pitAt(fell)!.l); await waitTicks(2);
                check(tot('big_bones') === b.bones + 1 && tot('kyatt_fur') === b.fur + 1 && tot('logs') === b.logs, '...Dismantle: big bones and kyatt fur, no log back');
                check(xp() - b.xp === cnum('hunter_kyatt_xp'), `...${(xp() - b.xp) / 10} xp`);
                check(plain(fell) !== null, '...and the pit is a pit again');
            }
            const lo = ScriptProvider.getByTrigger(ServerTriggerType.LOGOUT, -1, -1);
            player.executeScript(ScriptRunner.init(lo!, player), true); await waitTicks(3);
            check(slotsN().length === 0 && pits.every(p => plain(p) !== null), '[logout] frees every slot and hands every pit back');
        }
    }

    // ---------------------------------------------------------------- the expert, the guide
    {
        const ex = npcsOf('hunting_expert_rellekka')[0];
        check(ex && ScriptProvider.getByTrigger(ServerTriggerType.OPNPC1, ex.type, NpcType.get(ex.type).category) !== undefined && ex.level === 1, 'the plateau Hunting expert stands on level 1 and has something to say');
    }
    console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
    process.exit(fails ? 1 : 0);
}

const TRAP = ObjType.getId(TRAPNAME);
const inv = player.getInventory(InvType.INV)!;
const total = (name: string) => inv.getItemCount(ObjType.getId(name));
player.invAdd(InvType.INV, TRAP, 5);
check(total(TRAPNAME) === 5, `five ${TRAPNAME} in the pack`);

const TYPES = ['hunter_boxtrap_laid', 'hunter_boxtrap_collapsed', 'hunter_boxtrap_catching_chinchompa', 'hunter_boxtrap_catching_chinchompa_red',
    'hunter_boxtrap_catching_ferret', 'hunter_boxtrap_shaking_chinchompa', 'hunter_boxtrap_shaking_chinchompa_red', 'hunter_boxtrap_shaking_ferret',
    'hunter_snare_laid', 'hunter_snare_springing', 'hunter_snare_collapsed', 'hunter_snare_catching_swift', 'hunter_snare_catching_wagtail',
    'hunter_snare_caught_swift', 'hunter_snare_caught_wagtail'];
const typeIds = TYPES.map(t => LocType.getId(t));
const locAt = (x: number, z: number) => {
    for (let i = 0; i < typeIds.length; i++) {
        const l = World.getLoc(x, z, 0, typeIds[i]);
        if (l) return { name: TYPES[i], loc: l };
    }
    return null;
};
const slots = () => [1, 2, 3, 4, 5].map(i => player.getVar(VarPlayerType.getId(`hunter_trap${i}`)) as number);
const coordXZ = (c: number) => ({ x: (c >> 14) & 0x3fff, z: c & 0x3fff });

function opheld1(objName: string) {
    const id = ObjType.getId(objName);
    const slot = inv.getItemIndex(id);
    // OpHeldHandler refuses an op on an item that is not in the slot; so must this, or it lays traps
    // out of an empty pack.
    if (slot === -1) { log('opheld1: no', objName, 'in the pack'); return; }
    player.lastItem = id; player.lastSlot = slot;
    const script = ScriptProvider.getByTrigger(ServerTriggerType.OPHELD1, id, ObjType.get(id).category);
    player.executeScript(ScriptRunner.init(script!, player), true);
}
function oploc(op: number, loc: any) {
    const t = LocType.get(loc.type);
    const script = ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category);
    player.executeScript(ScriptRunner.init(script!, player, loc), true);
}

// ---- 1. limits and laying
// Open tiles beside the grey chinchompas' spawns (checked against the engine's own collision). A
// tile the game refuses - a fern is active and so blocks loc_add - is skipped, not counted.
const max = Math.min(5, 1 + Math.floor(LEVEL / 20));
const CANDIDATES = SNARE
    ? [[2597, 2884], [2599, 2884], [2601, 2884], [2597, 2886], [2599, 2886], [2601, 2886], [2595, 2884], [2603, 2884], [2595, 2886], [2603, 2886]]
    : [[2560, 2891], [2562, 2891], [2564, 2891], [2558, 2891], [2566, 2891], [2560, 2889], [2562, 2889], [2558, 2889], [2556, 2891], [2568, 2891]];
const HOME = CANDIDATES[0];
let refusedTile = 0;
for (const [x, z] of CANDIDATES) {
    if (slots().filter(c => c !== -1).length >= max) break;
    player.teleport(x, z, 0);
    await waitTicks(2);
    const n = msgs.length;
    opheld1(TRAPNAME);
    await waitTicks(6);
    if (msgs.slice(n).some(m => m.includes("can't lay a trap here"))) refusedTile++;
}
log('tiles refused', refusedTile);
{
    const n = msgs.length;
    player.teleport(SNARE ? 2605 : 2570, SNARE ? 2888 : 2891, 0); await waitTicks(2);
    opheld1(TRAPNAME); await waitTicks(6);
    check(msgs.slice(n).some(m => m.includes('more than')), `a trap over the limit of ${max} is refused`);
}
const laid = slots().filter(c => c !== -1);
check(laid.length === max, `laid exactly ${max} traps at level ${LEVEL} (${laid.length})`);
check(total(TRAPNAME) === 5 - max, `${5 - max} traps left in the pack (${total(TRAPNAME)})`);
for (const c of laid) {
    const { x, z } = coordXZ(c);
    check(locAt(x, z) !== null, `a trap stands at ${x},${z} (${locAt(x, z)?.name})`);
}

// ---- 2. the loop, watched
const seen = new Map<string, string>();
const firstShaking: any[] = [];
for (let t = 0; t < (CAN_CATCH ? 600 : 300) && firstShaking.length === 0; t++) {
    await waitTicks(1);
    for (const c of slots()) {
        if (c === -1) continue;
        const { x, z } = coordXZ(c);
        const s = locAt(x, z)?.name ?? '(none)';
        const k = `${x},${z}`;
        if (seen.get(k) !== s) { log('trap', k, '->', s); seen.set(k, s); }
        if (s.startsWith('hunter_boxtrap_shaking') || s.startsWith('hunter_snare_caught')) firstShaking.push({ x, z, s });
        if (s === 'hunter_boxtrap_collapsed') {
            const l = locAt(x, z)!.loc;
            oploc(2, l); // Reset
            await waitTicks(5);
            check(locAt(x, z)?.name === 'hunter_boxtrap_laid', `Reset on the collapsed trap at ${k} lays it again`);
        }
        if (s === 'hunter_snare_collapsed') {
            // A collapsed snare has no Reset, only Dismantle - then it is laid again on the same tile.
            const before = total(TRAPNAME), held = slots().filter(c => c !== -1).length;
            oploc(1, locAt(x, z)!.loc);
            await waitTicks(2);
            check(locAt(x, z) === null && total(TRAPNAME) === before + 1 && slots().filter(c => c !== -1).length === held - 1,
                `Dismantle on the collapsed snare at ${k} takes it up and frees its slot`);
            player.teleport(x, z, 0); await waitTicks(2);
            opheld1(TRAPNAME); await waitTicks(6);
        }
    }
}
if (CAN_CATCH) check(firstShaking.length > 0, 'something was caught within 600 ticks');
else {
    check(firstShaking.length === 0, `at level ${LEVEL}, below the ${GATE_NAME}'s ${GREY}, nothing in their clearing goes in`);
    // 300 ticks untouched is past ^hunter_trap_duration, so the expiry path has run too.
    check(slots().every(c => c === -1), '...and traps left untouched past their duration fall over and free their slots');
    check(msgs.some(m => m.includes('fallen over')), '...with a message');
    player.teleport(HOME[0], HOME[1], 0); await waitTicks(2);
    opheld1(TRAPNAME); await waitTicks(6);
}

// ---- 3. Check
if (firstShaking.length) {
    const { x, z, s } = firstShaking[0];
    const LOOT = ['chinchompa', 'red_chinchompa', 'ferret', 'bones', 'raw_bird_meat', 'red_feather', 'stripy_feather'];
    const before: any = { trap: total(TRAPNAME), xp: player.stats[PlayerStat.HUNTER] };
    for (const n of LOOT) before[n] = total(n);
    const slotsBefore = slots().filter(c => c !== -1).length;
    oploc(1, locAt(x, z)!.loc);
    await waitTicks(2);
    check(locAt(x, z) === null, `Check removes the ${s}`);
    check(total(TRAPNAME) === before.trap + 1, '...gives the trap back');
    const got = Object.fromEntries(LOOT.map(n => [n, total(n) - before[n]]).filter(([, d]) => d !== 0));
    if (SNARE) {
        const feather = s.endsWith('swift') ? 'red_feather' : 'stripy_feather';
        const n = parseInt(/\^hunter_bird_feathers = (\d+)/.exec(CONST)![1]);
        check(JSON.stringify(got) === JSON.stringify({ bones: 1, raw_bird_meat: 1, [feather]: n }),
            `...pays bones, raw bird meat and ${n} ${feather}, and nothing else (${JSON.stringify(got)})`);
    } else {
        check(Object.values(got).reduce((a: number, b: any) => a + b, 0) === 1 && ['chinchompa', 'red_chinchompa', 'ferret'].includes(Object.keys(got)[0]),
            `...gives exactly one animal (${JSON.stringify(got)})`);
    }
    check(player.stats[PlayerStat.HUNTER] > before.xp, `...and experience (+${(player.stats[PlayerStat.HUNTER] - before.xp) / 10})`);
    check(slots().filter(c => c !== -1).length === slotsBefore - 1, '...and frees the slot');
}

// ---- 4. somebody else's trap
{
    const c = slots().find(c => c !== -1)!;
    const { x, z } = coordXZ(c);
    const vid = VarPlayerType.getId(`hunter_trap${slots().indexOf(c) + 1}`);
    // The slot is blanked only around the click itself, which runs synchronously: if a tick passed
    // with it blank, the owner's timer would count no traps, stop itself (as it should when the
    // last trap goes), and nothing would restart it for the traps restored after.
    const n = msgs.length;
    const l = locAt(x, z)!.loc;
    player.setVar(vid, -1);
    oploc(1, l);
    player.setVar(vid, c);
    await waitTicks(2);
    check(msgs.slice(n).some(m => m.includes("isn't your trap")), "a trap not in your varps is not yours");
    check(locAt(x, z) !== null, '...and is left where it is');
}

// ---- 5. walk away: the leash
{
    const held = slots().filter(c => c !== -1);
    const trapsBefore = total(TRAPNAME);
    player.teleport(2570, 2887 + 30, 0);
    await waitTicks(6);
    check(slots().every(c => c === -1), 'walking 30 tiles away collapses every trap and frees every slot');
    for (const c of held) {
        const { x, z } = coordXZ(c);
        check(locAt(x, z) === null, `...the loc at ${x},${z} is gone`);
    }
    check(total(TRAPNAME) === trapsBefore, '...and the traps are on the ground, not in the pack');
    check(msgs.some(m => m.includes('moved too far away')), '...with a message');
}

// ---- 6. logout gives them back
{
    player.teleport(HOME[0], HOME[1], 0);
    await waitTicks(3);
    if (total(TRAPNAME) < 2) player.invAdd(InvType.INV, TRAP, 2 - total(TRAPNAME));
    // In snare mode the second trap is a BOX trap, so [logout] has to hand back one of each - which
    // only works if the slot remembered its kind (%hunter_trap_kinds).
    const OTHER = SNARE ? 'hunter_box_trap' : TRAPNAME;
    // A box trap needs Hunter 27 (refused with a mesbox, which is not a chat line), and level 10
    // only allows one trap - so the snare passes step up to 40 for this.
    if (SNARE) { player.stats[PlayerStat.HUNTER] = getExpByLevel(40); player.baseLevels[PlayerStat.HUNTER] = 40; player.levels[PlayerStat.HUNTER] = 40; }
    if (SNARE && total(OTHER) < 1) player.invAdd(InvType.INV, ObjType.getId(OTHER), 1);
    const before = total(TRAPNAME), beforeOther = total(OTHER);
    opheld1(TRAPNAME); await waitTicks(6);
    opheld1(OTHER); await waitTicks(6);
    const held = slots().filter(c => c !== -1);
    check(held.length === 2, SNARE ? 'a snare and a box trap laid side by side' : 'two laid again');
    const script = ScriptProvider.getByTrigger(ServerTriggerType.LOGOUT, -1, -1);
    player.executeScript(ScriptRunner.init(script!, player), true);
    await waitTicks(2);
    check(slots().every(c => c === -1), '[logout] frees every slot');
    for (const c of held) { const { x, z } = coordXZ(c); check(locAt(x, z) === null, `...and takes up the trap at ${x},${z}`); }
    check(total(TRAPNAME) === before && (!SNARE || total(OTHER) === beforeOther),
        `...and puts each back in the pack as what it was (${TRAPNAME} ${total(TRAPNAME)}/${before}${SNARE ? `, ${OTHER} ${total(OTHER)}/${beforeOther}` : ''})`);
}

console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
process.exit(fails ? 1 : 0);
