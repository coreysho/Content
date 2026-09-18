#!/usr/bin/env python3
"""rs2check - the compile-trap checklist from claude/rs2-compile-traps.md, as a script.

    cd content/scripts
    python3 ../tools/rs2check.py                       # whole repo
    python3 ../tools/rs2check.py path/to/file.rs2 ...  # just these

Two severities:
  ERROR  will not compile, or is a real defect
  CHECK  a symbol did not resolve - usually means the defining file is not in this
         working copy rather than that anything is wrong (see claude/staged-mirror-gaps.md)

Exit status is 1 if any ERROR was reported, else 0.

Every rule here was learned by failing `npm run build`. Three of them were WRONG on their
first version and each wrong version was worse than no check at all, because a checker that
cries wolf gets ignored:

  * Rule 4 started as "any varp write inside ai_*" and flagged 31 files that all compile.
    Only PLAYER varps need p_active_player - .varn and .vars writes are fine in an npc
    trigger - and protect=no opts out, and a preceding p_finduid grants the access.
  * Rule 13 started comma-blind and flagged magic_spells.dbrow, where
    column=specificobj_reqmessage,obj,string declares a two-value column whose first comma
    is load-bearing. It now reads arity from the .dbtable.
  * Rule 1 did not understand block comments and reported a paren imbalance in
    fred_the_farmer.rs2, whose /* */ contains unmatched parens inside YouTube URLs.

And check 11 originally read the stripped-line variable one statement before it was
assigned, so it reported every hit one line late. The tool written to catch off-by-one
mistakes shipped with an off-by-one mistake, and only a probe file with a known expected
answer found it. There is a --selftest for that reason.
"""

import io
import os
import re
import sys
from collections import defaultdict

SCRIPTS = os.path.abspath(".")
CONTENT = os.path.abspath(os.path.join(SCRIPTS, ".."))
PACK = os.path.join(CONTENT, "pack")

findings = []
# The selftest builds its own tiny pack directory, so the missing-pack guard below has to know it
# is being exercised rather than run in anger.
SELFTEST_RUNNING = False


def report(sev, path, line, rule, msg):
    findings.append((sev, os.path.relpath(path, SCRIPTS), line, rule, msg))


# --------------------------------------------------------------------------- reading

def read(path):
    """Always binary. Text mode would silently rewrite every line ending in the file."""
    with open(path, "rb") as f:
        return f.read()


def text(path):
    return read(path).decode("utf-8", "replace").replace("\r\n", "\n")


def walk(exts):
    for root, dirs, files in os.walk(SCRIPTS):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        for f in sorted(files):
            if os.path.splitext(f)[1] in exts:
                yield os.path.join(root, f)


STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def strip_line(line):
    """Remove string literals then a // comment. Block comments are handled by the caller,
    which owns the in-block state."""
    line = STRING.sub('""', line)
    i = line.find("//")
    return line if i < 0 else line[:i]


def stripped_lines(src):
    """Yield (lineno, original, stripped) with strings, // comments and /* */ regions removed.

    ORDER MATTERS. Strings and // comments come off FIRST, because
    quest_blackknight.rs2 line 141 ends in a // comment containing the URL
    .../web/*/http://... - and "/*" inside that opened a block comment that never closed,
    blanking the rest of the file and producing a phantom brace imbalance."""
    inblock = False
    for n, raw in enumerate(src.split("\n"), 1):
        if inblock:
            j = raw.find("*/")
            if j < 0:
                yield n, raw, ""
                continue
            inblock = False
            line = raw[j + 2:]
        else:
            line = raw
        line = strip_line(line)
        out = []
        i = 0
        while i < len(line):
            if inblock:
                j = line.find("*/", i)
                if j < 0:
                    i = len(line)
                else:
                    inblock = False
                    i = j + 2
            else:
                j = line.find("/*", i)
                if j < 0:
                    out.append(line[i:])
                    i = len(line)
                else:
                    out.append(line[i:j])
                    inblock = True
                    i = j + 2
        yield n, raw, "".join(out)


# --------------------------------------------------------------------------- symbol tables

HEADER = re.compile(r"^\[([a-z_0-9]+),([^\]]+)\]")
SIG = re.compile(r"^\[(command|proc|label),([^\]]+)\]\s*(\([^)]*\))?\s*(\([^)]*\))?")


def parse_params(chunk):
    """'(int $a, npc $b)' -> ['int','npc']"""
    if not chunk:
        return []
    inner = chunk.strip()[1:-1].strip()
    if not inner:
        return []
    out = []
    for part in inner.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(part.split()[0])
    return out


def parse_returns(chunk):
    if not chunk:
        return []
    inner = chunk.strip()[1:-1].strip()
    if not inner:
        return []
    return [p.strip() for p in inner.split(",") if p.strip()]


