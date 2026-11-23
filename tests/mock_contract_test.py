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
    size = int(len(json.dumps(request.get("messages") or [],
                              ensure_ascii=False)) // 4
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
      "MOCK_CTX_TRUNC", "MOCK_TOKEN_RATIO",
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


async def main():
  # clean: the scripted full loop completes with all phase markers
  ev, _ = await run_case("clean", {"MOCK_CASE": "clean"}, {})
  check(ev, log_in=("phase: plan", "phase: work", "phase: gate 1",
                    "gate: script ready", "verdict: PASS"),
        log_not_in=("reply announces work",),
        final_in=("summary: /app/out.txt",), name="clean")

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
                    "phase: verify 1"),
        log_not_in=("phase: gate 2",), name="gate_exec")

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
