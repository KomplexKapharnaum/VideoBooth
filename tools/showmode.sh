#!/usr/bin/env bash
# showmode.sh on|off|status — stop the other GPU tenants of kxkm-ai for a show, restore after.
#
# "on"  stops what is RUNNING among the known tenants and records exactly that list;
# "off" restarts only what "on" stopped. Nothing else on the machine is touched.
# Tenants (as found 2026-09-04): ComfyUI2 (manual python + filebrowser, from
# /ai/ComfyUI2/run.sh), the hub whisper worker (docker gpu-worker-worker-1), VoiceClone
# (tmux "voiceclone", :7865), gpu-swap LLM launcher (uvicorn :18890), and the GPU-ish
# systemd --user units (kokoro-tts, vllm-prod, kxkm-llama-*, kxkm-qwen3*, …) + the
# ollama warm-up timer. Docker/systemd/tmux/kill all work as kxkm: no root needed.
set -uo pipefail
. "$(dirname "$0")/../setup/env.sh"
STATE=$BOOTH_STATE/showmode.stopped
GPU_UNITS="kokoro-tts vllm-prod kxkm-llama-server kxkm-llama-moe kxkm-llama-devstral kxkm-qwen3coder-30b kxkm-qwen3next-80b kxkm-qwen3-tts kxkm-tts kxkm-reranker colpali-service kxkm-lightrag kxkm-comfyui"
GPU_TIMERS="kxkm-ollama-warmup"
COMFY_DIR=/ai/ComfyUI2
GW=gpu-worker-worker-1

comfy_pids() { for p in $(pgrep -u "$USER" -f 'python main.py --listen' 2>/dev/null); do [ "$(readlink /proc/$p/cwd 2>/dev/null)" = "$COMFY_DIR" ] && echo "$p"; done; }
fb_pids()    { pgrep -u "$USER" -x filebrowser 2>/dev/null || true; }
port_pid()   { ss -tlnp 2>/dev/null | awk -v p=":$1 " 'index($0,p)' | grep -oP 'pid=\K[0-9]+' | head -1; }
vc_pid()     { port_pid 7865; }
gs_pid()     { pgrep -u "$USER" -f 'uvicorn gpu_swap_proxy:app' 2>/dev/null | head -1 || true; }
gw_state()   { docker inspect -f '{{.State.Status}}' "$GW" 2>/dev/null || echo absent; }
unit_state() { systemctl --user is-active "$1.service" 2>/dev/null || true; }
timer_state(){ systemctl --user is-active "$1.timer" 2>/dev/null || true; }
term_wait()  { local p=$1 n=${2:-20}; kill -TERM "$p" 2>/dev/null || return 0; for _ in $(seq "$n"); do kill -0 "$p" 2>/dev/null || return 0; sleep 1; done; kill -KILL "$p" 2>/dev/null || true; }
gpu_apps()   { nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null; }

status() {
  echo "showmode: $([ -f "$STATE" ] && echo "ON since $(stat -c %y "$STATE" | cut -d. -f1) — stopped: $(tr '\n' ' ' < "$STATE")" || echo off)"
  echo "comfyui   : $([ -n "$(comfy_pids)" ] && echo "running pid $(comfy_pids | tr '\n' ' ')(+filebrowser $(fb_pids | tr '\n' ' '))" || echo stopped)"
  echo "gpu-worker: $(gw_state)"
  echo "voiceclone: $([ -n "$(vc_pid)" ] && echo "running pid $(vc_pid)" || echo stopped)"
  echo "gpu-swap  : $([ -n "$(gs_pid)" ] && echo "running pid $(gs_pid)" || echo stopped)"
  for u in $GPU_UNITS; do s=$(unit_state "$u"); [ "$s" = inactive ] || [ -z "$s" ] || echo "unit $u: $s"; done
  for t in $GPU_TIMERS; do s=$(timer_state "$t"); [ "$s" = inactive ] || [ -z "$s" ] || echo "timer $t: $s"; done
  if nvidia-smi >/dev/null 2>&1; then a=$(gpu_apps); echo "GPU apps  : ${a:-none}"; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | sed 's/^/GPU memory: /'; else echo "GPU       : nvidia-smi unavailable"; fi
}