def build_tables():
    t = {
        "commands": {},     # name -> (params, returns)
        "procs": {},        # name -> (params, returns, path, line)
        "labels": {},
        "triggers": defaultdict(list),   # "[trig,subject]" -> [(path,line)]
        "constants": set(),
        "player_varps": {},  # name -> protected(bool)
        "other_vars": set(),
        "dbcolumns": {},    # "table:column" -> arity
        "packs": {},        # kind -> set(names)
    }

    # engine.rs2 command signatures.
    #
    # SCRIPTS is the CURRENT DIRECTORY, so this file is only found when the tool is run from
    # content/scripts as the docstring says. Run it from content/ and it still walks the tree and
    # still prints "0 ERROR" - but with no signatures loaded, rules 6, 7, 7b and 15 all check
    # nothing at all. That silent half-run hid a real type error on 2026-09-11 until the server
    # build caught it. So: loud, not quiet.
    eng = os.path.join(SCRIPTS, "engine.rs2")
    if not os.path.exists(eng):
        sys.exit("rs2check: no engine.rs2 in %s - run this from content/scripts, or half the "
                 "rules check nothing" % SCRIPTS)
    if os.path.exists(eng):
        for raw in text(eng).split("\n"):
            m = SIG.match(raw)
            if m and m.group(1) == "command":
                t["commands"][m.group(2)] = (parse_params(m.group(3)), parse_returns(m.group(4)))

    for path in walk({".rs2"}):
        for n, raw, _ in stripped_lines(text(path)):
            m = SIG.match(raw)
            if m:
                kind, name = m.group(1), m.group(2)
                if kind == "proc":
                    t["procs"][name] = (parse_params(m.group(3)), parse_returns(m.group(4)), path, n)
                elif kind == "label":
                    t["labels"][name] = (parse_params(m.group(3)), parse_returns(m.group(4)), path, n)
                continue
            h = HEADER.match(raw)
            if h and h.group(1) not in ("command", "proc", "label"):
                t["triggers"]["[%s,%s]" % (h.group(1), h.group(2))].append((path, n))

    for path in walk({".constant"}):
        for raw in text(path).split("\n"):
            m = re.match(r"^\^([a-zA-Z_0-9]+)\s*=", raw)
            if m:
                t["constants"].add(m.group(1))

    # .varp: protected unless the block says protect=no. .varn/.vars are not player varps.
    for path in walk({".varp"}):
        cur = None
        for raw in text(path).split("\n"):
            h = re.match(r"^\[([^\]]+)\]", raw)
            if h:
                cur = h.group(1)
                t["player_varps"][cur] = True
            elif cur and raw.strip().replace(" ", "") == "protect=no":
                t["player_varps"][cur] = False
    for path in walk({".varn", ".vars", ".varbit"}):
        for raw in text(path).split("\n"):
            h = re.match(r"^\[([^\]]+)\]", raw)
            if h:
                t["other_vars"].add(h.group(1))

    # .dbtable column arity, for rule 13
    for path in walk({".dbtable"}):
        table = None
        for raw in text(path).split("\n"):
            h = re.match(r"^\[([^\]]+)\]", raw)
            if h:
                table = h.group(1)
                continue
            m = re.match(r"^column=([a-zA-Z_0-9]+),(.*)$", raw.strip())
            if m and table:
                types = [x for x in m.group(2).split(",") if x and x != "LIST"]
                t["dbcolumns"]["%s:%s" % (table, m.group(1))] = len(types)

    if os.path.isdir(PACK):
        for f in sorted(os.listdir(PACK)):
            if not f.endswith(".pack"):
                continue
            names = set()
            with open(os.path.join(PACK, f), "rb") as fh:
                for raw in fh.read().decode("utf-8", "replace").splitlines():
                    if "=" in raw:
                        names.add(raw.split("=", 1)[1].strip())
            t["packs"][f[:-5]] = names

    # A MISSING PACK IS A SILENTLY DISABLED RULE. Rules 14 and 14b both read
    # `known = T["packs"].get(pack)` and then `if known and ...` - so if synth.pack is absent or
    # empty, every sound_synth in the repo goes unchecked and the tool still prints 0 ERROR. That
    # is the same shape as running this from the wrong directory, which build_tables refuses to do
    # quietly a few lines above, and it is how the selftest first came out green on a fixture with
    # no packs in it at all. Loud, not quiet.
    NEEDED = ("synth", "seq", "spotanim", "obj", "npc", "loc", "inv", "varp")
    empty = [k for k in NEEDED if not t["packs"].get(k)]
    if empty and not SELFTEST_RUNNING:
        sys.exit("rs2check: pack/%s.pack is missing or empty - rules 14 and 14b would check "
                 "nothing and this tool would still print 0 ERROR" % ".pack, pack/".join(empty))
    return t


# --------------------------------------------------------------------------- rules

DISCARDABLE = {"gosub", "jump"}


