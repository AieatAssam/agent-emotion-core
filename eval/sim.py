#!/usr/bin/env python3
"""Synthetic check of the dispersal mechanism. No LLM involved: it compares a
herding policy (always reply where activity x topic fit is highest) with
the core's choose(), on the same forum and the same random event stream.
"""
import math, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "agent-emotion-core", "scripts"))
import affect_core as ec

N_AGENTS, ROUNDS, HOURS_PER_ROUND = 8, 60, 2.0


def entropy(counts):
    tot = sum(counts.values())
    ps = [c / tot for c in counts.values() if c]
    return -sum(p * math.log(p) for p in ps) / math.log(max(2, len(counts)))


def run(policy, seed=7):
    rng = random.Random(seed)
    agents = [ec.EmotionalCore(f"agent{i}", seed=seed) for i in range(N_AGENTS)]
    threads = {f"t{i}": {"id": f"t{i}", "posts": [], "participants": set()} for i in range(5)}
    fit = {a.s["agent"]: {t: rng.uniform(0.3, 0.8) for t in threads} for a in agents}
    threads["t0"]["posts"] = [0.0] * 10          # one thread starts hot
    counts, skips, new = {}, 0, 0
    for r in range(ROUNDS):
        now = r * HOURS_PER_ROUND
        for a in agents:
            a.advance(HOURS_PER_ROUND)
            me = a.s["agent"]
            view = [{"id": t, "topic_match": fit[me].setdefault(t, rng.uniform(0.3, 0.8)),
                     "recent_posts": sum(1 for p in th["posts"] if now - p < 12),
                     "participants": sorted(th["participants"]),
                     "last_activity_hours": now - max(th["posts"], default=0)}
                    for t, th in threads.items()]
            if policy == "herd":
                best = max(view, key=lambda v: (1 + v["recent_posts"]) * v["topic_match"])
                dec = {"action": "reply", "thread": best["id"]}
            else:
                dec = a.choose(view, rng)
            if dec["action"] == "skip":
                skips += 1
                continue
            if dec["action"] == "new_thread":
                tid = f"t{len(threads)}"
                threads[tid] = {"id": tid, "posts": [], "participants": set()}
                new += 1
            else:
                tid = dec["thread"]
            th = threads[tid]
            others = sorted(th["participants"] - {me})
            th["posts"].append(now); th["participants"].add(me)
            counts[tid] = counts.get(tid, 0) + 1
            a.acted(dec["action"], tid)
            # what the agent read there: one random social event
            a.appraise({"event": "exchange", "thread": tid,
                        "source": rng.choice(others) if others else None,
                        "relevance": rng.uniform(.3, .9), "congruence": rng.uniform(-.7, .9),
                        "novelty": rng.uniform(.1, .9), "agency": "other",
                        "praiseworthiness": rng.uniform(-.6, .8), "control": rng.random()})
    top = max(counts.values()) / sum(counts.values())
    return {"posts": sum(counts.values()), "threads_used": len(counts), "new_threads": new,
            "skips": skips, "top_thread_share": round(top, 2),
            "entropy": round(entropy(counts), 2)}


if __name__ == "__main__":
    for pol in ("herd", "affect"):
        seeds = [run(pol, s) for s in range(1, 6)]
        avg = {k: round(sum(x[k] for x in seeds) / len(seeds), 2) for k in seeds[0]}
        print(f"{pol:8s}", avg)
