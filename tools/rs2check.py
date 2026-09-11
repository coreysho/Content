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

import os
import re
import sys
from collections import defaultdict

SCRIPTS = os.path.abspath(".")
CONTENT = os.path.abspath(os.path.join(SCRIPTS, ".."))
PACK = os.path.join(CONTENT, "pack")

findings = []


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

def check_duplicates(T):
    for trig, places in sorted(T["triggers"].items()):
        if len(places) > 1:
            for path, n in places:
                report("ERROR", path, n, 2, "duplicate trigger %s (declared %d times)" % (trig, len(places)))


# --------------------------------------------------------------------------- selftest

SELFTEST = r'''
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
%probe_packonly_varp = 1;
// a real block comment with an unmatched ( inside, which must not unbalance anything
/* ( ( ( */
// and a line comment holding https://web.archive.org/web/*/http://x - the /* here is not a block

[proc,probe_two](int $a, int $b)
mes("y");
'''


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, "probe.rs2")
    with open(p, "wb") as f:
        f.write(SELFTEST.encode())
    T = build_tables()
    T["procs"]["probe_p"] = ([], [], p, 2)
    T["procs"]["probe_two"] = (["int", "int"], [], p, 20)
    T["labels"]["probe_label"] = (["int"], [], p, 5)
    T["constants"].add("probe_const")
    T["player_varps"]["probe_protected_varp"] = True
    T["packs"].setdefault("varp", set()).add("probe_packonly_varp")
    del findings[:]
    check_script(p, T)
    want = {11, 4, 3, 6, 7, "7b", 14, "5b"}
    got = set(r[3] for r in findings if r[0] == "ERROR")
    for f in sorted(findings, key=lambda x: x[2]):
        print("  %-5s line %-3s rule %-3s %s" % (f[0], f[2], f[3], f[4]))
    missing = want - got
    print("selftest:", "PASS" if not missing else "FAIL, missed rules %s" % sorted(map(str, missing)))
    return 0 if not missing else 1


# --------------------------------------------------------------------------- main

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
    for p in configs:
        check_config(p, T)
    if not targets:
        check_duplicates(T)

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
