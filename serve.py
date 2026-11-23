# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Plan-work-verify harness running three specialized agent roles per task.

1. The planner inspects the task's files and writes a plan describing each
   deliverable, its path and format, and how to verify it.
2. The worker executes the task using the plan; its answer becomes the final
   message.
3. The gate role turns the task's hard requirements into a mechanical
   Python acceptance check -- required files at their exact paths, table
   headers and column order, value formats, ordering rules, counts --
   and recomputes the worker's calculation ledger (`/tmp/ple_ledger.tsv`)
   from its sources instead of rereading stated figures (P3-01/P3-02).
   It also audits the assumptions ledger (`/tmp/ple_assumptions.tsv`):
   each judgement's citation must check out in the source and each
   recorded duty must be stated in the deliverable (P3-03/P3-04).
   The harness compiles it, runs it in the task
   container and sends its `FAIL` lines back to the worker for up to
   `MAX_FIX_ROUNDS` rounds while sufficient time remains. For any round
   with no usable check, the verifier instead inspects the deliverables
   by hand and replies `PASS` or lists specific gaps.

The planner, gate and verifier receive only `bash` and `read_file` and are
instructed not to modify any files.

When the task message names MCP servers, every role also receives `mcp_list`
and `mcp_call`, which reach those servers through the evaluator's in-container
`http` request ([`docs/protocol.md`](../docs/protocol.md)).
"""

import asyncio
import json
import os
import re
import shlex

import openai
import taskbridge

MODEL = os.environ["MODEL_NAME"]
# The model's highest reasoning level: max for Claude, GLM, GPT-6 and
# DeepSeek-V4, high for the others (Gemini refuses max). REASONING_EFFORT
# overrides it.
MAX_EFFORT_MODELS = ("claude", "glm", "gpt-6", "deepseek-v4")
EFFORT = os.environ.get("REASONING_EFFORT") or (
    "max" if any(m in MODEL.lower() for m in MAX_EFFORT_MODELS) else "high"
)
# a fix round wraps up this long before the time limit, and a wrap-up call may
# take as long
WRAP_UP_SEC = 240
WRAP_UP = {
    "role": "user",
    "content": "Time is up for this step. Stop and reply with your answer.",
}
RESULT_CHARS = 20_000  # a longer tool result loses its middle
# Seconds between retries once the SDK's own quick retries are exhausted.
# $RETRY_WAITS overrides it (comma-separated) so contract tests can fail
# fast; production keeps the default backoff.
RETRY_WAITS = tuple(
    int(w) for w in os.environ.get("RETRY_WAITS", "5,15,30,60,120").split(",")
)
# How endpoints word a 400 saying the conversation no longer fits the context
# window: Claude, OpenAI and vLLM, Gemini, xAI.
CONTEXT_FULL = re.compile(
    r"context.?(length|window)|prompt is too long|maximum prompt length"
    r"|exceed[^.]{0,40}(token|context)",
    re.I,
)
CUT_KEEP = 1000  # characters a tool result keeps once the context is full
# DEF-003: a proactive context budget. $CONTEXT_TOKENS pins the endpoint's
# window (0: learn it from the endpoint once, see window_probe; if that
# also fails, from the first 400 overflow, see learn_window). The serve
# container receives no arbitrary host variables -- only submission.yaml's
# env -- so learning the window from the endpoint is what lets development
# (local stand-in) and production (declared model) share one entry with
# no pinned constant. A call goes out only once the conversation plus its
# reply budget fits the window minus $CTX_MARGIN_TOKENS; 0: a margin of
# window/12, at least 8000, because est_tokens (chars/4) undercounts
# code-heavy transcripts. Long old tool results are shortened before the
# call instead of the endpoint answering 400 and recover() cutting after
# the fact.
CONTEXT_TOKENS = int(os.environ.get("CONTEXT_TOKENS", "0"))
CTX_MARGIN = int(os.environ.get("CTX_MARGIN_TOKENS", "0"))
# real prompt tokens per est_tokens unit, from the last reply's usage (None:
# no reply yet). chars/4 drifts by content: EXP-026 #3 saw it run ~15% high
# in one phase and low in another, enough to pin the reply budget at its
# floor for 20 calls while the window still had room
CTX_RATIO = None
CTX_PROBED = False  # window_probe runs once per serve process
# never shrink the reply budget below this, even if the conversation alone
# no longer fits: let the reactive path handle it
CTX_MIN_ANSWER = 1024
# times in a row an empty or cut-off reply gets a "continue" before the run
# stops
MAX_NUDGES = 3
# lower it for a small context window
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "32000"))
# once the window is known, one reply never asks for more than this share of
# it: a reasoning model can spend a whole reply budget thinking (EXP-024: one
# 32K-token reply, all reasoning, half of a 64K window)
OUT_SHARE = 4
# a "length" reply this many tokens or more short of its budget was stopped by
# the window (EXP-026: three 200 replies stopped at 65,535 tokens, asked 32K)
CUT_SLACK = 16
# sent after a reply that hit the output limit before it wrote any answer:
# nothing of it reaches the conversation, so "continue where it stopped" would
# point at text the model cannot see
EMPTY_CUT = (
    "Your reasoning ran past the output limit before you wrote any answer,"
    " so none of it was kept. Answer now: keep your reasoning short and do"
    " detailed work with the tools."
)
# sent after a reply that hit the output limit inside a tool call: the call's
# arguments are cut, so it is not run (EXP-027: ~100 heredocs cut before
# their EOF line were run anyway, each writing a partial file)
CALL_CUT = (
    "Your reply hit the output limit ({limit} tokens) inside a tool call, so"
    " the call was cut off and not run. Make smaller calls: write a long file"
    " or script in parts (write the first part, then append the rest), and"
    " keep your reasoning short."
)
# a reply without a tool call that only announces work ("I will start by...",
# or a final summary listing "Next steps") is not an answer: EXP-027 #2's
# worker stopped on such a summary before writing any deliverable, and its
# planner and verifier answered one sentence of intent. Each step pushes back
# at most MAX_PUSHES times, then takes the reply as it is.
INTENT = re.compile(
    r"\s*(?:now,?\s+)?(?:I will|I'll|let me|I am going to|I'm going to)\b",
    re.I,
)
INTENT_CHARS = 800  # an announcement is short; a real plan or answer is not
NEXT_STEPS = re.compile(
    r"^\W*(?:next steps?|remaining (?:steps|work)|still to do)\b", re.I | re.M
)
MAX_PUSHES = 2
UNFINISHED = (
    "You described work that is still to do instead of doing it. Do it now"
    " with your tools, and reply without a tool call only once it is done."
)
# Claude caches a prompt prefix only when marked with cache_control. Each call
# marks the system prompt and the latest message (using 2 of Claude's 4 cache
# breakpoints) so each turn reads the prior conversation from cache. Other
# providers cache automatically without markers.
CACHE_MARK = "claude" in MODEL.lower()
# the planner wraps up once it has used this share of the task's time
PLAN_SHARE = 0.1
# the worker wraps up when this share is left, to keep time for checking and
# fixing
CHECK_SHARE = 0.25
# a check or a fix round starts only with this long to work before its own
# wrap-up
MIN_STEP_SEC = 120
MAX_FIX_ROUNDS = 2
# P3 mechanical acceptance check: where the gate script runs in the task
# container, and how much of its output reaches the worker as gaps.
GATE_PATH = "/tmp/ple_gate.py"
GATE_MAX_FAILS = 30
GATE_GAP_CHARS = 4000
GATE_SCRIPT_CHARS = 60_000
# The check roles (gate, its script, verifier) must not change the
# deliverables, but their tools can (EXP-026 #3: the gate script ran
# `zip -u` and added duplicates to submission.zip; EXP-028 #1: the gate
# wrote acceptance_check.py into the task folder). GUARD snapshots the
# workdir before the check and afterwards removes what is new and restores
# what changed. Files over GUARD_FILE_MB, or past GUARD_TOTAL_MB in all,
# are only compared (named in the log if changed, not restored).
GUARD_PATH = "/tmp/ple_guard.py"
GUARD = r'''
import json, os, sys, tarfile
root, mode = sys.argv[1], sys.argv[2]
snap = os.environ.get("PLE_GUARD_SNAP", "/tmp/ple_check_snap")
one, total_cap = int(sys.argv[3]) << 20, int(sys.argv[4]) << 20

def walk():
  files, dirs = {}, set()
  for d, subdirs, names in os.walk(root):
    dirs.add(d)
    for name in names:
      p = os.path.join(d, name)
      try:
        st = os.lstat(p)
      except OSError:
        continue
      files[p] = [st.st_size, st.st_mtime_ns]
  return files, dirs

if mode == "save":
  files, dirs = walk()
  kept, total = [], 0
  with tarfile.open(snap + ".tar", "w") as tar:
    for p, (size, _) in sorted(files.items()):
      if size <= one and total + size <= total_cap:
        try:
          tar.add(p, recursive=False)
        except OSError:
          continue
        kept.append(p)
        total += size
  with open(snap + ".json", "w") as f:
    json.dump({"files": files, "dirs": sorted(dirs), "kept": kept}, f)
  sys.exit(0)
try:
  with open(snap + ".json") as f:
    saved = json.load(f)
except OSError:
  sys.exit(0)
old, kept = saved["files"], set(saved["kept"])
files, dirs = walk()
added = [p for p in files if p not in old]
changed = [p for p in old if files.get(p) != old[p]]
for p in added:
  try:
    os.remove(p)
  except OSError:
    pass
for d in sorted(dirs - set(saved["dirs"]), key=len, reverse=True):
  try:
    os.rmdir(d)
  except OSError:
    pass
back = [p for p in changed if p in kept]
trusted = hasattr(tarfile, "fully_trusted_filter")
kw = {"filter": "fully_trusted"} if trusted else {}
with tarfile.open(snap + ".tar") as tar:
  for p in back:
    try:
      tar.extract(tar.getmember(p.lstrip("/")), "/", **kw)
      os.utime(p, ns=(old[p][1], old[p][1]))  # tar keeps mtime as a float
    except (KeyError, OSError):
      pass
for ext in (".json", ".tar"):  # a snapshot is used once
  try:
    os.remove(snap + ext)
  except OSError:
    pass
lost = [p for p in changed if p not in kept]
if added or changed:
  note = f", could not restore {len(lost)} (too big): {lost[:3]}"
  print(f"undid the check's writes under {root}: removed {len(added)} new"
        f" file(s), restored {len(back)} changed or deleted"
        + (note if lost else "") + f"; e.g. {(added + changed)[:3]}")
'''
GUARD_FILE_MB = 50
GUARD_TOTAL_MB = 1000
# lines of a crashed gate script's output sent back in its repair turn
GATE_CRASH_LINES = 15
# sent once when the gate's script ran but gave no verdict (EXP-028 #3/#4:
# four scripts compiled, then stopped at `import pandas`, which the task
# container does not have)
GATE_RUN_REPAIR = (
    "Your script ran in the task container but {why}\n\nFix it -- use only"
    " the standard library and modules you have checked import there -- and"
    " reply with the whole corrected script in one fenced code block and"
    " nothing else."
)
# sent once when the gate's script does not compile
GATE_REPAIR = (
    "Your script does not compile ({why}). Reply with the whole corrected"
    " script in one fenced code block and nothing else."
)
# A FAIL line saying the check's own tooling is missing (a bare command or a
# Python module, not a deliverable path) reports a broken check, not a gap
# in the files: EXP-024's gate called `strings`, absent from the container,
# and two fix rounds reread files that were fine. A missing file named by a
# path stays a gap.
CHECK_BROKE = re.compile(
    r"No such file or directory: '[^'/]+'|command not found"
    r"|No module named|ModuleNotFoundError|NameError",
    re.I,
)
# The endpoint key the evaluator provides. Log lines are free text the
# graders record, so anything logged passes through `safe`, which replaces
# the key (asserted by the `redaction` case in tests/mock_contract_test.py).
API_KEY = os.environ.get("OPENAI_API_KEY", "")


def safe(text):
  """Returns `text` with the API key replaced by a placeholder.

  Args:
    text: Any string about to be sent as a `log` frame.

  Returns:
    The text with every occurrence of `$OPENAI_API_KEY` replaced.
  """
  return text.replace(API_KEY, "<api-key>") if API_KEY else text

# The evaluator sets OPENAI_BASE_URL and OPENAI_API_KEY for every model.
# The SDK handles quick retries; recover() handles longer backoffs. Because
# calls are non-streaming, a max-effort response can take over 15 minutes
# before any bytes arrive, so the timeout matches the egress proxy's 30-minute
# idle limit.
client = openai.AsyncOpenAI(max_retries=5, timeout=1800)

PLANNER = """You plan an engineering task that another engineer will carry out in a Linux container with no internet \
access. Inspect the task's files with your tools (bash starts in {workdir}), but do not create or change any file. \
Then reply with the plan: each deliverable with its exact path and format, what it must contain, the data and method \
to use, and how to check it."""

