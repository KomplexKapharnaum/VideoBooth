# Glass-to-glass latency protocol

Measures the delay between a movement in front of the camera and its appearance on the
booth screen, for each engine, as mean AND spread (brief rule 2.2). No software clock
is trusted: it is a camera-of-the-camera test.

## Setup
1. Engine running, kiosk showing its output on the booth screen, baseline config from
   `CLAUDE.md` §5, preset "Chrome Sentinel (clean)".
2. A phone recording at **240 fps** (or 120 fps; note which) framed so that BOTH the
   event source and the booth screen are in the shot.
3. Event source, pick one and note it: a hand clap in frame · a torch/phone flashlight
   switched on in frame · an LED on a button. The event must be visible to the booth
   camera AND to the phone in the same shot.

## Run
- 10 events at least 5 s apart, person otherwise still, then 10 events while the
  person keeps moving (the pipeline behaves differently under motion).
- In the phone video, for each event count frames from the source event to the first
  frame where the booth screen shows it. latency = frames / phone fps.

## Report (BENCHMARKS.md, "## Glass-to-glass latency")
| date | engine + settings | phone fps | n | mean s | min s | max s | stdev s | notes |

Spread (max − min, stdev) is the number the design rule is about. Repeat after any
change that touches the pipeline, the browser flags or the capture format.