def check_script(path, T):
    raw_bytes = read(path)
    src = raw_bytes.decode("utf-8", "replace").replace("\r\n", "\n")
    lines = list(stripped_lines(src))

    # 12: a CRLF file whose endings were appended twice
    if b"\r\r" in raw_bytes:
        n = raw_bytes[: raw_bytes.index(b"\r\r")].count(b"\n") + 1
        report("ERROR", path, n, 12, "\\r\\r - line endings applied twice")

    # 1: brace / paren balance
    braces = parens = 0
    for n, _, s in lines:
        braces += s.count("{") - s.count("}")
        parens += s.count("(") - s.count(")")
    if braces:
        report("ERROR", path, 0, 1, "brace imbalance %+d" % braces)
    if parens:
        report("ERROR", path, 0, 1, "paren imbalance %+d" % parens)

    cur_kind = None
    cur_name = None
    ai_trigger = False
    seen_pfinduid = False

    for n, orig, s in lines:
        h = HEADER.match(s) or HEADER.match(orig)
        if h:
            cur_kind, cur_name = h.group(1), h.group(2)
            ai_trigger = cur_kind.startswith("ai_")
            seen_pfinduid = False
            continue

        if "p_finduid" in s:
            seen_pfinduid = True

        # 3: a ^constant interpolated raw into a string needs tostring()
        for m in re.finditer(r"<\s*\^([a-zA-Z_0-9]+)\s*>", orig):
            report("ERROR", path, n, 3, "^%s interpolated raw - use <tostring(^%s)>" % (m.group(1), m.group(1)))

        # 11: @label jump inside a [proc,...] body. Only a real jump - @dbl@ is a colour code.
        if cur_kind == "proc":
            for m in re.finditer(r"@([a-zA-Z_0-9]+)\s*[;(]", s):
                report("ERROR", path, n, 11,
                       "@%s inside [proc,%s] - labels cannot be jumped to from a proc" % (m.group(1), cur_name))

        # 4: protected player varp written inside an ai_* trigger with no preceding p_finduid
        if ai_trigger and not seen_pfinduid:
            m = re.match(r"^\s*%([a-zA-Z_0-9]+)\s*=", s)
            if m:
                v = m.group(1)
                if T["player_varps"].get(v, False) and v not in T["other_vars"]:
                    report("ERROR", path, n, 4,
                           "%%%s (protected player varp) written in [%s,%s] - queue it or p_finduid first"
                           % (v, cur_kind, cur_name))

        # 6: bare call to a command that returns a value
        m = re.match(r"^\s*(\.?[a-z_0-9]+)\s*\(.*\)\s*;\s*$", s)
        if m:
            name = m.group(1)
            if name in T["commands"] and T["commands"][name][1] and name not in DISCARDABLE:
                report("ERROR", path, n, 6, "%s(...) returns a value that is discarded" % name)

        # 7: def_TYPE assigned from a command or bare pointer whose return type differs
        m = re.match(r"^\s*def_([a-z_0-9]+)\s+\$[a-zA-Z_0-9]+\s*=\s*(\.?[a-z_0-9]+)\s*(\(|;)", s)
        if m:
            want, src_name = m.group(1), m.group(2)
            if src_name in T["commands"]:
                rets = T["commands"][src_name][1]
                if len(rets) == 1 and rets[0] != want and not (rets[0] == "namedobj" and want == "obj"):
                    report("ERROR", path, n, 7,
                           "def_%s from %s which returns %s" % (want, src_name, rets[0]))

        # 7b: argument count passed to a ~proc / @label against its declaration
        for sigil, table in (("~", "procs"), ("@", "labels")):
            for m in re.finditer(re.escape(sigil) + r"([a-zA-Z_0-9]+)\s*\(", s):
                name = m.group(1)
                if name not in T[table]:
                    continue
                start = m.end() - 1
                depth = 0
                end = -1
                for i in range(start, len(s)):
                    if s[i] == "(":
                        depth += 1
                    elif s[i] == ")":
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                if end < 0:
                    continue
                inner = s[start + 1:end].strip()
                # An argument list cannot be counted through a call. A proc may return SEVERAL
                # values and fill several parameters at once - doors.rs2 does
                #   ~movecoord_loc_return(~door_open(loc_angle, loc_shape))
                # where door_open returns (int, int) and fills both of movecoord_loc_return's
                # parameters - and db_getfield's arity depends on the dbtable column, so it is
                # not knowable from the script at all. This check therefore only runs on
                # argument lists made of plain literals and variables. That still catches the
                # common mistake - a forgotten argument - with no false positives. Counting
                # naively flagged 81 call sites in a repo that compiles clean.
                if not inner:
                    got = 0
                elif "(" in inner or "~" in inner or "null" in inner:
                    continue
                else:
                    got = inner.count(",") + 1
                want = len(T[table][name][0])
                if got != want:
                    report("ERROR", path, n, "7b",
                           "%s%s takes %d argument(s), given %d" % (sigil, name, want, got))


        # 15: an enum(...) passed where the declared parameter is a different type.
        #
        # THE RULE THIS ROUND EARNED. enum's second argument IS its output type, and the compiler
        # checks it against the parameter exactly: enum(int, obj, ...) into inv_add's namedobj is
        #   "Type mismatch: 'inv,obj,int' was given but 'inv,namedobj,int' was expected"
        # and nothing else in this file would have caught it, because the arity is right. namedobj
        # widens to obj (rule 7 already knows that); obj does not narrow to namedobj.
        #
        # Only argument lists with no ~proc, @label or db_getfield call in them: those can return
        # several values and fill several parameters at once, so the positions no longer line up.
        for sigil, table in (("", "commands"), ("~", "procs"), ("@", "labels")):
            pat = (re.escape(sigil) if sigil else r"(?<![a-zA-Z_0-9.~@$])") + r"([a-zA-Z_0-9]+)\s*\("
            for m in re.finditer(pat, s):
                name = m.group(1)
                if name not in T[table] or name == "enum":
                    continue
                params = T[table][name][0]
                start = m.end() - 1
                depth, end = 0, -1
                for i in range(start, len(s)):
                    if s[i] == "(":
                        depth += 1
                    elif s[i] == ")":
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                if end < 0:
                    continue
                inner = s[start + 1:end]
                if "~" in inner or "@" in inner or "db_getfield" in inner:
                    continue
                args, depth, cur = [], 0, ""
                for ch in inner:
                    if ch == "," and depth == 0:
                        args.append(cur.strip()); cur = ""
                        continue
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                    cur += ch
                if cur.strip():
                    args.append(cur.strip())
                if len(args) != len(params):
                    continue
                for arg, want in zip(args, params):
                    e = re.match(r"^enum\s*\(\s*[a-zA-Z_0-9]+\s*,\s*([a-zA-Z_0-9]+)\s*,", arg)
                    if not e:
                        continue
                    got = e.group(1)
                    if got == want or (got == "namedobj" and want == "obj"):
                        continue
                    report("ERROR", path, n, 15,
                           "%s%s wants %s here, enum(...) gives %s" % (sigil, name, want, got))

        # 14: a seq or synth that does not exist. Only the positions where the argument is
        # always a bare name - this is what caught sound_synth(cannon_fire) and
        # sound_synth(splash) on two separate Recipe for Disaster passes.
        for cmd, pack in (("sound_synth", "synth"), ("anim", "seq"), ("npc_anim", "seq"),
                          ("loc_anim", "seq"), ("spotanim_map", "spotanim")):
            for m in re.finditer(r"(?<![a-zA-Z_0-9.])" + cmd + r"\(\s*([a-zA-Z_0-9+]+)\s*[,)]", s):
                sym = m.group(1)
                if sym in ("null",) or sym.isdigit():
                    continue
                known = T["packs"].get(pack)
                if known and sym not in known:
                    report("ERROR", path, n, 14, "%s(%s) - no such %s" % (cmd, sym, pack))

        # 14b: an obj, npc, loc or inv NAME that does not exist. Same idea as 14 but the name is
        # not the first argument, so the call has to be split properly - nested calls and
        # coordinates both contain commas. Only BARE names are checked: $vars, ^constants,
        # enum(...) and arithmetic all resolve elsewhere and are skipped.
        #
        # This is the check that would have caught a drop table written from memory instead of
        # from pack/obj.pack: bigbones, grimy_ranarr, grimy_irit, grimy_avantoe and adamant_bolts
        # are all plausible, all wrong, and none of them is a compile error until the packer runs.
        for cmd, pack, idx in (("obj_add", "obj", 1), ("inv_add", "obj", 1), ("inv_del", "obj", 1),
                               ("inv_total", "obj", 1), ("inv_getnum", "obj", 1),
                               ("inv_setslot", "obj", 2), ("inv_placeholder", "obj", 2),
                               ("oc_name", "obj", 0), ("oc_param", "obj", 0),
                               ("npc_add", "npc", 1), ("loc_add", "loc", 4),
                               ("inv_total", "inv", 0), ("inv_add", "inv", 0),
                               ("inv_del", "inv", 0), ("inv_getobj", "inv", 0)):
            known = T["packs"].get(pack)
            if not known:
                continue
            for m in re.finditer(r"(?<![a-zA-Z_0-9.$^~@%])" + cmd + r"\s*\(", s):
                args, depth, cur, i = [], 0, "", m.end()
                while i < len(s):
                    ch = s[i]
                    if ch in "([":
                        depth += 1; cur += ch
                    elif ch == ")" and depth == 0:
                        args.append(cur); break
                    elif ch in ")]":
                        depth -= 1; cur += ch
                    elif ch == "," and depth == 0:
                        args.append(cur); cur = ""
                    else:
                        cur += ch
                    i += 1
                if idx >= len(args):
                    continue
                sym = args[idx].strip()
                # engine-supplied bare words, not config names: these read an obj id out of
                # the current context (ScriptOpcodePointers) and resolve no pack at all
                if sym in ("null", "last_useitem", "last_item", "last_usedobj", "obj_type"):
                    continue
                if not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]*", sym):
                    continue
                if sym not in known:
                    report("ERROR", path, n, 14, "%s(...) argument %d is %s - no such %s"
                           % (cmd, idx + 1, sym, pack))

        # 5: unresolved references
        for m in re.finditer(r"~([a-zA-Z_0-9]+)", s):
            if m.group(1) not in T["procs"]:
                report("CHECK", path, n, 5, "~%s does not resolve to a [proc,...]" % m.group(1))
        for m in re.finditer(r"(?<![a-zA-Z_0-9@])@([a-zA-Z_0-9]+)\s*[;(]", s):
            if m.group(1) not in T["labels"]:
                report("CHECK", path, n, 5, "@%s does not resolve to a [label,...]" % m.group(1))
        for m in re.finditer(r"\^([a-zA-Z_0-9]+)", s):
            if m.group(1) not in T["constants"]:
                report("CHECK", path, n, 5, "^%s does not resolve to a constant" % m.group(1))
        for m in re.finditer(r"%([a-zA-Z_0-9]+)", s):
            v = m.group(1)
            if v not in T["player_varps"] and v not in T["other_vars"]:
                where = [k for k in ("varp", "varn", "vars", "varbit") if v in T["packs"].get(k, ())]
                if where:
                    # Compiles, because the symbol resolves from the pack - but with no config
                    # block it has no scope, no protect and no transmit, and it is registered in
                    # whichever pack happens to hold it rather than the one its name implies.
                    report("ERROR", path, n, "5b",
                           "%%%s is in %s.pack but NO config block defines it - no scope, no protect, no transmit"
                           % (v, where[0]))
                else:
                    report("CHECK", path, n, 5, "%%%s does not resolve to a var" % v)