WORKER = """You are an expert engineer working on a task in a Linux container with no internet access. Your tools \
act inside it, and bash starts in {workdir}. A plan for the task follows it; use it, and correct it where the files \
show it is wrong. Compute with code, not by hand. Keep a calculation ledger: each time you derive a figure the \
task's files imply rather than state, append one tab-separated line to `/tmp/ple_ledger.tsv` -- id, deliverable \
path, value, source files, formula -- converting units inside the computing code (in/ft, CF/CY, LF) and rounding \
only where the task says to. Keep an assumptions ledger too: for every judgement of what the files mean (which \
item a change belongs to, which quantity convention applies) and for every duty, acceptance or decision a cited \
source states that the deliverable must reflect, append one tab-separated line to `/tmp/ple_assumptions.tsv` -- \
statement, exact source citation (file, and sheet, row or section), the alternative reading considered, and why \
this one was chosen. Write each deliverable exactly where and in the format the task \
asks, then open it again to check it. An archive holds its files at its top level unless the task says \
otherwise: build it from inside the folder (`cd dir && zip out.zip a b`), never from an absolute path, and list \
its entries to check. When you are done, reply without calling a tool: a short summary of each \
deliverable, where it is, and the key results."""

VERIFIER = """You check an engineer's work on a task in a Linux container. You get the task, the plan, and the \
engineer's summary of what was delivered. Open every deliverable with your tools (bash starts in {workdir}) and check \
it against the task: the path, the format, the entry paths inside an archive, every part the task asks for, and the key numbers, recomputed. Do not \
create or change any file. If everything holds, reply with the single word PASS and nothing else. Otherwise reply \
with a numbered list of the gaps, each specific enough to fix."""

