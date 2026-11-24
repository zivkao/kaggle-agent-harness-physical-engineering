"""Contract tests for the plan-work-verify harness (mock model + evaluator).

Run from the harness folder:

  uv run --no-project --python 3.12 --with websockets,openai \
    python tests/mock_contract_test.py

Nineteen scenarios assert the P1 exit conditions (bounded ends under
faults) plus the protocol contract:

  clean         scripted plan/work/gate PASS    -> done, phases logged
  fix_round     scripted check lists a gap once -> fix 1, gate 2, done
  retry_429     six 429s, then health           -> recovered, done
  retry_dead    every call 400 (no retry fit)   -> error frame, bounded
  timeout_wrap  slow model, 6 s task clock      -> done before 12 s
  tool_error    exec exits 1                    -> model sees it, run ends
  context_full  400 "prompt is too long"        -> old results cut, done
  cancel        cancel mid-work                 -> done within 10 s
  socket_close  socket dropped mid-work         -> server survives, rerun
  redaction     key inside an error body        -> key never in any log
  gate_fallback gate emits no usable script     -> reviewer takes the round
  gate_exec     check prints no verdict lines   -> reviewer takes the round
  ctx_budget    tiny $CONTEXT_TOKENS window     -> results cut before call
  ctx_discover  window announced on /v1/models  -> budget arms itself
  ctx_learn     window unknown, size-based 400  -> learned once, then cut
  empty_cut     reply cut with no answer text   -> nudge says so
  out_cap       known window, big output cap    -> reply <= window / 4
  gate_broke    check's own command missing     -> reviewer, no fix round
  gate_missing_file  deliverable path missing   -> still a gap, fix round
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import websockets

SECRET = "SECRETKEY123"  # stands in for $OPENAI_API_KEY in `redaction`


class MockModel(BaseHTTPRequestHandler):
  """OpenAI-compatible /v1/chat/completions scripted per MOCK_CASE."""

  n = 0  # HTTP responses given this scenario (fail injection counts)
  role_calls = {}  # per-role call counters
  flags = {}  # observations asserted after a run

  def role_of(self, messages):
    """Maps a request's system prompt to the harness role running it."""
    system = str((messages or [{}])[0].get("content", ""))
    if system.startswith("You check"):
      return "verifier"
    if system.startswith("You turn"):
      return "gate"
    if system.startswith("You are an expert"):
      return "worker"
    return "planner"

  def reply(self, request):
    """Returns the scripted assistant message for this request."""
    case = os.environ.get("MOCK_CASE", "clean")
    messages = request.get("messages") or []
    role = self.role_of(messages)
    MockModel.role_calls[role] = MockModel.role_calls.get(role, 0) + 1
    call = MockModel.role_calls[role]
    last = str((messages or [{}])[-1].get("content", ""))
    if "A reviewer checked" in last:
      MockModel.flags["saw_gap"] = True  # the fix-round prompt arrived
    if "exit code 1" in json.dumps(messages):
      MockModel.flags["saw_exit1"] = True
    for m in messages:  # old tool calls cut by shorten() stay valid JSON
      for c in m.get("tool_calls") or ():
        arguments = c["function"]["arguments"]
        if "already run]" in arguments:
          MockModel.flags["saw_args_cut"] = True
        try:
          json.loads(arguments)
        except ValueError:
          MockModel.flags["bad_args"] = True
    if request.get("tool_choice") == "none":  # a wrap-up call
      return {"role": "assistant", "content": "wrapped up: partial work"}
    if case == "cancel":
      return self.tool("bash", {"command": "echo spin"})
    if case == "socket_close":
      return self.tool("bash", {"command": "echo spin"})
    if "A reviewer checked" in last:  # each gap list a fix round received
      MockModel.flags.setdefault("gaps", []).append(last)
    if role == "planner":
      if call == 1:
        return self.tool("bash", {"command": "ls"})
      if case == "empty_cut" and call == 2:
        # all reasoning, no answer, cut at the output limit
        return {"role": "assistant", "content": "", "_finish": "length"}
      if case == "unfinished" and call == 2:  # one sentence of intent
        return {"role": "assistant", "content": "I will start by reading."}
      if "still to do instead" in last:
        MockModel.flags["pushes"] = MockModel.flags.get("pushes", 0) + 1
      if "ran past the output limit" in last:
        MockModel.flags["saw_empty_cut"] = True
      if "continue where it stopped" in last:
        MockModel.flags["saw_continue"] = True
      return {"role": "assistant", "content": "PLAN: write /app/out.txt"}
    if role == "worker":
      if case == "call_cut":  # first call cut at the output limit
        if call == 1:
          cut = self.tool(
              "write_file", {"path": "/app/out.txt", "content": "PARTIAL"}
          )
          cut["_finish"] = "length"
          return cut
        if "inside a tool call" in last:
          MockModel.flags["saw_call_cut"] = True
        call -= 1  # then as clean
      if case == "unfinished":  # a summary that lists the work still to do
        if call == 2:
          return {"role": "assistant", "content":
                  "Parsed the inputs.\n\n**Next Steps:**\n* write out.txt"}
        if "still to do instead" in last:
          MockModel.flags["pushes"] = MockModel.flags.get("pushes", 0) + 1
      if "missing, empty or do not open" in last:
        MockModel.flags["saw_missing"] = True
      if case == "ratio_carry":  # a long read first, then as clean
        if call == 1:
          return self.tool("bash", {"command": "cat big_input.txt"})
        call -= 1
      if case == "claimed_done":  # EXP-029 fire-solve: says done, wrote none
        if call == 1:
          return {"role": "assistant",
                  "content": "summary: saved /app/out.txt as asked"}
        call -= 1  # then as clean, once asked for the file
      if case == "args_cut" and call == 1:  # a long file through a call
        return self.tool(
            "write_file", {"path": "/app/out.txt", "content": "x" * 30000}
        )
      if case == "fix_round" and call >= 3:  # the fix round and its answer
        if call == 3:
          return self.tool("bash", {"command": "printf '\\n' >> /app/out.txt"})
        return {"role": "assistant", "content": "summary fixed: out.txt"}
      if call == 1:
        return self.tool(
            "write_file", {"path": "/app/out.txt", "content": "hi\n"}
        )
      return {"role": "assistant", "content": "summary: /app/out.txt written"}
    if role == "gate":
      first = str(messages[1].get("content", "")) if len(messages) > 1 else ""
      if "names (absolute)\n/app/out.txt" in first:
        MockModel.flags["gate_paths"] = True  # the named paths reached it
      if "No module named 'pandas'" in last:  # the runtime repair turn
        MockModel.flags["saw_run_repair"] = True
      if case == "gate_fallback":  # prose instead of a script
        return {"role": "assistant", "content": "I could not write a script"}
      if case == "gate_fence":  # the script itself checks for a fence
        return {
            "role": "assistant",
            "content": "Here is the check.\n```python\n"
                       "fence = '```json'\nprint('PASS fence-ok', len(fence))"
                       "\n```\n",
        }
      if case == "gate_repair" and "does not compile" not in last:
        return {  # an unterminated string, as EXP-028 #1's gate wrote
            "role": "assistant",
            "content": "```python\nimport os\nprint('PASS scripted-ok)\n```",
        }
      return {
          "role": "assistant",
          "content": "```python\nprint('PASS scripted-ok')\n```",
      }
    # verifier
    if call == 1:
      return self.tool("bash", {"command": "cat /app/out.txt"})
    if case == "fix_round" and not MockModel.flags.get("gapped"):
      MockModel.flags["gapped"] = True
      return {"role": "assistant", "content": "1. out.txt needs a newline"}
    return {"role": "assistant", "content": "PASS"}

  def tool(self, name, args):
    """Builds a single tool-call message with a unique id."""
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": f"c{MockModel.n}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(args),
            },
        }],
    }

  def do_GET(self):  # noqa: N802 required by BaseHTTPRequestHandler
    """Serves /v1/models: announces a window only when $MOCK_WINDOW > 0."""
    win = int(os.environ.get("MOCK_WINDOW", "0"))
    if self.path == "/v1/models" and win:
      body = json.dumps({
          "object": "list",
          "data": [{
              "id": "mock-model", "object": "model", "created": 0,
              "owned_by": "mock", "max_model_len": win,
          }],
      }).encode()
      self.send_response(200)
    else:
      body = json.dumps({"error": {"message": "not found"}}).encode()
      self.send_response(404)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def do_POST(self):  # noqa: N802 required by BaseHTTPRequestHandler
    length = int(self.headers.get("Content-Length", "0"))
    request = json.loads(self.rfile.read(length) or b"{}")
    MockModel.n += 1
    # $MOCK_FAIL_FROM/$MOCK_FAIL_TO inject HTTP failures for response
    # numbers in that inclusive range (0 disables).
    if int(os.environ.get("MOCK_FAIL_FROM", "0")) <= MockModel.n <= int(
        os.environ.get("MOCK_FAIL_TO", "0")
    ):
      body = json.dumps({
          "error": {
              "message": os.environ.get("MOCK_FAIL_BODY", "injected failure")
          }
      }).encode()
      self.send_response(int(os.environ.get("MOCK_FAIL_STATUS", "500")))
      self.send_header("Content-Type", "application/json")
      self.send_header("Content-Length", str(len(body)))
      self.end_headers()
      self.wfile.write(body)
      return
    # $MOCK_CTX_LIMIT refuses any prompt over that many chars/4 the way
    # Ollama words it, counting each refusal (0 disables)
    limit = int(os.environ.get("MOCK_CTX_LIMIT", "0"))
    # $MOCK_TOKEN_RATIO: real tokens per chars/4 unit (default 1), which
    # usage.prompt_tokens reports and the window limits below are counted in
    # stored reasoning sent back is not part of the prompt, as with Ollama
    shown = [{k: v for k, v in m.items() if k != "reasoning_content"}
             for m in request.get("messages") or []]
    size = int(len(json.dumps(shown, ensure_ascii=False)) // 4
               * float(os.environ.get("MOCK_TOKEN_RATIO", "1")))
    if limit and size > limit:
      MockModel.flags["overflows"] = MockModel.flags.get("overflows", 0) + 1
      body = json.dumps({"error": {
          "message": "the prompt is longer than the context length"
                     " currently available to the model",
          "type": "invalid_request_error",
      }}).encode()
      self.send_response(400)
      self.send_header("Content-Type", "application/json")
      self.send_header("Content-Length", str(len(body)))
      self.end_headers()
      self.wfile.write(body)
      return
    delay = float(os.environ.get("MOCK_DELAY", "0"))
    if delay:
      time.sleep(delay)
    asked = request.get("max_completion_tokens") or 0
    MockModel.flags["max_out"] = max(MockModel.flags.get("max_out", 0), asked)
    message = self.reply(request)
    # $MOCK_REASONING: characters of reasoning each reply carries
    thought = int(os.environ.get("MOCK_REASONING", "0"))
    if thought:
      message["reasoning_content"] = "r" * thought
    finish = message.pop("_finish", "stop")
    # a reply stopped at its budget used all of it
    made = asked if finish == "length" else 100
    # $MOCK_CTX_TRUNC: past that many tokens (prompt chars/4 + reply budget)
    # the reply stops at the window the way Ollama does: 200, "length",
    # fewer tokens than asked, and the cut-off tool call is lost
    trunc = int(os.environ.get("MOCK_CTX_TRUNC", "0"))
    if trunc and size + asked > trunc:
      MockModel.flags["truncs"] = MockModel.flags.get("truncs", 0) + 1
      message = {"role": "assistant", "content": "Partial answer, cut"}
      finish, made = "length", max(1, trunc - size)
    body = json.dumps({
        "id": f"cm{MockModel.n}",
        "object": "chat.completion",
        "model": "mock",
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish,
        }],
        "usage": {
            "prompt_tokens": size,
            "completion_tokens": made,
            "total_tokens": size + made,
        },
    }).encode()
    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def log_message(self, *args):  # keep the test output clean
    pass