def check_locals(path):
    """Rule 18: a $local read in a block that never declares it.

    A proc's locals do not reach the next proc, and the compiler says so - but nothing here did,
    so the mistake survived a full rs2check run. It was made writing the black mask imbue: the
    single-target magic cast set up $mask_num and the multi-target proc two blocks down read it,
    which reads fine and does not compile.

    Deliberately ORDER-BLIND. A declaration anywhere in the block counts, so this does not try to
    catch use-before-declare - that is a different mistake, and checking it would need to model the
    if/else nesting that RuneScript does not scope by anyway. What it catches is the one that
    matters: a name that block never declares at all.
    """
    src = text(path)
    blocks = []
    cur = None
    for n, raw, s in stripped_lines(src):
        m = SIG.match(raw) or HEADER.match(raw)
        if m and raw.startswith("["):
            # ANY block header can carry a signature, not just proc/label/command:
            # [debugproc,clearinv](inv $inv), [queue,x](int $n), [timer,y](...) and so on. SIG only
            # matches three of them, and using it here made this rule report 93 findings in a repo
            # that compiles - which is the failure mode three other rules in this file have had.
            head = raw.split("]", 1)
            params = re.findall(r"\$([a-zA-Z_0-9]+)", head[1]) if len(head) > 1 else []
            cur = {"name": raw.split("]")[0] + "]", "line": n, "declared": set(params), "used": []}
            blocks.append(cur)
            continue
        if cur is None:
            continue
        for d in re.finditer(r"\bdef_[a-z_0-9]+\s+\$([a-zA-Z_0-9]+)", s):
            cur["declared"].add(d.group(1))
        for u in re.finditer(r"\$([a-zA-Z_0-9]+)", s):
            cur["used"].append((u.group(1), n))
    for b in blocks:
        seen = set()
        for name, n in b["used"]:
            if name in b["declared"] or name in seen:
                continue
            seen.add(name)
            report("ERROR", path, n, 18,
                   "$%s is read in %s but that block never declares it" % (name, b["name"]))