GATE = """You turn an engineering task into a mechanical acceptance check that runs before the \
delivery is accepted. The task and a plan follow; an engineer has already produced the files. Open the \
deliverables with your tools (bash starts in {workdir}), but do not create or change any file under the \
task folders (scratch files may live in /tmp). Reply with a single Python 3 script in one fenced code \
block and nothing else. The script runs as `python3` inside the task container: it may read any task \
file, write only under /tmp, import only the standard library and modules you have checked import there \
(`python3 -c 'import openpyxl'`), prints one line per hard requirement the task states -- `PASS <id>` when it \
holds, `FAIL <id>: <what is wrong, and in which file and row>` when it does not -- cheapest checks first, \
and exits 0 either way. Cover every mechanically checkable requirement: each required file at its exact \
path (inside an archive, at its exact entry path, top level unless the task says otherwise), table headers, column names and column order, value formats such as drawing-number and \
revision-suffix rules, row and sheet ordering, required sections and counts. Recompute, never reread: \
the engineer may leave `/tmp/ple_ledger.tsv` with one row per derived figure (id, deliverable path, \
value, source files, formula). If it exists your script must read every row and recompute each value \
from its source files -- inputs read fresh, units converted in the code -- printing `PASS <id>` only \
when the recomputed value matches what the deliverables state, else `FAIL <id>: stated <X> but \
recomputed <Y> from <source>`; key derived figures stated without a ledger row get the same \
treatment. A ledger figure obtained by counting or enumerating records -- a count, a list, a \
sum over matched rows -- must not be checked against only the records the ledger cites: \
re-enumerate the matching population from the source yourself, recompute from that population, \
and print `FAIL C<id>: ledger counts <N> but the source holds <M> -- <the missed or extra \
records>` when they differ. Check `/tmp/ple_assumptions.tsv` too if present: for each recorded \
judgement verify its \
citation actually says that in the source, and for each recorded duty or accepted fact verify the \
deliverable states it -- `FAIL A<id>: <duty or choice, with its source citation> is not stated or \
not supported` names the file at fault. Never credit a figure for appearing in two files. Leave \
purely stylistic preferences out."""


def tool(name, description, **params):
  """Builds an OpenAI function-tool definition dictionary.

  Args:
    name: Tool function name.
    description: Human-readable tool description.
    **params: Parameter names mapped to their JSON Schema type strings.

  Returns:
    An OpenAI function-tool specification dictionary.
  """
  return {
      "type": "function",
      "function": {
          "name": name,
          "description": description,
          "parameters": {
              "type": "object",
              "properties": {k: {"type": v} for k, v in params.items()},
              "required": list(params),
          },
      },
  }


TOOLS = [
    tool(
        "bash",
        "Run a bash command (120 s limit) and return its exit code and output.",
        command="string",
    ),
    tool("read_file", "Read a text file.", path="string"),
    tool(
        "write_file",
        "Create or overwrite a file; parent folders are created.",
        path="string",
        content="string",
    ),
]
READ_ONLY = TOOLS[:2]
# Added for every role only when the task's message names MCP servers. A task
# server's catalog can hold hundreds of tools (~500 KB), so the model
# discovers tools through `mcp_list` instead of the full catalog being inlined
# into every model call.
MCP_TOOLS = [
    tool(
        "mcp_list",
        "List one of this task's MCP servers' tools: their names,"
        " descriptions and argument schemas. Call it before mcp_call.",
        server="string",
    ),
    tool(
        "mcp_call",
        "Run one of this task's MCP servers' tools. `tool` must be a name"
        " returned by mcp_list and `args_json` a JSON object holding that"
        " tool's arguments.",
        server="string",
        tool="string",
        args_json="string",
    ),
]