class Evaluator:
  """Speaks the serve protocol: one task, answers tools, catches the end."""

  def __init__(self, case_cfg):
    self.cfg = case_cfg
    self.result = None
    self.logs = []
    self.execs = []
    self.n_execs = 0
    self.n_gate = 0  # mechanical-check runs (own counter, see below)
    self.guards = []  # check-guard commands (save / restore), not counted
    self.named = []  # named-file checks and what each reported missing

  async def handle(self, ws):
    """Runs one full exchange on `ws` and returns the terminal frame."""
    await ws.send(json.dumps({
        "type": "task",
        "protocol": 1,
        "session": "mock",
        "instruction": "Write /app/out.txt containing hi.",
        "workdir": "/app",
        "limits": {
            "agent_timeout_sec": self.cfg.get("agent_timeout_sec", 3600),
            "exec_timeout_sec": 600,
            "max_output_bytes": 100000,
            "max_write_bytes": 10000000,
        },
        "mcp_servers": [],
    }))
    self.cancel_sent = None
    async for raw in ws:
      message = json.loads(raw)
      kind = message.get("type")
      if kind == "log":
        self.logs.append(message.get("text", ""))
        continue
      if kind == "usage":
        continue
      if kind in ("done", "error"):
        self.result = message
        return message
      if kind == "exec":
        cmd = message.get("command", "")
        self.execs.append(cmd)
        if "ple_guard.py" in cmd:
          # the check guard runs outside the fault-injection counters; a
          # restore reports what $guard_out says the check had changed
          self.guards.append(cmd.split()[3])
          restore = cmd.split()[3] == "restore"
          await ws.send(json.dumps({
              "type": "result",
              "id": message["id"],
              "exit_code": 0,
              "output": self.cfg.get("guard_out", "") if restore else "",
              "truncated": False,
              "timed_out": False,
          }))
          continue
        if "ple_deliverables" in cmd:
          # the named-file check runs outside the fault-injection counters;
          # $missing_outs scripts which paths it reports missing per call
          outs = self.cfg.get("missing_outs") or [""]
          out = outs[min(len(self.named), len(outs) - 1)]
          self.named.append(out)
          await ws.send(json.dumps({
              "type": "result",
              "id": message["id"],
              "exit_code": 0,
              "output": out,
              "truncated": False,
              "timed_out": False,
          }))
          continue
        if "ple_gate.py" in cmd:
          # the mechanical check runs on its own counter, scripted from
          # gate_outs, so gate reruns never shift the fault injections
          if self.cfg.get("gate_fail_exec"):
            out = "Traceback (most recent call last):\n  crash (injected)"
          else:
            outs = self.cfg.get("gate_outs") or ["PASS scripted-ok"]
            out = outs[min(self.n_gate, len(outs) - 1)]
          self.n_gate += 1
          await ws.send(json.dumps({
              "type": "result",
              "id": message["id"],
              "exit_code": 1 if self.cfg.get("gate_fail_exec") else 0,
              "output": out,
              "truncated": False,
              "timed_out": False,
          }))
          continue
        self.n_execs += 1
        big = self.cfg.get("exec_output_chars", 4)
        await ws.send(json.dumps({
            "type": "result",
            "id": message["id"],
            "exit_code": 1 if self.cfg.get(
                "fail_first_exec"
            ) and self.n_execs == 1 else 0,
            "output": ("x" * big) if big != 4 else "mock",
            "truncated": False,
            "timed_out": False,
        }))
        at = self.cfg.get("cancel_after_execs")
        if at and self.n_execs == at:
          await ws.send(json.dumps({"type": "cancel"}))
          self.cancel_sent = time.monotonic()
        at = self.cfg.get("close_after_execs")
        if at and self.n_execs == at:
          return None  # caller closes the socket
      if kind == "write_file":
        await ws.send(json.dumps({
            "type": "result",
            "id": message["id"],
            "ok": True,
            "size": len(base64.b64decode(message.get("content_b64", ""))),
        }))
      if kind == "read_file":
        data = b"hi\n"
        await ws.send(json.dumps({
            "type": "result",
            "id": message["id"],
            "ok": True,
            "content_b64": base64.b64encode(data).decode(),
            "size": len(data),
        }))
    return None