def check_config(path, T):
    raw_bytes = read(path)
    if b"\r\r" in raw_bytes:
        n = raw_bytes[: raw_bytes.index(b"\r\r")].count(b"\n") + 1
        report("ERROR", path, n, 12, "\\r\\r - line endings applied twice")

    if not path.endswith(".dbrow"):
        return

    # 13: unquoted comma in a config prose field, arity-aware
    src = raw_bytes.decode("utf-8", "replace").replace("\r\n", "\n")
    table = None
    for n, raw in enumerate(src.split("\n"), 1):
        line = raw.strip()
        if line.startswith("//") or not line:
            continue
        m = re.match(r"^table=([a-zA-Z_0-9]+)", line)
        if m:
            table = m.group(1)
            continue
        m = re.match(r"^data=([a-zA-Z_0-9]+),(.*)$", line)
        if not m or table is None:
            continue
        column, rest = m.group(1), m.group(2)
        if rest.startswith('"'):
            continue                      # quoted, which is the levelup.dbrow idiom
        arity = T["dbcolumns"].get("%s:%s" % (table, column))
        if arity is None:
            continue
        got = rest.count(",") + 1
        if got > arity:
            report("ERROR", path, n, 13,
                   "data=%s declares %d value(s) but this row has %d - quote it or reword"
                   % (column, arity, got))


# --------------------------------------------------------------------------- duplicate triggers

def check_models():
    """Rule 16: every .ob2 on disk is registered in model.pack, and every entry has a file.

    A config's model= name is NOT the check here. Loc models get a shape suffix in the pack
    (`model=100_bubbleb` in the .loc, `13670=100_bubbleb_8` in model.pack), so comparing config
    names against pack names reports thousands of false positives. Filenames match pack names
    exactly, in every one of the six model directories, so that is what is compared.

    This exists because an importer wrote models/npc/npc_cave_horror_1.ob2 and a .npc that
    references it and never touched model.pack. Nothing in the content tree catches that: it is
    not a script, so no rule here looked at it, and the packer's message is
    "Invalid property value: model1=npc_cave_horror_1", which reads like the config is wrong.
    """
    import glob
    pack_path = os.path.join(CONTENT, "pack", "model.pack")
    if not os.path.exists(pack_path):
        return
    names, ids = {}, {}
    for n, line in enumerate(io.open(pack_path, encoding="utf-8", errors="replace"), 1):
        line = line.strip()
        if "=" not in line:
            continue
        i, nm = line.split("=", 1)
        if nm in names:
            report("ERROR", "pack/model.pack", n, 16, "duplicate model name %s" % nm)
        if i in ids:
            report("ERROR", "pack/model.pack", n, 16, "duplicate model id %s" % i)
        names[nm] = n
        ids[i] = n

    for d in ("npc", "obj", "loc", "com", "idk", "spot"):
        for f in sorted(glob.glob(os.path.join(CONTENT, "models", d, "*.ob2"))):
            nm = os.path.basename(f)[:-4]
            if nm not in names:
                report("ERROR", "models/%s/%s.ob2" % (d, nm), 0, 16,
                       "on disk but NOT in pack/model.pack - any config naming it fails the build")

    on_disk = {os.path.basename(f)[:-4]
               for f in glob.glob(os.path.join(CONTENT, "models", "*", "*.ob2"))}
    for nm, n in sorted(names.items()):
        if nm not in on_disk:
            report("ERROR", "pack/model.pack", n, 16, "%s is registered but no .ob2 exists" % nm)


def check_enum_defaults():
    """Rule 17: an enum whose outputtype has a REAL id 0 must declare default=.

    EnumConfig only writes opcode 4 when a default= key is present, EnumType.defaultInt is 0, and
    EnumOps pushes `value ?? defaultInt` - so a MISS RETURNS 0, NOT NULL. Id 0 is a real thing in
    every one of these tables:

        seq.pack:0      swarm_walk
        spotanim.pack:0 triple_firebreath_attack
        npc.pack:0      hans
        obj.pack:0      mcannonremains
        loc.pack:0      mcannoncrate

    So a lookup that misses does not fail - it returns something plausible, and every `! null` guard
    written against it passes. That is how the skillcape emote came to breathe dragonfire at anyone
    in a plain cape (2026-09-12), and how `slayer_superior` was one 1/200 roll away from spawning
    HANS as a superior slayer monster on any of the 69 tasks that have no superior (2026-09-14).

    Only types where 0 is a real entry are flagged. An `int`- or `string`-typed enum returning 0 on
    a miss is ordinary and frequently intended, and flagging those would put 96 findings in front of
    the 61 that matter.
    """
    risky = ("namedobj", "npc", "obj", "seq", "loc", "spotanim", "component",
             "interface", "synth", "category", "struct", "dbrow", "inv", "stat")
    for path in walk({".enum"}):
        cur = None
        info = {}
        order = []
        for n, raw, _ in stripped_lines(text(path)):
            # NOT the HEADER regex: that one requires a comma ("[opheld1,thing]"), and a config
            # block header has none ("[superiors]"). Using it here made the whole rule a no-op -
            # cur never got set, nothing was ever recorded, and deleting a default= to test it
            # still printed 0 ERROR. Second time a rule in this file has shipped inert; test every
            # new one by breaking the thing it is supposed to catch.
            m = re.match(r"^\[([^\],]+)\]\s*$", raw.strip())
            if m:
                cur = m.group(1)
                info[cur] = {"line": n, "default": False, "out": None}
                order.append(cur)
            elif cur:
                t = raw.strip()
                if t.startswith("default="):
                    info[cur]["default"] = True
                elif t.startswith("outputtype="):
                    info[cur]["out"] = t.split("=", 1)[1].strip()
        for k in order:
            v = info[k]
            if not v["default"] and v["out"] in risky:
                report("ERROR", path, v["line"], 17,
                       "[%s] outputs %s and has no default= - a miss returns id 0, which is a real %s"
                       % (k, v["out"], v["out"]))