def clip(text):
  """Truncates `text` in the middle if it exceeds `RESULT_CHARS` characters.

  Args:
    text: Tool output string to clip.

  Returns:
    The original string if within `RESULT_CHARS`, or a middle-truncated string.
  """
  if len(text) <= RESULT_CHARS:
    return text
  half = RESULT_CHARS // 2
  return (
      f"{text[:half]}\n[... {len(text) - RESULT_CHARS} characters cut"
      f" ...]\n{text[-half:]}"
  )


def marked(messages):
  """Returns the messages a model call sends.

  For Claude, this is a copy whose system prompt and newest message carry
  `cache_control`. The stored conversation stays as it is, so each turn marks
  its own newest message.

  Args:
    messages: The conversation so far, in OpenAI chat format.

  Returns:
    `messages` itself for other models, or the marked copy for Claude.
  """
  if not CACHE_MARK:
    return messages
  out = list(messages)
  for i in {0, len(out) - 1}:
    m, content = out[i], out[i].get("content")
    if isinstance(content, str) and content:
      out[i] = {
          **m,
          "content": [{
              "type": "text",
              "text": content,
              "cache_control": {"type": "ephemeral"},
          }],
      }
    else:
      out[i] = {**m, "cache_control": {"type": "ephemeral"}}
  return out


async def run_tool(session, fn):
  """Executes a single tool call in the task container and returns its output.

  Rewrites `fn["arguments"]` as canonical JSON (or `"{}"` if invalid) so the
  conversation history remains valid for strict endpoints. Any tool failure is
  returned as an error string for the model.

  Args:
    session: Active `taskbridge.Session` connected to the task container.
    fn: Function-call dictionary containing `name` and `arguments`.

  Returns:
    The clipped tool output or error string to send back to the model.
  """
  name = fn["name"]
  try:
    args = json.loads(fn["arguments"] or "{}")
    if not isinstance(args, dict):
      raise TypeError("not a JSON object")
    fn["arguments"] = json.dumps(args, allow_nan=False)
  except (TypeError, ValueError) as exc:
    fn["arguments"] = "{}"
    return (
        f"error: the arguments are not a JSON object ({exc}); send the call"
        " again"
    )
  try:
    if name == "bash":
      result = await session.exec(args["command"])
      return clip(f"exit code {result['exit_code']}\n{result['output']}")
    if name == "read_file":
      return clip(
          (await session.read_file(args["path"])).decode("utf-8", "replace")
      )
    if name == "write_file":
      return (
          f"wrote {await session.write_file(args['path'], args['content'])}"
          f" bytes to {args['path']}"
      )
    if name == "mcp_list":
      tools = _mcp_tools.get(args["server"])
      if tools is None:
        return f"error: no MCP server named {args['server']}{_known()}"
      return clip(
          "\n".join(
              f"- {t['name']}: {t['description'][:200]} | arguments:"
              f" {json.dumps(t['inputSchema'], separators=(',', ':'))[:400]}"
              for t in tools
          )
      )
    if name == "mcp_call":
      client = _mcp.get(args["server"])
      if client is None:
        return f"error: no MCP server named {args['server']}{_known()}"
      try:
        tool_args = json.loads(args["args_json"] or "{}")
      except ValueError as exc:
        return (
            f"error: args_json is not a JSON object ({exc}); send the call"
            " again"
        )
      if not isinstance(tool_args, dict):
        return "error: args_json is not a JSON object; send the call again"
      return clip(
          json.dumps(
              await client.call_tool(args["tool"], tool_args),
              ensure_ascii=False,
          )
      )
    return f"error: there is no tool named {name}"
  # ValueError: content with an unpaired surrogate
  except (
      taskbridge.TaskError,
      taskbridge.MCPError,
      KeyError,
      ValueError,
  ) as exc:
    return f"error: {type(exc).__name__}: {exc}"


async def recover(session, messages, exc, waits, until):
  """Handles a failed model call and returns whether to retry.

  On a 400 context-overflow error, shortens the oldest tool results. On a rate
  limit, server error, or connection drop, sleeps for the next interval in
  `RETRY_WAITS` (capped at the step's wrap-up deadline). Errors are logged
  rather than added to the conversation.

  Args:
    session: Active `taskbridge.Session` for the task.
    messages: The conversation, shortened in place when the context is full.
    exc: The `openai.APIError` the call raised.
    waits: Iterator over the remaining intervals in `RETRY_WAITS`.
    until: Seconds before the time limit at which the step wraps up.

  Returns:
    `True` to retry the call, `False` to re-raise.
  """
  status = getattr(exc, "status_code", None)  # None: no HTTP answer
  if status == 400 and CONTEXT_FULL.search(str(exc)):
    await learn_window(session, ctx_used(messages))
    return await shorten(session, messages)
  wait = next(waits, None)
  if wait is None or not (
      status is None or status in (408, 409, 429) or status >= 500
  ):
    return False
  left = session.time_left()
  if left is not None and left > until:
    wait = min(wait, left - until)
  await session.log(
      safe(f"model call failed ({str(exc)[:200]}); again in {wait:.0f} s")
  )
  await asyncio.sleep(wait)
  return True


def est_tokens(messages):
  """Estimates how many prompt tokens `messages` will take (chars / 4).

  A rough estimate; its only job is deciding when to shorten the
  conversation before sending it.

  Args:
    messages: The conversation so far, in OpenAI chat format.

  Returns:
    The estimated prompt token count.
  """
  return len(json.dumps(messages, ensure_ascii=False)) // 4


def ctx_used(messages):
  """Estimates the real prompt tokens of `messages`: chars/4, calibrated.

  Scales `est_tokens` by `CTX_RATIO`, the real-to-estimate ratio the last
  reply's `usage.prompt_tokens` showed (it also absorbs the tool
  definitions, which est_tokens does not see). Before any reply, chars/4.

  Args:
    messages: The conversation so far, in OpenAI chat format.

  Returns:
    The estimated prompt token count in the endpoint's own tokens.
  """
  est = est_tokens(messages)
  return int(est * CTX_RATIO) if CTX_RATIO else est