def free_port():
  import socket

  with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    return s.getsockname()[1]


async def connect(port):
  """Opens the harness socket, waiting up to 60 s for it to boot."""
  for _ in range(60):
    try:
      return await websockets.connect(f"ws://127.0.0.1:{port}")
    except OSError:
      await asyncio.sleep(1)
  raise AssertionError("harness never accepted the socket")


async def run_case(name, env_add, cfg, api_key="mock-test-key"):
  """Boots serve.py against a fresh mock model and returns the evaluator."""
  MockModel.n = 0
  MockModel.role_calls = {}
  MockModel.flags = {}
  m_port, s_port = free_port(), free_port()
  for key in (
      "MOCK_CASE", "MOCK_FAIL_FROM", "MOCK_FAIL_TO", "MOCK_FAIL_STATUS",
      "MOCK_FAIL_BODY", "MOCK_DELAY", "MOCK_WINDOW", "MOCK_CTX_LIMIT",
      "MOCK_CTX_TRUNC", "MOCK_TOKEN_RATIO", "MOCK_REASONING",
  ):
    if key in env_add:
      os.environ[key] = str(env_add[key])
    else:
      os.environ.pop(key, None)
  server = ThreadingHTTPServer(("127.0.0.1", m_port), MockModel)
  threading.Thread(target=server.serve_forever, daemon=True).start()
  env = dict(
      os.environ,
      MODEL_NAME="mock-model",
      OPENAI_BASE_URL=f"http://127.0.0.1:{m_port}/v1",
      OPENAI_API_KEY=api_key,
      PORT=str(s_port),
      RETRY_WAITS="1,1,1,1,1",
      **{k: str(v) for k, v in env_add.items()},
  )
  env.pop("REASONING_EFFORT", None)
  proc = subprocess.Popen(
      [sys.executable, "serve.py"], env=env, cwd=os.getcwd()
  )
  try:
    return await _drive(name, cfg, s_port), proc
  finally:
    proc.terminate()
    server.shutdown()