on() {
  [ -f "$STATE" ] && { echo "already on (see status); run 'off' first to restore"; return 1; }
  : > "$STATE"
  for u in $GPU_UNITS; do s=$(unit_state "$u"); case "$s" in active|activating|reloading) echo "stop unit $u ($s)"; systemctl --user stop "$u.service"; echo "unit:$u" >> "$STATE";; esac; done
  for t in $GPU_TIMERS; do s=$(timer_state "$t"); case "$s" in active|waiting) echo "stop timer $t"; systemctl --user stop "$t.timer"; echo "timer:$t" >> "$STATE";; esac; done
  if [ -n "$(comfy_pids)" ]; then echo "stop comfyui"; for p in $(comfy_pids); do term_wait "$p" 30; done; for p in $(fb_pids); do term_wait "$p" 5; done; echo "comfyui" >> "$STATE"; fi
  if [ -n "$(vc_pid)" ]; then echo "stop voiceclone"; term_wait "$(vc_pid)" 15; tmux kill-session -t voiceclone 2>/dev/null; echo "voiceclone" >> "$STATE"; fi
  if [ -n "$(gs_pid)" ]; then echo "stop gpu-swap"; term_wait "$(gs_pid)" 10; echo "gpu-swap" >> "$STATE"; fi
  if [ "$(gw_state)" = running ]; then echo "stop gpu-worker"; docker stop "$GW" >/dev/null; echo "gpu-worker" >> "$STATE"; fi
  sleep 3
  a=$(gpu_apps); if [ -n "$a" ]; then echo "WARN: GPU still busy:"; echo "$a"; else echo "GPU is free."; fi
  echo "show mode ON — stopped: $(tr '\n' ' ' < "$STATE")"
}

off() {
  [ -f "$STATE" ] || { echo "show mode is not on (nothing recorded to restore)"; return 0; }
  # a tmux server born inside a service's cgroup dies with that service: start it in its own scope
  tmux ls >/dev/null 2>&1 || systemd-run --user --scope --unit "booth-tmux-$(date +%s)" --quiet tmux start-server
  while IFS= read -r item; do
    case "$item" in
      unit:*)  echo "start unit ${item#unit:}"; systemctl --user start "${item#unit:}.service" || true;;
      timer:*) echo "start timer ${item#timer:}"; systemctl --user start "${item#timer:}.timer" || true;;
      comfyui) echo "start comfyui (tmux comfyui)"; tmux new-session -d -s comfyui "cd $COMFY_DIR && . comfyenv/bin/activate && export PYTHONWARNINGS=ignore && (filebrowser -p 8189 -a 0.0.0.0 -r /ai/data &) && exec python main.py --listen --max-upload-size 100 --enable-manager" || true;;
      voiceclone) echo "start voiceclone (tmux voiceclone)"; tmux new-session -d -s voiceclone "bash /ai/VoiceClone/run-vc.sh >> /ai/VoiceClone/logs/app.log 2>&1" || true;;
      gpu-swap) echo "start gpu-swap"; ( cd /home/kxkm/gpu-swap && nohup /home/kxkm/gpu-swap/.venv/bin/uvicorn gpu_swap_proxy:app --host 0.0.0.0 --port 18890 >> /home/kxkm/gpu-swap/logs/proxy.log 2>&1 & ) || true;;
      gpu-worker) echo "start gpu-worker"; docker start "$GW" >/dev/null || true;;
      "") ;;
      *) echo "unknown state item '$item' (ignored)";;
    esac
  done < "$STATE"
  rm -f "$STATE"; echo "show mode OFF — tenants restored."
}

case "${1:-status}" in on) on;; off) off;; status) status;; *) echo "usage: $0 on|off|status"; exit 2;; esac
