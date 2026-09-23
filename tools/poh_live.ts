// Live test of house guests (skill_construction/scripts/poh_guests.rs2) against the real engine and
// the real compiled scripts: two socketless players, the owner in their house and a friend coming in
// through the town portal's Friend's house. Run it through tools/poh_live_battery.py, which puts it
// inside the engine and takes it out.
//
// What a compile cannot see and this does: findname finding the owner, the guest landing in the
// owner's instance, and the guest being put outside the portal - not left in the void - when the
// house goes (Expel Guests, the owner leaving) and when they leave by the exit portal themselves.
import World from '#/engine/World.js';
import { PlayerLoading } from '#/engine/entity/PlayerLoading.js';
import Packet from '#/io/Packet.js';
import ScriptProvider from '#/engine/script/ScriptProvider.js';
import ScriptRunner from '#/engine/script/ScriptRunner.js';
import ScriptState from '#/engine/script/ScriptState.js';
import ServerTriggerType from '#/engine/script/ServerTriggerType.js';
import LocType from '#/cache/config/LocType.js';
import VarPlayerType from '#/cache/config/VarPlayerType.js';
import Component from '#/cache/config/Component.js';

for (const k of ['loginThread', 'friendThread', 'loggerThread']) (World as any)[k]?.on?.('error', () => {});

const log = (...a: unknown[]) => console.log(`[t${World.currentTick}]`, ...a);
const players: any[] = [];
const waitTicks = (n: number) => new Promise<void>(res => {
    const target = World.currentTick + n;
    const iv = setInterval(() => {
        // a socketless player is logged out 50 ticks after its last "response"; keep them alive
        for (const p of players) { p.lastResponse = World.currentTick; p.lastConnected = World.currentTick; }
        if (World.currentTick >= target) { clearInterval(iv); res(); }
    }, 1);
});

let fails = 0;
const check = (ok: boolean, what: string) => { console.log((ok ? '  ok   ' : '  FAIL ') + what); if (!ok) fails++; };

await World.start(false, true);
World.tickRate = 4;

const varp = (p: any, name: string) => p.getVar(VarPlayerType.getId(name)) as number;
const setVarp = (p: any, name: string, v: number) => p.setVar(VarPlayerType.getId(name), v);
const coordOf = (c: number) => ({ x: (c >> 14) & 0x3fff, z: c & 0x3fff, level: (c >> 28) & 0x3 });

function login(name: string, x: number, z: number) {
    const p = PlayerLoading.load(name, new Packet(new Uint8Array(0)), null);
    p.members = true;
    p.x = x; p.z = z; p.level = 0;
    const msgs: string[] = [];
    (p as any).msgs = msgs;
    p.messageGame = (m: string) => { msgs.push(m); log(name, 'MES', m); };
    World.newPlayers.add(p);
    players.push(p);
    return p;
}
const said = (p: any, text: string, from = 0) => (p.msgs as string[]).slice(from).some(m => m.includes(text));

const PORTAL = LocType.getId('poh_house_portal');
const EXIT = LocType.getId('poh_exit_portal');
// Rimmington's portal (poh_locations.enum poh_loc_portal 0: 0_46_50_7_23) and where its way out lands
const PX = 46 * 64 + 7, PZ = 50 * 64 + 23;

function oploc(p: any, op: number, loc: any) {
    const t = LocType.get(loc.type);
    const script = ScriptProvider.getByTrigger(ServerTriggerType.OPLOC1 + (op - 1), t.id, t.category);
    p.executeScript(ScriptRunner.init(script!, p, loc), true);
}
function button(p: any, com: string) {
    const script = ScriptProvider.getByTrigger(ServerTriggerType.IF_BUTTON, Component.getId(com), -1);
    p.executeScript(ScriptRunner.init(script!, p), true);
}
async function friendsHouse(p: any, name: string) {
    oploc(p, 3, World.getLoc(PX, PZ, 0, PORTAL));
    await waitTicks(2);
    check(p.activeScript?.execution === ScriptState.NAMEDIALOG, `${p.username}: Friend's house asks for a name`);
    if (p.activeScript?.execution !== ScriptState.NAMEDIALOG) return;
    p.activeScript.lastString = name;
    p.executeScript(p.activeScript, true, true);
    await waitTicks(3);
}
function findExitPortal(p: any) {
    for (let dx = -16; dx <= 16; dx++) for (let dz = -16; dz <= 16; dz++) {
        const l = World.getLoc(p.x + dx, p.z + dz, p.level, EXIT);
        if (l) return l;
    }
    return null;
}
const inHouseOf = (guest: any, owner: any) => guest.x >= 6400 && varp(guest, 'poh_visiting') === varp(owner, 'poh_instance');
const outsidePortal = (p: any) => p.x < 6400 && Math.abs(p.x - PX) < 12 && Math.abs(p.z - PZ) < 12;

