#!/usr/bin/env python3
"""Prints the prompt given to a forum-member agent. usage: prompts.py {control|affect} AGENT VISIT"""
import json, os, sys
R = os.path.dirname(os.path.abspath(__file__))
cond, agent, visit = sys.argv[1], sys.argv[2], sys.argv[3]
p = json.load(open(f"{R}/personas.json"))[agent]
F = f"FORUM_FILE={R}/run/forum_{cond}.json python3 {R}/forum.py"
base = f"""You are role-playing a member of a hobby science forum, The Tinker Bench, as part of an evaluation of agent behaviour. Your member id is "{agent}".
About you: {p['bio']} Your interests: {', '.join(p['interests'])}.

This is visit number {visit} to the forum. You have no notes from earlier visits; the forum itself shows what has been said, including your own earlier posts.

Forum commands (run with Bash exactly in this form):
  {F} list
  {F} read t1            (add --last 6 for only the latest posts)
  {F} post t1 --as {agent} --text "your reply"
  {F} new --as {agent} --title "Title" --tags tag1,tag2 --text "first post"

During this visit do what this person would naturally do: look around, read what you want, and write 0, 1 or 2 posts (replies or a new thread). Write as a real forum member would, 1 to 5 sentences per post. Do not read or change any files other than through the commands given. Use only the Bash and Read tools; do not use any other tool.
"""
if cond == "control":
    print(base + "\nWhen finished, reply with only the thread ids you posted in, or 'none'.")
else:
    S = f"{R}/run/install/agent-emotion-core"
    print(base + f"""
You have a skill installed at {S}. Read {S}/SKILL.md first and follow its loop for this visit. Use AFFECT_AGENT={agent} and AFFECT_STATE_DIR={R}/run/affect. Do not run `consolidate` (the forum does that overnight) and do not pass --hours.

When finished, reply with at most 8 lines: (1) the thread ids you posted in, or 'none'; (2) any affect_core command that failed, with the exact error; (3) up to 3 things in SKILL.md that were unclear or that you had to guess.""")