def check_duplicates(T):
    for trig, places in sorted(T["triggers"].items()):
        if len(places) > 1:
            for path, n in places:
                report("ERROR", path, n, 2, "duplicate trigger %s (declared %d times)" % (trig, len(places)))


# --------------------------------------------------------------------------- selftest
#
# EVERY RULE HAS TO BE ABLE TO GO RED, and this is what proves it. Two rules in this file have
# shipped INERT - doing nothing, reporting nothing, and counting as coverage:
#
#   * check 11 read the stripped-line variable one statement before it was assigned, so it reported
#     every hit one line late. The tool written to catch off-by-one mistakes shipped with one.
#   * check 17 matched a block header with a pattern a header never satisfies, so the whole rule was
#     a no-op and the repo still printed 0 ERROR.
#
# The old selftest covered eight of the sixteen rules. The other eight were 1, 2, 5, 12, 13, 15, 16
# and 17 - which is to say BOTH rules that shipped inert were in the uncovered half, and both stayed
# inert until something else found them.
#
# So this builds a whole miniature content tree - scripts, configs, a pack, a models directory -
# breaks one thing per rule in it, points the tool at it and runs the real code path end to end.
# build_tables walks the fixture and every check function runs against it, so a rule that cannot
# fire shows up as a missing id rather than as silence.

FIXTURE = {
    # rules 3, 4, 5, 5b, 6, 7, 7b, 11, 14, 15
    "probe.rs2": """
[proc,probe_p]
@probe_label;

[label,probe_label](int $a)
mes("x");

[ai_queue3,probe_npc]
%probe_protected_varp = 1;

[opheld1,probe_obj]
mes("<^probe_const>");
npc_finduid(npc_uid);
def_int $u = npc_uid;
~probe_two(1);
sound_synth(probe_no_such_synth, 1, 0);
inv_total(inv, probe_no_such_obj);
%probe_packonly_varp = 1;
~probe_wants_int(enum(int, namedobj, probe_enum, 0));
~probe_no_such_proc(1);
~probe_wants_int($probe_undeclared);
@probe_no_such_label;
mes("<tostring(^probe_no_such_const)>");
%probe_no_such_var = 1;
// a real block comment with an unmatched ( inside, which must not unbalance anything
/* ( ( ( */
// and a line comment holding https://web.archive.org/web/*/http://x - the /* here is not a block

[proc,probe_two](int $a, int $b)
mes("y");

[proc,probe_wants_int](int $a)
mes("z");
""",
    # rule 1, on its own file: an imbalance swallows everything after it
    "probe_brace.rs2": """
[proc,probe_unbalanced]
if (1 = 1) {
    mes("the closing brace and paren are both missing";
""",
    # rule 2: the same trigger in two files
    "probe_dup_a.rs2": "\n[opheld2,probe_obj]\nmes(\"a\");\n",
    "probe_dup_b.rs2": "\n[opheld2,probe_obj]\nmes(\"b\");\n",
    # rule 13: a prose comma in a one-value column
    "probe.dbtable": "\n[probe_table]\ncolumn=probe_text,string\n",
    "probe.dbrow": "\n[probe_row]\ntable=probe_table\ndata=probe_text,one, two\n",
    # rule 17: a namedobj enum with no default, where a miss returns obj 0 rather than null
    "probe.enum": "\n[probe_enum]\ninputtype=int\noutputtype=namedobj\nval=0,probe_obj\n",
    # AND THE OTHER HALF: a file that is entirely correct and must produce NOTHING. A rule that
    # fires on everything is no more use than one that fires on nothing, and three rules in this
    # file were wrong in exactly that direction on their first version - rule 4 flagged 31 files
    # that all compile, rule 13 flagged a load-bearing comma, rule 1 could not read a block comment.
    # Every idiom below is one that a previous version of some rule got wrong.
    "probe_clean.rs2": """
[proc,probe_clean](int $given)
def_int $n = calc(1 + $given);
mes("<tostring(^probe_const)> and a @dbl@ colour code, which is not a jump");
~probe_two(1, 2);
if ($n = 2) {
    mes("balanced");
}
/* a block comment with ) ) ) unmatched inside it */
// and a url with /* in it: https://web.archive.org/web/*/http://example.com
~probe_wants_int(enum(int, int, probe_int_enum, 0));

[ai_queue4,probe_npc]
if (p_finduid(uid) = true) {
    %probe_protected_varp = 2;
}

// the shape rule 4's first version got wrong: an ai_ trigger with no p_finduid at all, writing a
// varp that is NOT protected. 31 files look like this and every one of them compiles.
[ai_queue5,probe_npc]
%probe_unprotected_varp = 3;

[opheld3,probe_obj]
%probe_unprotected_varp = 1;
def_obj $o = inv_getobj(inv, 0);
// declared in THIS block. The first draft of this fixture read $n from the proc above, which is
// the exact mistake rule 18 exists for - the clean file caught the rule's own author.
def_int $n = 2;
~probe_wants_int($n);
sound_synth(probe_synth, 1, 0);
inv_add(inv, probe_obj, 1);
""",
    "probe_clean.dbrow": "\n[probe_clean_row]\ntable=probe_table\ndata=probe_text,\"one, two\"\n",
    "probe_clean.enum": "\n[probe_int_enum]\ninputtype=int\noutputtype=int\nval=0,1\n",
    # rule 20: a type=text with no font, which packs as fonts[255] and kills the client on load
    "probe.if": "type=overlay\n\n[probe_nofont]\ntype=text\nx=0\ny=0\nwidth=10\nheight=10\n",
    "probe_clean.if": ("type=overlay\n\n[probe_ok]\ntype=text\nx=0\ny=0\nwidth=10\nheight=10\n"
                       "font=p12_full\nshadowed=yes\n"),
}
# rule 12 is bytes, not text: \r\r is what a line-ending pass applied twice leaves behind
FIXTURE_BYTES = {
    "probe_crlf.rs2": b"\r\n[proc,probe_crlf]\r\r\nmes(\"x\");\r\n",
    "probe_crlf.obj": b"\r\n[probe_crlf_obj]\r\rname=Probe\r\n",
}
# rule 16, three ways: a name twice, an id twice, an entry with no file - plus a file with no entry
FIXTURE_PACK = "0=probe_model\n1=probe_model\n1=probe_other\n2=probe_phantom\n"
# ...and the packs rules 14 and 14b read. They have to be REAL files in the fixture, not entries
# poked into the table afterwards, because "the pack was not there" is the failure being guarded
# against and poking the table would hide it.
FIXTURE_PACKS = {
    "synth.pack": "0=probe_synth\n",
    "seq.pack": "0=probe_seq\n",
    "spotanim.pack": "0=probe_spotanim\n",
    "obj.pack": "0=probe_obj\n",
    "npc.pack": "0=probe_npc\n",
    "loc.pack": "0=probe_loc\n",
    "inv.pack": "0=inv\n",
    "varp.pack": "0=probe_packonly_varp\n",
}
FIXTURE_MODEL = "models/loc/probe_orphan.ob2"