async def _drive(name, cfg, s_port):
  evaluator = Evaluator(cfg)
  ws = await connect(s_port)
  started = time.monotonic()
  async with ws:
    await evaluator.handle(ws)
  evaluator.secs = time.monotonic() - started
  if cfg.get("close_after_execs"):
    # the socket was dropped mid-work: the server must still accept a task
    # (the mock model lives in THIS process, so switch its script back)
    os.environ["MOCK_CASE"] = "clean"
    evaluator2 = Evaluator({"case": "rerun"})
    async with await connect(s_port) as ws2:
      end2 = await evaluator2.handle(ws2)
    assert end2 and end2["type"] == "done", f"{name}: rerun got {end2}"
  return evaluator


def check(ev, *, name, result_type="done", final_in=(), log_in=(),
          log_not_in=(), max_secs=None, cancel_max=None):
  """Asserts the recorded run against one scenario's contract."""
  assert ev.result is not None, f"{name}: no done/error frame"
  assert ev.result["type"] == result_type, f"{name}: got {ev.result}"
  final = ev.result.get("final_message") or ev.result.get("message", "")
  joined = "\n".join(ev.logs)
  for needle in final_in:
    assert needle in final, f"{name}: final lacks {needle!r}: {final[:200]}"
  for needle in log_in:
    assert needle in joined, f"{name}: log lacks {needle!r}: {joined[:400]}"
  for needle in log_not_in:
    assert needle not in joined, f"{name}: log contains {needle!r}"
  if max_secs is not None:
    assert ev.secs < max_secs, f"{name}: {ev.secs:.0f}s > {max_secs}s"
  if cancel_max is not None:
    left = (time.monotonic() - ev.cancel_sent)  # measured at done receipt
    assert left < cancel_max, f"{name}: done {left:.1f}s after cancel"
  print(f"[PASS] {name}: {ev.result['type']} secs={ev.secs:.1f}")


def guard_unit():
  """Runs serve.py's GUARD script for real on a scratch tree.

  The check writes a new file and a new folder, rewrites one deliverable
  and deletes another; the restore must leave the tree exactly as it was
  saved (contents and mtimes), and use its snapshot once. With a 0 MB cap
  nothing is kept, so a rewritten file is reported, not restored.
  """
  import ast
  import shutil
  import subprocess
  import tempfile

  here = os.path.dirname(os.path.abspath(__file__))
  tree = ast.parse(open(os.path.join(here, "..", "serve.py")).read())
  guard = next(
      ast.literal_eval(n.value) for n in tree.body
      if isinstance(n, ast.Assign)
      and getattr(n.targets[0], "id", "") == "GUARD"
  )
  tmp = tempfile.mkdtemp()
  try:
    script, snap = os.path.join(tmp, "g.py"), os.path.join(tmp, "snap")
    root = os.path.join(tmp, "work")
    os.makedirs(os.path.join(root, "output"))
    os.makedirs(os.path.join(root, "project"))
    for rel, data in (("output/submission.zip", b"PK-original"),
                      ("output/notes.md", b"notes"),
                      ("project/input.csv", b"a,b\n1,2\n")):
      with open(os.path.join(root, rel), "wb") as f:
        f.write(data)
    open(script, "w").write(guard)
    env = dict(os.environ, PLE_GUARD_SNAP=snap)

    def state():
      out = {}
      for d, _, names in os.walk(root):
        for name in names:
          p = os.path.join(d, name)
          out[os.path.relpath(p, root)] = (
              open(p, "rb").read(), os.stat(p).st_mtime_ns)
      dirs = sorted(os.path.relpath(d, root) for d, _, _ in os.walk(root))
      return out, dirs

    def run(mode, one="50", total="1000"):
      return subprocess.run(
          [sys.executable, script, root, mode, one, total], env=env,
          capture_output=True, text=True, check=True).stdout

    def meddle():
      time.sleep(0.01)
      with open(os.path.join(root, "output/submission.zip"), "ab") as f:
        f.write(b"+duplicates")
      os.remove(os.path.join(root, "output/notes.md"))
      with open(os.path.join(root, "acceptance_check.py"), "w") as f:
        f.write("print('PASS')")
      os.makedirs(os.path.join(root, "scratch/deep"))
      with open(os.path.join(root, "scratch/deep/x.txt"), "w") as f:
        f.write("x")

    before = state()
    assert run("save") == "", "guard: save printed output"
    assert run("restore") == "", "guard: an untouched tree reported changes"
    assert run("save") == ""
    meddle()
    out = run("restore")
    assert "removed 2 new file(s), restored 2 changed or deleted" in out, out
    after = state()
    off = sorted(k for k in set(before[0]) | set(after[0])
                 if before[0].get(k) != after[0].get(k))
    assert after == before, f"guard: differs at {off}, dirs {after[1]}"
    assert not os.path.exists(snap + ".json"), "guard: snapshot kept"
    assert run("restore") == "", "guard: a used snapshot was reused"
    run("save", one="0", total="0")
    meddle()
    out = run("restore", one="0", total="0")
    assert "could not restore 2 (too big)" in out, out
    assert not os.path.exists(os.path.join(root, "acceptance_check.py"))
    print("[PASS] guard_unit: restore matches the saved tree")
  finally:
    shutil.rmtree(tmp)