// ---- the owner goes in
const owner = login('pohowner', PX + 2, PZ - 2);
const guest = login('pohguest', PX + 3, PZ - 2);
await waitTicks(3);
setVarp(owner, 'poh_owned', 1);
setVarp(owner, 'poh_location', 0);
// a wooden chair (poh_furniture.enum item 64) in the starter house's parlour, grid (5,4), laid by
// hand in genfurn.py's packing: rx 3 bits, rz 3, lx 3, lz 3, angle 2, item 8, lit 1, item_hi 7
const CHAIR = { rx: 5, rz: 4, lx: 2, lz: 2 };
setVarp(owner, 'poh_furn_0', CHAIR.rx | (CHAIR.rz << 3) | (CHAIR.lx << 6) | (CHAIR.lz << 9) | (0 << 12) | (64 << 14));
oploc(owner, 1, World.getLoc(PX, PZ, 0, PORTAL));
await waitTicks(4);
check(owner.x >= 6400 && varp(owner, 'poh_instance') !== -1, `the owner is in their house (${owner.x},${owner.z})`);

// ---- a name that is not online
let n = guest.msgs.length;
await friendsHouse(guest, 'nobody_here');
check(said(guest, 'do not seem to be at home', n) && guest.x < 6400, 'a name nobody has: "They do not seem to be at home."');

// ---- in, and expelled
n = guest.msgs.length;
await friendsHouse(guest, 'pohowner');
const entry = coordOf(varp(owner, 'poh_entry'));
check(inHouseOf(guest, owner), `the guest is in the owner's house (${guest.x},${guest.z})`);
check(guest.x === entry.x && guest.z === entry.z, `...where the owner came in (${entry.x},${entry.z})`);
n = owner.msgs.length;
button(owner, 'house_options:expel');
await waitTicks(4);
check(said(owner, 'expelled', n), 'Expel Guests tells the owner');
check(outsidePortal(guest) && said(guest, 'expelled'), `...and the guest is outside the portal (${guest.x},${guest.z})`);
check(varp(guest, 'poh_visiting') === -1, '...and no longer a guest');

// ---- a guest may sit in the owner's chair (furniture that only reads the house is theirs to use)
await friendsHouse(guest, 'pohowner');
{
    const base = coordOf(varp(owner, 'poh_instance'));
    const sits: any[] = [];
    for (let id = 0; id < (LocType as any).configs.length; id++) {
        const t = LocType.get(id);
        if (t?.op?.[0] === 'Sit-on' || t?.op?.[0] === 'Sit') sits.push(id);
    }
    let chair: any = null;
    for (let dx = 0; dx < 8 && !chair; dx++) for (let dz = 0; dz < 8 && !chair; dz++) {
        const x = base.x + (4 + CHAIR.rx) * 8 + dx, z = base.z + (4 + CHAIR.rz) * 8 + dz;
        for (const id of sits) { const l = World.getLoc(x, z, 0, id); if (l) { chair = l; break; } }
    }
    check(chair !== null, `the owner's chair stands in the parlour (${chair ? LocType.get(chair.type).debugname : 'none'})`);
    if (chair) {
        const seated: number[] = [];
        const pa = guest.playAnimation.bind(guest); guest.playAnimation = (a: number, d: number) => { seated.push(a); return pa(a, d); };
        n = guest.msgs.length;
        oploc(guest, 1, chair);
        await waitTicks(6);
        check(seated.length > 0 && !said(guest, 'house you are in', n), 'the guest sits on it');
        guest.playAnimation = pa;
    }
}

// ---- in, and out by the exit portal
check(inHouseOf(guest, owner), 'the guest is back in');
const exitLoc = findExitPortal(guest);
check(exitLoc !== null, 'there is an exit portal near where the guest came in');
if (exitLoc) {
    oploc(guest, 1, exitLoc);
    await waitTicks(4);
    check(outsidePortal(guest), `the exit portal puts the guest outside the owner's portal (${guest.x},${guest.z})`);
    check(owner.x >= 6400 && varp(owner, 'poh_instance') !== -1, "...and the owner's house still stands");
}

// ---- in, and the owner leaves
await friendsHouse(guest, 'pohowner');
check(inHouseOf(guest, owner), 'the guest is in again');
n = guest.msgs.length;
const ownerExit = findExitPortal(owner);
if (ownerExit) oploc(owner, 1, ownerExit);
await waitTicks(5);
check(owner.x < 6400, 'the owner has left their house');
check(outsidePortal(guest) && said(guest, 'owner of the house has left', n), `the guest is put outside the portal, not left in the void (${guest.x},${guest.z})`);

// ---- building mode
oploc(owner, 2, World.getLoc(PX, PZ, 0, PORTAL));
await waitTicks(4);
check(owner.x >= 6400 && varp(owner, 'poh_buildmode') === 1, 'the owner is back in, in building mode');
n = guest.msgs.length;
await friendsHouse(guest, 'pohowner');
check(guest.x < 6400 && said(guest, 'building mode', n), 'a guest cannot come in while the owner is building');

// ---- your own name
n = guest.msgs.length;
await friendsHouse(guest, 'pohguest');
check(guest.x < 6400 && said(guest, 'own house', n), 'your own name sends you to Enter');

console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
process.exit(fails ? 1 : 0);