# Every rule id this file can report, AND THE EXACT LINE it must report it on. The line matters as
# much as the rule: check 11's inert version DID fire, on every hit, one line late - so a selftest
# that only asked "did rule 11 appear?" would have passed on it. Asking where is what turns this
# from a smoke test into a test.
ALL_RULES = {
    # 18 is the newest: a $local read in a block that never declares it. Made while writing the
    # black mask imbue - the single-target magic cast set up $mask_num and a proc two blocks down
    # read it - and nothing in this file noticed, because there was no rule for it.
    1:    ("probe_brace.rs2", 0),     # an imbalance has no single line; 0 is the file itself
    2:    ("probe_dup_a.rs2", 2),
    3:    ("probe.rs2", 12),
    4:    ("probe.rs2", 9),
    5:    ("probe.rs2", 20),
    "5b": ("probe.rs2", 18),
    6:    ("probe.rs2", 13),
    7:    ("probe.rs2", 14),
    "7b": ("probe.rs2", 15),
    11:   ("probe.rs2", 3),
    18:   ("probe.rs2", 21),
    12:   ("probe_crlf.rs2", 2),
    13:   ("probe.dbrow", 4),
    14:   ("probe.rs2", 16),
    15:   ("probe.rs2", 19),
    16:   ("model.pack", 2),
    17:   ("probe.enum", 2),
    # 20 is the newest: a type=text with no font=. PackShared writes -1 as the byte 255 and
    # Component.decode indexes an array of four with it, so the CLIENT dies on load - "loaderror
    # Unpacking interfaces 95" - with no server-side symptom at all. Cost one deploy.
    20:   ("probe.if", 3),
}