def files_unit():
  """Runs serve.py's FILES_CHECK script for real on scratch deliverables.

  Covers the EXP-029/030 fire-solve cases (no file; text saved as .docx; a
  hand-built package with a broken [Content_Types].xml) next to good files,
  which must print nothing. The broken package is only caught by opening it
  with python-docx, so that case runs where python-docx imports.
  """
  import ast
  import importlib.util
  import shutil
  import subprocess
  import tempfile
  import zipfile

  here = os.path.dirname(os.path.abspath(__file__))
  tree = ast.parse(open(os.path.join(here, "..", "serve.py")).read())
  check = next(
      ast.literal_eval(n.value) for n in tree.body
      if isinstance(n, ast.Assign)
      and getattr(n.targets[0], "id", "") == "FILES_CHECK"
  )
  has_docx = importlib.util.find_spec("docx") is not None
  tmp = tempfile.mkdtemp()
  try:
    p = lambda name: os.path.join(tmp, name)  # noqa: E731
    open(p("empty.pdf"), "wb").close()
    open(p("text.docx"), "w").write("Disposition, plain text")
    open(p("fake.pdf"), "w").write("not a pdf")
    open(p("good.pdf"), "wb").write(b"%PDF-1.7\n%%EOF\n")
    with zipfile.ZipFile(p("good.zip"), "w") as z:
      z.writestr("a.csv", "x,y\n")
    with zipfile.ZipFile(p("noparts.docx"), "w") as z:
      z.writestr("readme.txt", "hi")
    with zipfile.ZipFile(p("broken.docx"), "w") as z:  # as EXP-030 #1 built
      z.writestr("[Content_Types].xml",
                 '<?xml version="1.0"?><Types xmlns="http://schemas.'
                 'openxmlformats.org/package/2006/content-types"><Override'
                 ' PartName="/word/document.xml" DataType="x"/></Types>')
      z.writestr("_rels/.rels", "<Relationships/>")
      z.writestr("word/document.xml", "<w:document/>")
    names = ["none.docx", "empty.pdf", "text.docx", "fake.pdf", "good.pdf",
             "good.zip", "noparts.docx", "broken.docx"]
    if has_docx:
      import docx
      d = docx.Document()
      d.add_paragraph("ok")
      d.save(p("good.docx"))
      names.append("good.docx")
    script = p("check.py")
    open(script, "w").write(check)
    out = subprocess.run(
        [sys.executable, script] + [p(n) for n in names],
        capture_output=True, text=True, check=True).stdout
    got = dict(line.split("\t", 1) for line in out.splitlines())
    got = {os.path.basename(k): v for k, v in got.items()}
    want = {"none.docx": "does not exist", "empty.pdf": "is empty",
            "text.docx": "not a zip archive", "fake.pdf": "no %PDF header",
            "noparts.docx": "no word/document.xml"}
    if has_docx:
      want["broken.docx"] = "does not open as .docx"
    for name, needle in want.items():
      assert needle in got.get(name, ""), f"files: {name} -> {got.get(name)!r}"
    extra = set(got) - set(want) - ({"broken.docx"} if not has_docx else set())
    assert not extra, f"files: good files flagged {sorted(extra)}: {got}"
    print(f"[PASS] files_unit: {len(want)} faults found, good files pass"
          f"{'' if has_docx else ' (no python-docx: broken.docx not opened)'}")
  finally:
    shutil.rmtree(tmp)