async def window_probe(session):
  """Asks the model endpoint once what context window it actually serves.

  LiteLLM-style proxies and most providers announce the window on
  `/v1/models` (`max_model_len`, `max_context_length` or `context_length`).
  Learning it lets the proactive budget match the endpoint that is really
  wired up -- the local stand-in during development, the declared model
  on the evaluation server -- without pinning either constant into the
  entry. A failure leaves the budget off; the reactive post-400 cut is
  the backstop either way.

  Args:
    session: Active `taskbridge.Session` for the task.
  """
  global CONTEXT_TOKENS
  try:
    listed = await asyncio.wait_for(client.models.list(), timeout=30)
  except Exception as exc:  # endpoint may not expose /v1/models at all
    await session.log(
        f"context window: probe failed ({type(exc).__name__});"
        " reactive path only"
    )
    return
  wins = {}
  for m in getattr(listed, "data", None) or []:
    fields = m.model_dump() if hasattr(m, "model_dump") else {}
    win = next(
        (fields[k] for k in
         ("max_model_len", "max_context_length", "context_length")
         if isinstance(fields.get(k), int) and fields[k] > 0),
        0,
    )
    if win:
      wins[str(getattr(m, "id", ""))] = win
  if not wins:
    await session.log(
        "context window: not announced by the endpoint;"
        " reactive path only"
    )
    return
  win = wins.get(MODEL) or min(wins.values())
  CONTEXT_TOKENS = win
  await session.log(
      f"context window: {win} tokens (announced by the endpoint)"
  )


async def learn_window(session, seen, how="an overflow"):
  """Takes the size of a conversation that hit the window as the window.

  Two signals reach here, both in the endpoint's own tokens. A refused
  prompt (400): the window is at most `ctx_used` of what was sent. A reply
  the server stopped at the window rather than at the reply budget (Ollama
  answers 200, `finish_reason` "length", fewer tokens than asked): the
  window is that reply's prompt plus completion tokens, exactly. Keeping it
  as `CONTEXT_TOKENS` arms the proactive budget for the rest of the task,
  so one hit per serve process replaces one per step (and per refilled
  context). A known window is only ever lowered: a hit under it means the
  estimate ran low.

  Args:
    session: Active `taskbridge.Session` for the task.
    seen: Tokens of the conversation that hit the window.
    how: What hit the window, for the log line.
  """
  global CONTEXT_TOKENS
  if CONTEXT_TOKENS and seen >= CONTEXT_TOKENS:
    return
  CONTEXT_TOKENS = seen
  await session.log(f"context window: learned {seen} tokens from {how}")


def cut_args(arguments):
  """Shortens each long string in a tool call's JSON arguments.

  Args:
    arguments: The call's `function.arguments` JSON text.

  Returns:
    The arguments with every string over `CUT_KEEP` characters cut to
    `CUT_KEEP`, still valid JSON; unchanged when they are not a JSON object.
  """
  try:
    args = json.loads(arguments)
  except ValueError:
    return arguments
  if not isinstance(args, dict):
    return arguments
  note = "\n[... cut to save context; already run]"
  for key, value in args.items():
    if isinstance(value, str) and len(value) > CUT_KEEP:
      args[key] = value[:CUT_KEEP] + note
  return json.dumps(args, ensure_ascii=False)


def cuttable(message):
  """Whether `shorten` can make `message` shorter.

  Args:
    message: One chat message.

  Returns:
    True for a tool result over 2 * `CUT_KEEP` characters, or an assistant
    turn with a tool call whose arguments `cut_args` shortens by that much.
  """
  if message["role"] == "tool":
    return len(message["content"]) > 2 * CUT_KEEP
  calls = message.get("tool_calls") or ()
  return any(
      len(a) - len(cut_args(a)) > CUT_KEEP
      for a in (c["function"]["arguments"] for c in calls)
  )


