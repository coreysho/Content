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
const PlayerStat = { HUNTER: 22 };
import { getExpByLevel } from '#/engine/entity/Player.js';

// The login/friend/logger worker threads cannot resolve '#/' imports outside the app's own launch;
// this test needs none of them, so their failures are swallowed rather than allowed to end the process.
for (const k of ['loginThread', 'friendThread', 'loggerThread']) (World as any)[k]?.on?.('error', () => {});

const LEVEL = parseInt(process.env.HLEVEL ?? '70');
const CONST = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter.constant`, 'utf8');
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