def selftest():
    global SCRIPTS, CONTENT, PACK, SELFTEST_RUNNING
    SELFTEST_RUNNING = True
    import shutil
    import tempfile
    real_scripts = SCRIPTS
    real_content = CONTENT
    real_pack = PACK
    d = tempfile.mkdtemp(prefix="rs2check_selftest_")
    try:
        root = os.path.join(d, "content")
        sdir = os.path.join(root, "scripts")
        os.makedirs(os.path.join(root, "pack"))
        os.makedirs(os.path.join(root, "models", "loc"))
        os.makedirs(sdir)
        # the real command signatures: without them rules 6, 7, 7b and 15 check nothing, which is
        # the silent half-run build_tables refuses to do in anger and must not do here either
        shutil.copyfile(os.path.join(real_scripts, "engine.rs2"), os.path.join(sdir, "engine.rs2"))
        for name, body in FIXTURE.items():
            with open(os.path.join(sdir, name), "wb") as f:
                f.write(body.encode())
        for name, body in FIXTURE_BYTES.items():
            with open(os.path.join(sdir, name), "wb") as f:
                f.write(body)
        with open(os.path.join(root, "pack", "model.pack"), "w") as f:
            f.write(FIXTURE_PACK)
        for name, body in FIXTURE_PACKS.items():
            with open(os.path.join(root, "pack", name), "w") as f:
                f.write(body)
        open(os.path.join(root, FIXTURE_MODEL), "wb").close()

        SCRIPTS, CONTENT, PACK = sdir, root, os.path.join(root, "pack")
        del findings[:]
        T = build_tables()
        # symbols the probe leans on that no fixture file declares: a constant, a protected player
        # varp, and a varp that is in a pack with no config block behind it (rule 5b)
        T["constants"].add("probe_const")
        T["player_varps"]["probe_protected_varp"] = True
        T["packs"].setdefault("varp", set()).add("probe_packonly_varp")
        T["player_varps"]["probe_unprotected_varp"] = False
        for p in sorted(walk({".rs2"})):
            check_script(p, T)
            check_locals(p)
        for p in sorted(walk({".dbrow", ".constant", ".obj", ".npc", ".loc", ".inv",
                              ".varp", ".varbit"})):
            check_config(p, T)
        check_duplicates(T)
        check_models()
        check_enum_defaults()
        check_interfaces()
        got = {}
        for sev, path, line, rule, msg in findings:
            got.setdefault(rule, []).append((sev, path, line, msg))
    finally:
        SCRIPTS, CONTENT, PACK = real_scripts, real_content, real_pack
        shutil.rmtree(d, ignore_errors=True)

    bad = []
    for rule in sorted(ALL_RULES, key=str):
        want_file, want_line = ALL_RULES[rule]
        hits = got.get(rule, [])
        if not hits:
            print("  rule %-3s DID NOT FIRE - it cannot go red, so it is not coverage" % rule)
            bad.append("%s never fired" % rule)
            continue
        where = [(os.path.basename(h[1]), h[2]) for h in hits]
        if (want_file, want_line) not in where:
            print("  rule %-3s fired on %s, wanted %s:%s - off by %s"
                  % (rule, where[:2], want_file, want_line,
                     (where[0][1] - want_line) if where[0][0] == want_file else "the wrong file"))
            bad.append("%s fired in the wrong place" % rule)
            continue
        sev, path, line, msg = [h for h in hits if (os.path.basename(h[1]), h[2])
                                == (want_file, want_line)][0]
        print("  rule %-3s fired  %-5s %s:%-3s %s"
              % (rule, sev, os.path.basename(path), line, msg[:58]))

    # nothing may fire on the clean half
    noise = sorted({(os.path.basename(h[1]), h[2], r, h[3][:50])
                    for r, hs in got.items() for h in hs if "clean" in os.path.basename(h[1])})
    for f in noise:
        print("  FALSE POSITIVE on the clean fixture: %s:%s rule %s  %s" % f)
        bad.append("rule %s fires on correct code" % f[2])
    extra = sorted((set(got) - set(ALL_RULES)), key=str)
    if extra:
        print("  (also fired, not in ALL_RULES: %s - add them or tighten the fixture)" % extra)
    print("selftest: %s" % ("PASS, all %d rules go red in the right place and none on clean code"
                            % len(ALL_RULES) if not bad else "FAIL - " + "; ".join(bad)))
    return 0 if not bad else 1


# --------------------------------------------------------------------------- main


# --------------------------------------------------------------------------- rule 20

# PackShared.nameToFont returns -1 for a font it does not know - INCLUDING a missing one - and
# p1(-1) is the byte 255. Component.decode then does `com.font = fonts[font]` on an array of
# FOUR, so the client dies inside Component.unpack with
#
#     loaderror Unpacking interfaces 95
#
# before it reaches the login screen. There is no server-side symptom at all: the pack builds
# clean and the world comes up. Cost one deploy on 2026-09-18, from 22 buttons that draw no text
# and were given no font on the reasoning that they did not need one.
IF_FONTS = {"p11_full", "p12_full", "b12_full", "q8_full"}
IF_TYPES = {"layer", "overlay", "inv", "rect", "text", "graphic", "model", "invtext", "8"}


def check_interfaces():
    for path in walk({".if"}):
        cur, kv, start = None, {}, 0

        def finish():
            if cur is None:
                return
            t = kv.get("type")
            if t is not None and t not in IF_TYPES:
                report("ERROR", path, start, 20,
                       "[%s] type=%s is not a type the packer knows" % (cur, t))
            # comType 4 (text) and 1 - the two branches Component.decode reads a font for
            if t == "text":
                f = kv.get("font")
                if f is None:
                    report("ERROR", path, start, 20,
                           "[%s] is type=text with no font= - the client reads fonts[255] and "
                           "dies unpacking interfaces" % cur)
                elif f not in IF_FONTS:
                    report("ERROR", path, start, 20,
                           "[%s] font=%s is not one of %s" % (cur, f, sorted(IF_FONTS)))

        for n, raw, _ in stripped_lines(text(path)):
            m = re.match(r"^\[([A-Za-z0-9_]+)\]\s*$", raw)
            if m:
                finish()
                cur, kv, start = m.group(1), {}, n
                continue
            if "=" in raw and cur:
                k, v = raw.split("=", 1)
                kv.setdefault(k.strip(), v.strip())
        finish()


def main(argv):
    if "--selftest" in argv:
        return selftest()
    T = build_tables()
    targets = [a for a in argv if not a.startswith("-")]
    if targets:
        scripts = [os.path.abspath(t) for t in targets if t.endswith(".rs2")]
        configs = [os.path.abspath(t) for t in targets if not t.endswith(".rs2")]
    else:
        scripts = list(walk({".rs2"}))
        configs = list(walk({".dbrow", ".constant", ".obj", ".npc", ".loc", ".inv", ".varp", ".varbit"}))
    for p in scripts:
        check_script(p, T)
        check_locals(p)
    for p in configs:
        check_config(p, T)
    if not targets:
        check_duplicates(T)
        check_models()
        check_enum_defaults()
        check_interfaces()

    errors = [f for f in findings if f[0] == "ERROR"]
    checks = [f for f in findings if f[0] == "CHECK"]
    for f in sorted(errors, key=lambda x: (x[1], x[2])):
        print("ERROR %s:%s  rule %-3s %s" % (f[1], f[2], f[3], f[4]))
    if "-v" in argv or "--checks" in argv:
        for f in sorted(checks, key=lambda x: (x[1], x[2])):
            print("CHECK %s:%s  rule %-3s %s" % (f[1], f[2], f[3], f[4]))
    print("\n%d scripts, %d configs: %d ERROR, %d CHECK%s"
          % (len(scripts), len(configs), len(errors), len(checks),
             "" if ("-v" in argv or "--checks" in argv) else " (re-run with -v to list CHECK)"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