async def shorten(session, messages, tag="context full"):
  """Cuts the older half of long tool results and tool-call arguments.

  A tool result keeps its first `CUT_KEEP` characters; a tool call keeps
  each argument string's first `CUT_KEEP` (the call already ran, and file
  contents written through a call fill a 64K window as fast as results do,
  EXP-027). Repeated calls cut progressively newer messages. Claude's
  thinking blocks are kept intact because each block's signature is
  self-contained and Claude rejects tool loops if the latest assistant turn
  loses its thinking block.

  Args:
    session: Active `taskbridge.Session` for the task.
    messages: The conversation, modified in place.
    tag: Log line prefix naming the trigger ("context full" after a 400,
      "context budget" before a call that would not fit).

  Returns:
    Whether anything was cut.
  """
  long = [n for n, m in enumerate(messages) if cuttable(m)]
  if not long:
    return False
  cut = long[: max(1, len(long) // 2)]
  for n in cut:
    m = messages[n]
    if m["role"] == "tool":
      m["content"] = (
          m["content"][:CUT_KEEP]
          + "\n[... cut to save context; run the tool again if needed]"
      )
      continue
    for call in m["tool_calls"]:
      call["function"]["arguments"] = cut_args(call["function"]["arguments"])
  await session.log(f"{tag}: cut {len(cut)} old tool results")
  return True


def unfinished(text, final):
  """Whether a reply without a tool call only announces work still to do.

  Args:
    text: The reply's content.
    final: Whether the step's answer is the worker's summary, where a "Next
      steps" list means the deliverables are not done yet.

  Returns:
    True for a short reply opening with an intent ("I will...", "Let
    me..."), or a final summary with a "Next steps" heading.
  """
  if INTENT.match(text) and len(text) < INTENT_CHARS:
    return True
  return final and bool(NEXT_STEPS.search(text))


# a fenced code block; the closing fence is a line of its own, so a script
# that checks Markdown for "```" is not cut at that string (EXP-028 #2: four
# gate scripts lost to `startswith('```json')` and the like)
GATE_FENCE = re.compile(
    r"```(?:[Pp]ython\d*)?[^\S\n]*\n(.*?)^[^\S\n]*```[^\S\n]*$", re.S | re.M
)


def gate_body(reply):
  """Returns the gate reply's script source and where it came from.

  Args:
    reply: The gate agent's final text.

  Returns:
    `(body, where)`: the first fenced code block, or the whole reply when
    it has none, stripped; `where` says which, for the log.
  """
  found = GATE_FENCE.search(reply)
  if found:
    return found.group(1).strip(), "code block"
  return reply.strip(), "no code block, whole reply"


def gate_script(reply):
  """Extracts the gate agent's Python acceptance check from its reply.

  Takes the first fenced code block, or the whole reply when untagged.
  The source is accepted only if it compiles and is a sane size, so the
  harness never writes a truncated or prose answer into the container.

  Args:
    reply: The gate agent's final text.

  Returns:
    The script source, or None when no usable script was produced.
  """
  body, _ = gate_body(reply)
  if not body or len(body) > GATE_SCRIPT_CHARS:
    return None
  try:
    compile(body, "ple_gate", "exec")
  except (SyntaxError, ValueError):
    return None
  return body


def gate_why(reply):
  """Says why `gate_script` found no usable script in `reply` (for the log).

  Args:
    reply: The gate agent's final text.

  Returns:
    A short reason: an empty reply, its size, or the syntax error.
  """
  body, where = gate_body(reply)
  if not body:
    return "empty reply"
  if len(body) > GATE_SCRIPT_CHARS:
    return f"{where}: {len(body)} chars, over {GATE_SCRIPT_CHARS}"
  try:
    compile(body, "ple_gate", "exec")
  except SyntaxError as exc:
    lines = body.splitlines()
    n = exc.lineno or 0
    line = lines[n - 1].strip()[:120] if 0 < n <= len(lines) else ""
    return f"{where}: SyntaxError {exc.msg} at line {n}: {line!r}"
  except ValueError as exc:
    return f"{where}: ValueError {str(exc)[:120]}"
  return "ok"


async def guard(session, mode):
  """Snapshots the workdir ("save") or undoes changes since then ("restore").

  Skipped when the workdir is the container root. A guard that fails is
  logged and never stops the run.

  Args:
    session: Active `taskbridge.Session` connected to the task container.
    mode: "save" before the check roles run, "restore" after them (only
      after a save that succeeded).

  Returns:
    Whether the command ran and exited 0.
  """
  root = session.workdir.rstrip("/")
  if not root:
    return False
  try:
    if mode == "save":
      await session.write_file(GUARD_PATH, GUARD)
    result = await session.exec(
        f"python3 {GUARD_PATH} {shlex.quote(root)} {mode}"
        f" {GUARD_FILE_MB} {GUARD_TOTAL_MB}",
        timeout_sec=300,
    )
  except taskbridge.TaskError as exc:
    await session.log(safe(f"check guard: {mode} failed ({str(exc)[:200]})"))
    return False
  out = (result["output"] or "").strip()
  if out:
    await session.log(safe(f"check guard: {out[:600]}"))
  return result.get("exit_code") == 0


async def gate_run(session, script):
  """Runs the gate check inside the task container and reads its verdict.

  Args:
    session: Active `taskbridge.Session` connected to the task container.
    script: Python source of the gate check.

  Returns:
    `(verdict, crash)`. `verdict` is "PASS" when no printed line starts
    with FAIL, the FAIL lines (capped to `GATE_MAX_FAILS` lines and
    `GATE_GAP_CHARS` characters) as the gap list when some do, or None
    when the run printed no verdict lines or a FAIL line shows the check's
    own tooling is missing (`CHECK_BROKE`); `crash` then says what the
    script printed, for the gate's repair turn ("" otherwise).
  """
  try:
    await session.write_file(GATE_PATH, script)
    result = await session.exec(f"python3 {GATE_PATH}")
  except taskbridge.TaskError as exc:
    await session.log(safe(f"gate: run error ({str(exc)[:200]})"))
    return None, f"the run failed: {str(exc)[:500]}"
  lines = [ln.strip() for ln in (result["output"] or "").splitlines()]
  fails = [ln for ln in lines if ln.upper().startswith("FAIL")]
  passes = [ln for ln in lines if ln.upper().startswith("PASS")]
  if not fails and not passes:
    tail = " ".join(lines[-3:])[:200]
    await session.log(
        safe(
            f"gate: no verdict lines (exit {result['exit_code']}:"
            f" {tail})"
        )
    )
    shown = "\n".join(lines[-GATE_CRASH_LINES:])[-GATE_GAP_CHARS:]
    return None, (
        f"it exited {result['exit_code']} without printing any PASS or"
        f" FAIL line; its last output:\n{shown}"
    )
  if not fails:
    return "PASS", ""
  broke = [ln for ln in fails if CHECK_BROKE.search(ln)]
  if broke:
    await session.log(
        safe(f"gate: check itself failed ({broke[0][:200]})")
    )
    return None, f"its own tooling is missing:\n{broke[0][:500]}"
  return "\n".join(fails[:GATE_MAX_FAILS])[:GATE_GAP_CHARS], ""


def conversation(system, session, prompt):
  """Creates the initial `[system, user]` message list for a role.

  Args:
    system: System prompt template containing `{workdir}`.
    session: Active `taskbridge.Session` providing `workdir`.
    prompt: Initial user message content.

  Returns:
    A two-element list of OpenAI chat message dictionaries.
  """
  return [
      {"role": "system", "content": system.format(workdir=session.workdir)},
      {"role": "user", "content": prompt},
  ]


# MCP clients and tool catalogs for the current task, keyed by server name;
# filled by setup_mcp and read by run_tool's mcp_list / mcp_call.
_mcp: dict[str, taskbridge.MCPClient] = {}
_mcp_tools: dict[str, list[dict]] = {}


def _known():
  """Returns a `, (known: a, b)` suffix listing the connected MCP servers."""
  return f" (known: {', '.join(_mcp)})" if _mcp else ""


async def setup_mcp(session):
  """Connects to the task's MCP servers and caches their tool catalogs.

  A server that refuses the handshake or paging of its catalog is logged and
  skipped; its name then stays out of `_mcp`.

  Args:
    session: Active `taskbridge.Session` for the task.
  """
  _mcp.clear()
  _mcp_tools.clear()
  for server in session.mcp_servers:
    name = str(server.get("name") or server.get("url") or "")
    url = str(server.get("url") or "")
    if not name or not url:
      continue
    try:
      client = taskbridge.MCPClient(session, url)
      await client.initialize()
      tools = await client.list_tools()
    except (taskbridge.MCPError, taskbridge.TaskError) as exc:
      await session.log(safe(f"mcp {name}: no tools ({str(exc)[:200]})"))
      continue
    _mcp[name], _mcp_tools[name] = client, tools
    await session.log(f"mcp {name}: {len(tools)} tools")


async def agent(session, messages, tools, until, final=False):
  """Runs the tool-calling loop on `messages` until the model answers.

  Prompts the model to wrap up immediately once fewer than `until` seconds
  remain on the task clock. When `final` is `True`, updates
  `session.final_message` with each non-empty response.

  Args:
    session: Active `taskbridge.Session` for the task.
    messages: Mutable conversation history list.
    tools: List of OpenAI tool definitions available to this role.
    until: Remaining task time threshold (in seconds) at which this step wraps
      up.
    final: Whether to record responses in `session.final_message`.

  Returns:
    The final text response produced by this agent step.
  """
  # head: the start of an answer cut off at the output limit
  nudges, head, waits = 0, "", iter(RETRY_WAITS)
  pushes = 0  # replies sent back for announcing work instead of doing it
  while True:
    left = session.time_left()  # None when the task has no time limit
    wrap_up = left is not None and left < until
    if wrap_up and messages[-1:] != [WRAP_UP]:  # asked once, also on a retry
      messages.append(dict(WRAP_UP))
    # A call still running when the wrap-up starts is stopped. The wrap-up call
    # itself gets at most WRAP_UP_SEC and stops at the time limit; if it takes
    # longer, the step returns head, its answer so far.
    if left is None:
      timeout = None
    elif wrap_up:
      timeout = min(WRAP_UP_SEC, left)
    else:
      timeout = left - until
    # DEF-003: with a known window ($CONTEXT_TOKENS or the endpoint's
    # announced one), trim old tool results before sending so the
    # conversation plus its reply budget fits; the reply budget itself
    # shrinks to the room left. The reactive cut in recover() stays as
    # the backstop for unknown or mis-declared windows.
    global CTX_PROBED, CTX_RATIO
    if not CTX_PROBED:
      CTX_PROBED = True
      if not CONTEXT_TOKENS:
        await window_probe(session)
    max_out = MAX_OUTPUT_TOKENS
    if CONTEXT_TOKENS:
      margin = CTX_MARGIN or max(8000, CONTEXT_TOKENS // 12)
      room = CONTEXT_TOKENS - margin - ctx_used(messages)
      if room < 0:
        await session.log(
            f"context budget: over by {-room} tokens;"
            " shortening old tool results"
        )
      while room < CTX_MIN_ANSWER:
        if not await shorten(session, messages, tag="context budget"):
          room = CTX_MIN_ANSWER  # bare conversation alone does not fit
          break
        room = CONTEXT_TOKENS - margin - ctx_used(messages)
      max_out = max(
          CTX_MIN_ANSWER,
          min(MAX_OUTPUT_TOKENS, CONTEXT_TOKENS // OUT_SHARE, room),
      )
    sent = est_tokens(messages)
    try:
      reply = await asyncio.wait_for(
          client.chat.completions.create(
              model=MODEL,
              messages=marked(messages),
              tools=tools,
              tool_choice="none" if wrap_up else "auto",
              reasoning_effort=EFFORT,
              max_completion_tokens=max_out,
          ),
          timeout,
      )
    except asyncio.TimeoutError:
      if wrap_up:
        return head
      continue
    except openai.APIError as exc:
      if await recover(session, messages, exc, waits, until):
        continue
      raise
    waits = iter(RETRY_WAITS)
    if reply.usage:
      details = getattr(reply.usage, "prompt_tokens_details", None)
      await session.usage(
          MODEL,
          reply.usage.prompt_tokens,
          reply.usage.completion_tokens,
          getattr(details, "cached_tokens", 0) or 0,
      )
    message, cut = (
        reply.choices[0].message,
        reply.choices[0].finish_reason == "length",
    )
    # stopped short of the reply budget: the window, not the budget, ended it
    # (Ollama keeps answering 200 there, so no 400 ever teaches recover())
    seen = reply.usage.prompt_tokens if reply.usage else 0
    made = reply.usage.completion_tokens if reply.usage else None
    if seen and sent:
      CTX_RATIO = seen / sent
    if cut and seen and made is not None and made + CUT_SLACK < max_out:
      await learn_window(session, seen + made, "a reply cut at the window")
    text = head + (message.content or "")
    if final and text:
      session.final_message = text
    # sent back as returned: Gemini refuses a tool call without its thought
    # signature
    turn = message.model_dump(exclude_none=True)
    if wrap_up or not message.tool_calls or cut:
      # calls made at the wrap-up, or cut off at the output limit, are not run
      turn.pop("tool_calls", None)
      if message.content:
        # a fix round, or the request to go on after a cut-off reply, continues
        # from this answer
        messages.append(turn)
      if (
          not wrap_up and not cut and pushes < MAX_PUSHES
          and unfinished(message.content or "", final)
      ):
        pushes, nudges, head = pushes + 1, 0, ""
        await session.log(
            "reply announces work still to do; asking to do it"
        )
        messages.append({"role": "user", "content": UNFINISHED})
        continue
      if wrap_up or (message.content and not cut) or nudges == MAX_NUDGES:
        return text
      nudges, head = nudges + 1, text
      if message.tool_calls:  # cut off inside a call
        await session.log(
            "reply cut off inside a tool call; call not run, asking for"
            " smaller calls"
        )
        nudge = CALL_CUT.format(limit=max_out)
      elif cut and not message.content:
        await session.log(
            "reply cut off before any answer (reasoning only);"
            " asking for the answer"
        )
        nudge = EMPTY_CUT
      elif cut:
        nudge = "Your reply was cut off; continue where it stopped."
      else:
        nudge = "Continue, and finish with your answer."
      messages.append({"role": "user", "content": nudge})
      continue
    nudges, head = 0, ""
    messages.append(turn)
    for call in turn["tool_calls"]:
      await session.log(
          safe(
              f"{call['function']['name']}"
              f" {call['function']['arguments'][:200]}"
          )
      )
      content = await run_tool(session, call["function"])
      messages.append(
          {"role": "tool", "tool_call_id": call["id"], "content": content}
      )
    if left is not None:
      messages[-1]["content"] += (
          f"\n[{int((session.time_left() - until) // 60)} minutes left for this"
          " step]"
      )


async def solve(session):
  """Runs planner, worker, and the gate-checked fix loop for `session`.

  Args:
    session: Active `taskbridge.Session` for the task.

  Returns:
    The final summary message from the worker.
  """
  total = session.time_left()

  def until(share):
    """Computes the remaining seconds when `share` of total task time is left.

    Args:
      share: Fraction of total task time remaining (`0.0` to `1.0`).

    Returns:
      Remaining seconds threshold, or `0` if the task has no time limit.
    """
    return 0 if total is None else total * share

  def time_for(wrap_up):
    """Checks whether at least `MIN_STEP_SEC` remains before `wrap_up`.

    Args:
      wrap_up: Remaining seconds threshold at which the next step wraps up.

    Returns:
      `True` if there is no deadline or at least `MIN_STEP_SEC` before
      `wrap_up`.
    """
    left = session.time_left()
    return left is None or left - wrap_up >= MIN_STEP_SEC

  task = session.instruction
  await setup_mcp(session)
  extra = MCP_TOOLS if session.mcp_servers else []
  # `phase:` lines mark the state machine's transitions in the log so a
  # recorded run can be replayed step by step (P1-06 structured logs).
  await session.log("phase: plan")
  plan = await agent(
      session,
      conversation(PLANNER, session, task),
      READ_ONLY + extra,
      until(1 - PLAN_SHARE),
  )
  await session.log(safe(f"plan: {plan[:1000]}"))
  await session.log("phase: work")
  work = conversation(WORKER, session, f"{task}\n\n## Plan\n{plan}")
  summary = await agent(
      session, work, TOOLS + extra, until(CHECK_SHARE), final=True
  )
  # P3: the acceptance check is mechanical. It is written once by the gate
  # role and rerun every round; only when no usable check exists does the
  # read-only verifier check by hand for that round.
  check_script = None
  gating = None  # the conversation that wrote check_script
  run_fixed = False  # check_script already had its runtime repair turn
  for round_num in range(1, MAX_FIX_ROUNDS + 1):
    if not time_for(until(CHECK_SHARE / 2)):
      break
    await session.log(f"phase: gate {round_num}")
    # the check roles may not change the deliverables: whatever they write
    # under the workdir is undone before the verdict reaches the fix round
    saved = await guard(session, "save")
    try:
      if check_script is None and time_for(until(CHECK_SHARE / 4)):
        gating = conversation(
            GATE, session, f"## Task\n{task}\n\n## Plan\n{plan}"
        )
        reply = await agent(
            session, gating, READ_ONLY + extra, until(CHECK_SHARE / 2)
        )
        check_script, run_fixed = gate_script(reply), False
        why = "" if check_script else gate_why(reply)
        # one repair turn for a script that does not compile (EXP-028 #1:
        # both gate scripts lost to one unterminated string each)
        if "SyntaxError" in why and time_for(until(CHECK_SHARE / 4)):
          await session.log(safe(f"gate: script does not compile ({why})"))
          gating.append(
              {"role": "user", "content": GATE_REPAIR.format(why=why)}
          )
          reply = await agent(
              session, gating, READ_ONLY + extra, until(CHECK_SHARE / 2)
          )
          check_script = gate_script(reply)
          why = "" if check_script else gate_why(reply)
        await session.log(
            "gate: script ready" if check_script else
            safe(f"gate: no usable script ({why})")
        )
      verdict, crash = (
          await gate_run(session, check_script) if check_script
          else (None, "")
      )
      # one repair turn for a script that runs but gives no verdict
      if (
          crash and gating is not None and not run_fixed
          and time_for(until(CHECK_SHARE / 4))
      ):
        run_fixed = True
        await session.log(safe(
            f"gate: script failed to run; asking for a fix ({crash[:200]})"
        ))
        gating.append(
            {"role": "user", "content": GATE_RUN_REPAIR.format(why=crash)}
        )
        reply = await agent(
            session, gating, READ_ONLY + extra, until(CHECK_SHARE / 2)
        )
        fixed = gate_script(reply)
        await session.log(
            "gate: fixed script ready" if fixed else
            safe(f"gate: no usable fixed script ({gate_why(reply)})")
        )
        if fixed:
          check_script = fixed
          verdict, crash = await gate_run(session, check_script)
      if verdict is None:
        if check_script is not None:
          # a check with no verdict lines, or broken tooling, is not rerun
          check_script = None
        if not time_for(until(CHECK_SHARE / 2)):
          break
        await session.log(f"phase: verify {round_num}")
        review = (
            f"## Task\n{task}\n\n## Plan\n{plan}\n\n## The engineer's"
            f" summary\n{summary}"
        )
        verdict = await agent(
            session,
            conversation(VERIFIER, session, review),
            READ_ONLY + extra,
            until(CHECK_SHARE / 2),
        )
    finally:
      if saved:
        await guard(session, "restore")
    await session.log(safe(f"verdict: {verdict[:1000]}"))
    # PASS alone in any letter case (Markdown emphasis and a full stop aside),
    # or an empty reply, names no gaps
    if verdict.strip("*_. \r\n\t").upper() in ("", "PASS") or not time_for(
        WRAP_UP_SEC
    ):
      break
    await session.log(f"phase: fix {round_num}")
    work.append({
        "role": "user",
        "content": (
            "A reviewer checked your files and found these"
            f" gaps:\n{verdict}\n\nClose every gap by writing or editing"
            " the files with your tools -- rereading alone fixes nothing"
            " -- then reply with your updated summary."
        ),
    })
    summary = (
        await agent(session, work, TOOLS + extra, WRAP_UP_SEC, final=True)
        or summary
    )
  return summary or session.final_message


if __name__ == "__main__":
  taskbridge.run(solve)
