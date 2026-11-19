"""Contract tests for the plan-work-verify harness (mock model + evaluator).

Run from the harness folder:

  uv run --no-project --python 3.12 --with websockets,openai \
    python tests/mock_contract_test.py

Ten scenarios assert the P1 exit conditions (bounded ends under faults)
plus the protocol contract:

  clean         scripted plan/work/verify PASS  -> done, phases logged
  fix_round     verifier lists gaps once        -> fix 1, verify 2, done
  retry_429     six 429s, then health           -> recovered, done
  retry_dead    every call 400 (no retry fit)   -> error frame, bounded
  timeout_wrap  slow model, 6 s task clock      -> done before 12 s
  tool_error    exec exits 1                    -> model sees it, run ends
  context_full  400 "prompt is too long"        -> old results cut, done
  cancel        cancel mid-work                 -> done within 10 s
  socket_close  socket dropped mid-work         -> server survives, rerun
  redaction     key inside an error body        -> key never in any log
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
    if request.get("tool_choice") == "none":  # a wrap-up call
      return {"role": "assistant", "content": "wrapped up: partial work"}
    if case == "cancel":
      return self.tool("bash", {"command": "echo spin"})
    if case == "socket_close":
      return self.tool("bash", {"command": "echo spin"})
    if role == "planner":
      if call == 1:
        return self.tool("bash", {"command": "ls"})
      return {"role": "assistant", "content": "PLAN: write /app/out.txt"}
    if role == "worker":
      if case == "fix_round" and call >= 3:  # the fix round and its answer
        if call == 3:
          return self.tool("bash", {"command": "printf '\\n' >> /app/out.txt"})
        return {"role": "assistant", "content": "summary fixed: out.txt"}
      if call == 1:
        return self.tool(
            "write_file", {"path": "/app/out.txt", "content": "hi\n"}
        )
      return {"role": "assistant", "content": "summary: /app/out.txt written"}
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
    delay = float(os.environ.get("MOCK_DELAY", "0"))
    if delay:
      time.sleep(delay)
    body = json.dumps({
        "id": f"cm{MockModel.n}",
        "object": "chat.completion",
        "model": "mock",
        "choices": [{
            "index": 0,
            "message": self.reply(request),
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 500,
            "completion_tokens": 100,
            "total_tokens": 600,
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
        self.execs.append(message.get("command", ""))
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
      "MOCK_FAIL_BODY", "MOCK_DELAY",
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
  check(ev, log_in=("phase: plan", "phase: work", "phase: verify 1"),
        final_in=("summary: /app/out.txt",), name="clean")

  # fix_round: a gapped verdict sends the worker back once
  ev, _ = await run_case("fix_round", {"MOCK_CASE": "fix_round"}, {})
  assert MockModel.flags.get("saw_gap"), "fix_round: worker never got the gap"
  check(ev, log_in=("phase: verify 1", "phase: fix 1", "phase: verify 2"),
        final_in=("summary fixed",), name="fix_round")

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
