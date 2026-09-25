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
