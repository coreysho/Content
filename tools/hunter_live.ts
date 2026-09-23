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
const PlayerStat = { HUNTER: 22 };
import { getExpByLevel } from '#/engine/entity/Player.js';

// The login/friend/logger worker threads cannot resolve '#/' imports outside the app's own launch;
// this test needs none of them, so their failures are swallowed rather than allowed to end the process.
for (const k of ['loginThread', 'friendThread', 'loggerThread']) (World as any)[k]?.on?.('error', () => {});

const LEVEL = parseInt(process.env.HLEVEL ?? '70');
const CONST = fs.readFileSync(`${process.env.BUILD_SRC_DIR}/scripts/skill_hunter/configs/hunter.constant`, 'utf8');
const GREY = parseInt(/\^hunter_chinchompa_level = (\d+)/.exec(CONST)![1]);
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
const TRAP = ObjType.getId('hunter_box_trap');
const inv = player.getInventory(InvType.INV)!;
const total = (name: string) => inv.getItemCount(ObjType.getId(name));
player.invAdd(InvType.INV, TRAP, 5);
check(total('hunter_box_trap') === 5, 'five box traps in the pack');

const TYPES = ['hunter_boxtrap_laid', 'hunter_boxtrap_collapsed', 'hunter_boxtrap_catching_chinchompa', 'hunter_boxtrap_catching_chinchompa_red',
    'hunter_boxtrap_catching_ferret', 'hunter_boxtrap_shaking_chinchompa', 'hunter_boxtrap_shaking_chinchompa_red', 'hunter_boxtrap_shaking_ferret'];
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
const CANDIDATES = [[2560, 2891], [2562, 2891], [2564, 2891], [2558, 2891], [2566, 2891], [2560, 2889], [2562, 2889], [2558, 2889], [2556, 2891], [2568, 2891]];
let refusedTile = 0;
for (const [x, z] of CANDIDATES) {
    if (slots().filter(c => c !== -1).length >= max) break;
    player.teleport(x, z, 0);
    await waitTicks(2);
    const n = msgs.length;
    opheld1('hunter_box_trap');
    await waitTicks(6);
    if (msgs.slice(n).some(m => m.includes("can't lay a trap here"))) refusedTile++;
}
log('tiles refused', refusedTile);
{
    const n = msgs.length;
    player.teleport(2570, 2891, 0); await waitTicks(2);
    opheld1('hunter_box_trap'); await waitTicks(6);
    check(msgs.slice(n).some(m => m.includes('more than')), `a trap over the limit of ${max} is refused`);
}
const laid = slots().filter(c => c !== -1);
check(laid.length === max, `laid exactly ${max} traps at level ${LEVEL} (${laid.length})`);
check(total('hunter_box_trap') === 5 - max, `${5 - max} traps left in the pack (${total('hunter_box_trap')})`);
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
        if (s.startsWith('hunter_boxtrap_shaking')) firstShaking.push({ x, z, s });
        if (s === 'hunter_boxtrap_collapsed') {
            const l = locAt(x, z)!.loc;
            oploc(2, l); // Reset
            await waitTicks(5);
            check(locAt(x, z)?.name === 'hunter_boxtrap_laid', `Reset on the collapsed trap at ${k} lays it again`);
        }
    }
}
if (CAN_CATCH) check(firstShaking.length > 0, 'something was caught within 600 ticks');
else {
    check(firstShaking.length === 0, `at level ${LEVEL}, below the grey chinchompa's ${GREY}, nothing in their clearing goes in`);
    // 300 ticks untouched is past ^hunter_trap_duration, so the expiry path has run too.
    check(slots().every(c => c === -1), '...and traps left untouched past their duration fall over and free their slots');
    check(msgs.some(m => m.includes('fallen over')), '...with a message');
    player.teleport(2560, 2891, 0); await waitTicks(2);
    opheld1('hunter_box_trap'); await waitTicks(6);
}

// ---- 3. Check
if (firstShaking.length) {
    const { x, z, s } = firstShaking[0];
    const before = { trap: total('hunter_box_trap'), grey: total('chinchompa'), red: total('red_chinchompa'), ferret: total('ferret'), xp: player.stats[PlayerStat.HUNTER] };
    const slotsBefore = slots().filter(c => c !== -1).length;
    oploc(1, locAt(x, z)!.loc);
    await waitTicks(2);
    check(locAt(x, z) === null, 'Check removes the shaking box');
    check(total('hunter_box_trap') === before.trap + 1, '...gives the trap back');
    const got = total('chinchompa') - before.grey + total('red_chinchompa') - before.red + total('ferret') - before.ferret;
    check(got === 1, `...gives exactly one catch (${s})`);
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
    const trapsBefore = total('hunter_box_trap');
    player.teleport(2570, 2887 + 30, 0);
    await waitTicks(6);
    check(slots().every(c => c === -1), 'walking 30 tiles away collapses every trap and frees every slot');
    for (const c of held) {
        const { x, z } = coordXZ(c);
        check(locAt(x, z) === null, `...the loc at ${x},${z} is gone`);
    }
    check(total('hunter_box_trap') === trapsBefore, '...and the traps are on the ground, not in the pack');
    check(msgs.some(m => m.includes('moved too far away')), '...with a message');
}

// ---- 6. logout gives them back
{
    player.teleport(2560, 2891, 0);
    await waitTicks(3);
    if (total('hunter_box_trap') < 2) player.invAdd(InvType.INV, TRAP, 2 - total('hunter_box_trap'));
    const before = total('hunter_box_trap');
    opheld1('hunter_box_trap'); await waitTicks(6);
    opheld1('hunter_box_trap'); await waitTicks(6);
    const held = slots().filter(c => c !== -1);
    check(held.length === 2, 'two laid again');
    const script = ScriptProvider.getByTrigger(ServerTriggerType.LOGOUT, -1, -1);
    player.executeScript(ScriptRunner.init(script!, player), true);
    await waitTicks(2);
    check(slots().every(c => c === -1), '[logout] frees every slot');
    for (const c of held) { const { x, z } = coordXZ(c); check(locAt(x, z) === null, `...and takes up the trap at ${x},${z}`); }
    check(total('hunter_box_trap') === before, `...and puts them back in the pack (${total('hunter_box_trap')}/${before})`);
}

console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
process.exit(fails ? 1 : 0);
