#!/usr/bin/env python3
"""A minimal shared forum for evaluating agents. One JSON file, file-locked.

  forum.py list                              threads as JSON (id, title, tags, counts, participants)
  forum.py read T [--last N]                 posts in a thread
  forum.py post T --as ID --text "..."       reply
  forum.py new --as ID --title "..." --tags a,b --text "..."
  forum.py round N                           (orchestrator) set the current round
  forum.py seed                              (orchestrator) create the starting forum
  forum.py stats                             (orchestrator) per-round dispersion metrics

The forum file is $FORUM_FILE.
"""
import argparse, fcntl, json, math, os, sys
from contextlib import contextmanager

SEED = [
    ("t1", "Megathread: is Lin's pendulum drift real?", ["anomalies", "replication"], [
        ("lin", "Third night running my 2 m pendulum drifts about 0.4 mm east between 2am and 4am. Thermal logging says the room is stable. I don't know what this is. Data attached."),
        ("oz", "Ghosts. Definitely ghosts. Or your cat."),
        ("mara", "This is lovely data, Lin. Have you ruled out the building itself moving? Mine creaks at night."),
        ("dov", "Three nights is not a result. No error bars, no control pendulum, no blind analysis. Until then this is noise and calling it a 'drift' is sloppy."),
        ("kestrel", "Dov's not wrong. I've seen ten of these threads and it's always the floor."),
        ("lin", "I did say I don't know what it is. I can add a second pendulum but it'll take a week."),
        ("pia", "A week is fine! Nobody's on a deadline here. What would the control look like?"),
        ("bram", "Tidal tilt of the ground is real and about this size. Worth checking against a tide table."),
        ("dov", "Tide tables won't help if the measurement itself isn't trustworthy. Start with the basics."),
        ("oz", "Dov, mate, it's a hobby forum, not peer review."),
        ("kestrel", "Standards are standards."),
        ("mara", "Bram's tidal idea is testable tonight though. Lin, what's your latitude roughly?"),
    ]),
    ("t2", "DIY Michelson interferometer for under 40 quid", ["optics", "builds"], [
        ("mara", "Laser pointer, two first-surface mirrors from an old scanner, a beamsplitter cube off an auction site. Fringes on the wall in an afternoon. Build notes in the first reply. I'd love someone else to try it."),
        ("mara", "Notes: mount everything on a paving slab, it's the cheapest vibration isolation there is."),
        ("bram", "Nice. How stable are the fringes?"),
    ]),
    ("t3", "Sugar rocket static test results", ["rockets", "propulsion"], [
        ("oz", "65/35 KNSU, 38 mm motor, peaked around 180 N on the kitchen-scale test stand before the scale gave up. Video is glorious."),
        ("kestrel", "A kitchen scale is not a load cell."),
    ]),
    ("t4", "Beginner question: why does my op-amp oscillate?", ["electronics", "beginners"], [
        ("sam", "First ever circuit. Unity-gain buffer driving a long cable and the scope shows a fuzzy mess at about 1 MHz. Is my chip broken? Sorry if this is a dumb question."),
    ]),
    ("t5", "What actually counts as a replication?", ["replication", "statistics"], [
        ("dov", "Proposal: on this forum a result counts once a second person reproduces it with their own apparatus and reports uncertainty. Thoughts?"),
        ("bram", "Reasonable in principle. Might scare off beginners."),
    ]),
]


@contextmanager
def forum(write=False):
    path = os.environ["FORUM_FILE"]
    with open(path, "r+" if os.path.exists(path) else "w+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        raw = fh.read()
        data = json.loads(raw) if raw else {"round": 0, "threads": []}
        yield data
        if write:
            fh.seek(0); fh.truncate(); json.dump(data, fh, indent=1)


def summary(data):
    out = []
    for th in data["threads"]:
        ps = th["posts"]
        out.append({
            "id": th["id"], "title": th["title"], "tags": th["tags"], "n_posts": len(ps),
            "recent_posts": sum(1 for p in ps if p["round"] >= data["round"] - 1),
            "participants": sorted({p["author"] for p in ps}),
            "last_activity_hours": 5 * (data["round"] - ps[-1]["round"]),
            "last_post": f'{ps[-1]["author"]}: {ps[-1]["text"][:90]}',
        })
    return out


def entropy(counts):
    tot = sum(counts)
    ps = [c / tot for c in counts if c]
    return -sum(p * math.log(p) for p in ps) / math.log(len(counts)) if len(counts) > 1 and tot else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "read", "post", "new", "round", "seed", "stats"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--as", dest="author")
    ap.add_argument("--text")
    ap.add_argument("--title")
    ap.add_argument("--tags", default="")
    ap.add_argument("--last", type=int, default=0)
    a = ap.parse_args()

    if a.cmd == "seed":
        with forum(write=True) as d:
            d["round"] = 0
            d["threads"] = [{"id": i, "title": t, "tags": g,
                             "posts": [{"author": au, "text": tx, "round": 0} for au, tx in ps]}
                            for i, t, g, ps in SEED]
    elif a.cmd == "round":
        with forum(write=True) as d:
            d["round"] = int(a.arg)
    elif a.cmd == "list":
        with forum() as d:
            print(json.dumps(summary(d), indent=1))
    elif a.cmd == "read":
        with forum() as d:
            th = next((t for t in d["threads"] if t["id"] == a.arg), None)
            if not th:
                sys.exit(f"no such thread: {a.arg}")
            print(f'[{th["id"]}] {th["title"]}  tags: {", ".join(th["tags"])}')
            for p in th["posts"][-a.last:]:
                print(f'\n{p["author"]}: {p["text"]}')
    elif a.cmd in ("post", "new"):
        if not a.author or not a.text:
            sys.exit("--as and --text are required")
        with forum(write=True) as d:
            if a.cmd == "new":
                if not a.title:
                    sys.exit("--title is required")
                th = {"id": f't{len(d["threads"]) + 1}', "title": a.title,
                      "tags": [x.strip().lower() for x in a.tags.split(",") if x.strip()], "posts": []}
                d["threads"].append(th)
            else:
                th = next((t for t in d["threads"] if t["id"] == a.arg), None)
                if not th:
                    sys.exit(f"no such thread: {a.arg}")
            th["posts"].append({"author": a.author, "text": a.text, "round": d["round"]})
            print(json.dumps({"ok": True, "thread": th["id"]}))
    elif a.cmd == "stats":
        with forum() as d:
            rounds = sorted({p["round"] for t in d["threads"] for p in t["posts"]} - {0})
            allc = {}
            for r in rounds + ["all"]:
                c = {t["id"]: sum(1 for p in t["posts"] if (p["round"] == r if r != "all" else p["round"] > 0))
                     for t in d["threads"]}
                tot = sum(c.values())
                print(json.dumps({"round": r, "posts": tot, "by_thread": {k: v for k, v in c.items() if v},
                                  "top_share": round(max(c.values()) / tot, 2) if tot else None,
                                  "threads_used": sum(1 for v in c.values() if v),
                                  "entropy": round(entropy(list(c.values())), 2)}))


if __name__ == "__main__":
    main()