async def main():
  guard_unit()
  files_unit()

  # clean: the scripted full loop completes with all phase markers
  ev, _ = await run_case("clean", {"MOCK_CASE": "clean"}, {})
  assert ev.guards == ["save", "restore"], f"clean: guard calls {ev.guards}"
  assert ev.named == ["", ""], f"clean: named-file checks {ev.named}"
  assert MockModel.flags.get("gate_paths"), "clean: gate not given the paths"
  check(ev, log_in=("phase: plan", "phase: work", "phase: gate 1",
                    "gate: script ready", "verdict: PASS",
                    "deliverables: 1 of 1 named file(s) in order"),
        log_not_in=("reply announces work", "asking the worker to write"),
        final_in=("summary: /app/out.txt",), name="clean")

  # claimed_done: the worker says it saved the named file without a tool
  # call (EXP-029 fire-solve-convergence); the harness finds it missing and
  # sends the worker back once, before the gate
  ev, _ = await run_case(
      "claimed_done", {"MOCK_CASE": "claimed_done"},
      {"missing_outs": ["/app/out.txt\tdoes not exist\n", ""]},
  )
  assert MockModel.flags.get("saw_missing"), "claimed_done: no push"
  assert len(ev.named) == 2, f"claimed_done: checks {ev.named}"
  check(ev, log_in=("deliverables: 0 of 1 named file(s) in order; at fault:"
                    "\n- /app/out.txt does not exist",
                    "deliverables: asking the worker", "verdict: PASS"),
        log_not_in=("FAIL DELIVERABLE",),
        final_in=("summary: /app/out.txt written",), name="claimed_done")

  # deliverable_gate: the gate's script passes but the named file is gone;
  # the round fails on it and the fix round runs, then the rerun passes
  ev, _ = await run_case(
      "deliverable_gate", {"MOCK_CASE": "clean"},
      {"missing_outs": ["", "/app/out.txt\tdoes not open as .txt (x)\n", ""]},
  )
  assert MockModel.flags.get("saw_gap"), "deliverable_gate: no fix round"
  check(ev, log_in=("verdict: FAIL DELIVERABLE: /app/out.txt does not open",
                    "phase: fix 1", "phase: gate 2", "verdict: PASS"),
        log_not_in=("asking the worker to write",),
        name="deliverable_gate")

  # fix_round: the scripted mechanical check lists a gap once and the
  # worker is sent back to write; the rerun of the same check passes
  ev, _ = await run_case(
      "fix_round",
      {"MOCK_CASE": "fix_round"},
      {"gate_outs": ["FAIL g1: out.txt needs a trailing newline",
                     "PASS scripted-ok"]},
  )
  assert MockModel.flags.get("saw_gap"), "fix_round: worker never got the gap"
  check(ev, log_in=("phase: gate 1", "phase: fix 1", "phase: gate 2"),
        log_not_in=("phase: verify",), final_in=("summary fixed",),
        name="fix_round")

  # gate_fallback: the gate answers prose; the read-only reviewer takes
  # the round instead and passes
  ev, _ = await run_case("gate_fallback", {"MOCK_CASE": "gate_fallback"}, {})
  check(ev, log_in=("gate: no usable script (no code block, whole reply:"
                    " SyntaxError", "phase: verify 1"),
        final_in=("summary: /app/out.txt",), name="gate_fallback")

  # gate_exec: the check runs but prints no verdict lines; the reviewer
  # takes the round and the broken check is not rerun
  ev, _ = await run_case("gate_exec", {"MOCK_CASE": "clean"},
                         {"gate_fail_exec": True})
  check(ev, log_in=("phase: gate 1", "gate: no verdict lines",
                    "gate: script failed to run; asking for a fix",
                    "phase: verify 1"),
        log_not_in=("phase: gate 2",), name="gate_exec")

  # gate_crash: the script stops at a module the container lacks (EXP-028
  # #3/#4: pandas); its traceback goes back to the gate once, the fixed
  # script runs and its verdict stands, so no reviewer is needed
  ev, _ = await run_case(
      "gate_crash", {"MOCK_CASE": "clean"},
      {"gate_outs": ["Traceback (most recent call last):\n  File"
                     " \"/tmp/ple_gate.py\", line 4, in <module>\n"
                     "ModuleNotFoundError: No module named 'pandas'",
                     "PASS scripted-ok"]},
  )
  assert MockModel.flags.get("saw_run_repair"), "gate_crash: no traceback"
  check(ev, log_in=("gate: script failed to run; asking for a fix",
                    "gate: fixed script ready", "verdict: PASS"),
        log_not_in=("phase: verify 1",), name="gate_crash")

  # retry_429: six 429s exhaust the SDK, recover() retries once more
  ev, _ = await run_case(
      "retry_429",
      {"MOCK_CASE": "clean", "MOCK_FAIL_FROM": 1, "MOCK_FAIL_TO": 6,
       "MOCK_FAIL_STATUS": 429, "MOCK_FAIL_BODY": "rate cap reached"},
      {},
  )
  check(ev, log_in=("again in 1 s", "model call failed"), name="retry_429")

  # retry_dead: 400s fit no retry rule; the run ends with an error frame
  ev, _ = await run_case(
      "retry_dead",
      {"MOCK_CASE": "clean", "MOCK_FAIL_FROM": 1, "MOCK_FAIL_TO": 999,
       "MOCK_FAIL_STATUS": 400, "MOCK_FAIL_BODY": "upstream exploded"},
      {},
  )
  check(ev, result_type="error", final_in=("BadRequestError",), max_secs=40,
        name="retry_dead")

  # timeout_wrap: a slow model on a 6 s clock still ends bounded
  ev, _ = await run_case(
      "timeout_wrap", {"MOCK_CASE": "clean", "MOCK_DELAY": "4"},
      {"agent_timeout_sec": 6},
  )
  check(ev, max_secs=12, name="timeout_wrap")

  # tool_error: a failed exec reaches the model, the run continues
  ev, _ = await run_case("tool_error", {"MOCK_CASE": "clean"},
                         {"fail_first_exec": True})
  assert MockModel.flags.get("saw_exit1"), "tool_error: model never saw it"
  check(ev, name="tool_error")

  # context_full: a 400 overflow cuts old tool results and retries
  ev, _ = await run_case(
      "context_full",
      {"MOCK_CASE": "clean", "MOCK_FAIL_FROM": 2, "MOCK_FAIL_TO": 2,
       "MOCK_FAIL_STATUS": 400, "MOCK_FAIL_BODY": "prompt is too long"},
      {"exec_output_chars": 30000},
  )
  check(ev, log_in=("context full: cut",), name="context_full")

  # ctx_budget: with a tiny declared window, long old tool results are
  # cut BEFORE the call and no 400 is ever answered
  ev, _ = await run_case(
      "ctx_budget",
      {"MOCK_CASE": "clean", "CONTEXT_TOKENS": "1500",
       "CTX_MARGIN_TOKENS": "100", "MAX_OUTPUT_TOKENS": "1000"},
      {"exec_output_chars": 30000},
  )
  check(ev, log_in=("context budget: cut",),
        log_not_in=("context full: cut",), name="ctx_budget")

  # ctx_discover: no $CONTEXT_TOKENS anywhere; the endpoint announces a
  # tiny window on /v1/models, so the proactive budget arms itself and
  # cuts long old tool results before the call (GET never consumes a
  # $MOCK_FAIL slot; the 404 default keeps the other cases unchanged)
  ev, _ = await run_case(
      "ctx_discover",
      {"MOCK_CASE": "clean", "MOCK_WINDOW": "1500",
       "MAX_OUTPUT_TOKENS": "1000"},
      {"exec_output_chars": 30000},
  )
  check(ev, log_in=("context window: 1500 tokens", "context budget: cut"),
        log_not_in=("context full: cut",), name="ctx_discover")

  # ctx_learn: no window anywhere (neither $CONTEXT_TOKENS nor /v1/models);
  # the endpoint refuses oversized prompts with Ollama's 400. Two steps
  # (planner, then the fallback reviewer) each read a long tool result:
  # the first refusal teaches the window, so the second step is cut before
  # its call and the endpoint refuses exactly once
  ev, _ = await run_case(
      "ctx_learn",
      {"MOCK_CASE": "gate_fallback", "MOCK_CTX_LIMIT": "3000",
       "CTX_MARGIN_TOKENS": "100", "MAX_OUTPUT_TOKENS": "1000"},
      {"exec_output_chars": 30000},
  )
  overflows = MockModel.flags.get("overflows", 0)
  assert overflows == 1, f"ctx_learn: endpoint refused {overflows} times"
  check(ev, log_in=("context window: learned", "context full: cut",
                    "context budget: cut", "phase: verify 1"),
        name="ctx_learn")

  # ctx_trunc: no window anywhere, and the endpoint never refuses: past its
  # window it stops the reply short (200, "length", fewer tokens than
  # asked), as Ollama does. That one cut reply teaches the window, so the
  # later calls ask for a reply that fits and are never stopped again
  ev, _ = await run_case(
      "ctx_trunc",
      {"MOCK_CASE": "gate_fallback", "MOCK_CTX_TRUNC": "4000",
       "CTX_MARGIN_TOKENS": "100", "MAX_OUTPUT_TOKENS": "3000"},
      {"exec_output_chars": 8000},
  )
  truncs = MockModel.flags.get("truncs", 0)
  assert truncs == 1, f"ctx_trunc: {truncs} replies stopped at the window"
  check(ev, log_in=("from a reply cut at the window", "phase: verify 1"),
        name="ctx_trunc")

  # ctx_ratio: as ctx_trunc, but the endpoint's tokens run 1.5x chars/4 (a
  # code-heavy transcript). The window learned from the cut reply and the
  # budget both count the endpoint's tokens (usage), so the next calls fit
  # and the endpoint never stops a reply again
  ev, _ = await run_case(
      "ctx_ratio",
      {"MOCK_CASE": "gate_fallback", "MOCK_CTX_TRUNC": "4000",
       "MOCK_TOKEN_RATIO": "1.5", "CTX_MARGIN_TOKENS": "100",
       "MAX_OUTPUT_TOKENS": "3000"},
      {"exec_output_chars": 8000},
  )
  truncs = MockModel.flags.get("truncs", 0)
  assert truncs == 1, f"ctx_ratio: {truncs} replies stopped at the window"
  check(ev, log_in=("from a reply cut at the window", "phase: verify 1"),
        name="ctx_ratio")

  # empty_cut: a reply cut at the output limit with no answer text (all
  # reasoning) gets a nudge that says so, not "continue where it stopped"
  ev, _ = await run_case("empty_cut", {"MOCK_CASE": "empty_cut"}, {})
  assert MockModel.flags.get("saw_empty_cut"), "empty_cut: nudge not sent"
  assert not MockModel.flags.get("saw_continue"), "empty_cut: old nudge sent"
  check(ev, log_in=("reply cut off before any answer",),
        final_in=("summary: /app/out.txt",), name="empty_cut")

  # answer_room: a long tool result leaves the planner's next reply a
  # little over CTX_MIN_ANSWER; that reply runs out while reasoning, so the
  # following call cuts old results until a quarter of the window is free
  # (EXP-031: nine empty replies at 2.7-3.6K tokens of room in 64K)
  ev, _ = await run_case(
      "answer_room",
      {"MOCK_CASE": "empty_cut", "CONTEXT_TOKENS": "6800",
       "CTX_MARGIN_TOKENS": "100", "MAX_OUTPUT_TOKENS": "4000"},
      {"exec_output_chars": 30000},
  )
  check(ev, log_in=("reply cut off before any answer",
                    "tokens left for the reply, under 1700",
                    "context budget: cut"),
        final_in=("summary: /app/out.txt",), name="answer_room")

  # ratio_carry: every reply carries 16,000 characters of reasoning that the
  # endpoint does not read back. Sized by what is sent, and each
  # conversation by its own last real prompt, the work conversation still
  # fits at fix 1 after the gate's fresh one (EXP-032: counted, it looked
  # ~3.7x its real size there and fix 1 cut 9 results)
  ev, _ = await run_case(
      "ratio_carry",
      {"MOCK_CASE": "ratio_carry", "CONTEXT_TOKENS": "14000",
       "CTX_MARGIN_TOKENS": "100", "MAX_OUTPUT_TOKENS": "4000",
       "MOCK_REASONING": "16000"},
      {"exec_output_chars": 30000,
       "gate_outs": ["FAIL g1: out.txt needs a newline", "PASS scripted-ok"]},
  )
  check(ev, log_in=("phase: fix 1", "phase: gate 2", "verdict: PASS"),
        log_not_in=("context budget", "context full"), name="ratio_carry")

  # call_cut: a reply cut at the output limit inside a tool call is not
  # run (its arguments are cut); the model is asked for smaller calls
  ev, _ = await run_case("call_cut", {"MOCK_CASE": "call_cut"}, {})
  assert MockModel.flags.get("saw_call_cut"), "call_cut: nudge not sent"
  check(ev, log_in=("reply cut off inside a tool call",),
        log_not_in=("PARTIAL",), final_in=("summary: /app/out.txt",),
        name="call_cut")

  # args_cut: a long file written through a tool call fills the window as
  # a long result does; the budget cuts the old call's arguments, which
  # stay valid JSON
  ev, _ = await run_case(
      "args_cut",
      {"MOCK_CASE": "args_cut", "CONTEXT_TOKENS": "4000",
       "CTX_MARGIN_TOKENS": "100", "MAX_OUTPUT_TOKENS": "1000"},
      {},
  )
  assert MockModel.flags.get("saw_args_cut"), "args_cut: arguments not cut"
  assert not MockModel.flags.get("bad_args"), "args_cut: invalid arguments"
  check(ev, log_in=("context budget: cut",), name="args_cut")

  # gate_repair: a gate script that does not compile gets one repair turn
  # naming the error and its line; the corrected script then runs
  ev, _ = await run_case("gate_repair", {"MOCK_CASE": "gate_repair"}, {})
  check(ev, log_in=("gate: script does not compile (code block: SyntaxError",
                    "at line 2: \"print('PASS scripted-ok)\"",
                    "gate: script ready", "verdict: PASS"),
        name="gate_repair")

  # check_guard: every check round (gate, its script, the reviewer) runs
  # between a save and a restore of the workdir, and what the restore
  # undid reaches the log before the fix round
  ev, _ = await run_case(
      "check_guard", {"MOCK_CASE": "fix_round"},
      {"gate_outs": ["FAIL g1: out.txt needs a trailing newline",
                     "PASS g1"],
       "guard_out": "undid the check's writes under /app: removed 1 new"
                    " file(s), restored 1 changed or deleted"},
  )
  assert ev.guards == ["save", "restore"] * 2, f"check_guard: {ev.guards}"
  check(ev, log_in=("check guard: undid the check's writes under /app",
                    "phase: fix 1"), name="check_guard")

  # gate_fence: a gate script holding "```" inside a string is taken whole
  # (the closing fence is a line of its own), compiles and runs
  ev, _ = await run_case("gate_fence", {"MOCK_CASE": "gate_fence"}, {})
  check(ev, log_in=("gate: script ready", "verdict: PASS"),
        log_not_in=("does not compile",), name="gate_fence")

  # unfinished: a planner reply of one sentence of intent and a worker
  # summary listing "Next steps" are each sent back once to do the work;
  # the clean run's plan and summary are never sent back
  ev, _ = await run_case("unfinished", {"MOCK_CASE": "unfinished"}, {})
  pushes = MockModel.flags.get("pushes", 0)
  assert pushes == 2, f"unfinished: {pushes} replies sent back, want 2"
  check(ev, log_in=("reply announces work still to do",),
        final_in=("summary: /app/out.txt",), name="unfinished")

  # out_cap: with a known window, no call asks for more than a quarter of
  # it, even when $MAX_OUTPUT_TOKENS allows far more
  ev, _ = await run_case(
      "out_cap",
      {"MOCK_CASE": "clean", "CONTEXT_TOKENS": "8000",
       "CTX_MARGIN_TOKENS": "100", "MAX_OUTPUT_TOKENS": "32000"},
      {},
  )
  asked = MockModel.flags.get("max_out", 0)
  assert 0 < asked <= 2000, f"out_cap: a call asked for {asked} tokens"
  check(ev, name="out_cap")

  # gate_broke: the check's own tooling is missing (a bare command), so it
  # is a broken check, not a gap: the reviewer takes the round, no fix round
  ev, _ = await run_case(
      "gate_broke",
      {"MOCK_CASE": "clean"},
      {"gate_outs": ["FAIL F2: Could not read memo content: [Errno 2] No"
                     " such file or directory: 'strings'"]},
  )
  check(ev, log_in=("gate: check itself failed", "phase: verify 1"),
        log_not_in=("phase: fix 1", "phase: gate 2"), name="gate_broke")

  # gate_missing_file: a missing deliverable named by a path is still a
  # gap and drives a fix round
  ev, _ = await run_case(
      "gate_missing_file",
      {"MOCK_CASE": "fix_round"},
      {"gate_outs": ["FAIL g1: [Errno 2] No such file or directory:"
                     " '/app/out.txt'", "PASS scripted-ok"]},
  )
  check(ev, log_in=("phase: fix 1", "phase: gate 2"),
        log_not_in=("gate: check itself failed",), name="gate_missing_file")

  # repeat_fail: a FAIL the fix round left word for word unchanged is not
  # sent again (EXP-037: both fix rounds went to one false FAIL)
  ev, _ = await run_case(
      "repeat_fail", {"MOCK_CASE": "clean"},
      {"gate_outs": ["FAIL Q6: steady solution not stated",
                     "FAIL Q6: steady solution not stated"]},
  )
  check(ev, log_in=("phase: fix 1", "phase: gate 2",
                    "1 line(s) unchanged since the last fix round, not sent"
                    " again; 0 left"),
        log_not_in=("phase: fix 2",), name="repeat_fail")

  # repeat_part: only the new gap goes to the second fix round
  ev, _ = await run_case(
      "repeat_part", {"MOCK_CASE": "clean"},
      {"gate_outs": ["FAIL g1: a", "FAIL g1: a\nFAIL g2: b"]},
  )
  gaps = MockModel.flags.get("gaps", [])
  assert len(gaps) == 2 and "FAIL g2: b" in gaps[1] and (
      "FAIL g1: a" not in gaps[1]), f"repeat_part: gap lists {gaps}"
  check(ev, log_in=("not sent again; 1 left", "phase: fix 2"),
        name="repeat_part")

  # repeat_deliverable: a named file still missing after a fix round is
  # sent again
  ev, _ = await run_case(
      "repeat_deliverable", {"MOCK_CASE": "clean"},
      {"missing_outs": ["", "/app/out.txt\tdoes not exist\n",
                        "/app/out.txt\tdoes not exist\n"]},
  )
  check(ev, log_in=("phase: fix 1", "phase: fix 2"),
        log_not_in=("not sent again",), name="repeat_deliverable")

  # cancel: done must arrive within the evaluator's 10 s window
  ev, _ = await run_case("cancel", {"MOCK_CASE": "cancel"},
                         {"cancel_after_execs": 2})
  check(ev, final_in=("(stopped: time is up)",), cancel_max=10, name="cancel")

  # socket_close: a dropped socket ends the task but not the server
  ev, _ = await run_case("socket_close", {"MOCK_CASE": "socket_close"},
                         {"close_after_execs": 2})
  print("[PASS] socket_close: server accepted the rerun")

  # redaction: a key echoed in an error body must never reach a log frame
  ev, _ = await run_case(
      "redaction",
      {"MOCK_CASE": "clean", "MOCK_FAIL_FROM": 1, "MOCK_FAIL_TO": 6,
       "MOCK_FAIL_STATUS": 429,
       "MOCK_FAIL_BODY": f"quota for {SECRET} exceeded"},
      {},
      api_key=SECRET,
  )
  check(ev, log_in=("<api-key>",), log_not_in=(SECRET,), name="redaction")

  print("all contract cases passed")


if __name__ == "__main__":
  asyncio.run(main())
