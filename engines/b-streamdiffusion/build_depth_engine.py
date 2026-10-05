#!/usr/bin/env python3
"""build_depth_engine.py — build the Depth Anything V2 (small) TensorRT engine that the
fork's `depth_tensorrt` preprocessor needs, from an ONNX export.

Installed by setup/11_depth_engine.sh (fetches the pinned ONNX, then calls this). By hand,
inside the Engine B venv (TensorRT installed by setup/10_engine_b.sh):
  .engines/StreamDiffusion/.venv/bin/python engines/b-streamdiffusion/build_depth_engine.py \
      --onnx /ai/VideoBooth/.engines/onnx/depth_anything_v2_vits.onnx \
      --out  /ai/VideoBooth/.engines/trt/depth_anything_v2_vits-fp16.engine
  ... build_depth_engine.py --check --out <engine>    # loads with this TensorRT + GPU? exit 0/1

TensorRT engines are bound to the TensorRT version + GPU: rebuild after any TensorRT
upgrade (--check says when). Input is 1x3xHxW with H=W=518 for the ComfyUI-Depth-Anything-TensorRT
exports (the ONNX may carry a dynamic batch/size; an optimization profile pins 518).
"""
import argparse, os, sys, time


def check(path, size):
    """The engine deserializes with the installed TensorRT on this GPU and takes size x size."""
    import tensorrt as trt
    if not os.path.isfile(path):
        print(f'missing: {path}')
        return 1
    with open(path, 'rb') as f:
        engine = trt.Runtime(trt.Logger(trt.Logger.ERROR)).deserialize_cuda_engine(f.read())
    if engine is None:
        print(f'stale: {path} does not load with tensorrt {trt.__version__} on this GPU — rebuild it')
        return 1
    name = next(n for n in (engine.get_tensor_name(i) for i in range(engine.num_io_tensors))
                if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT)
    shape = list(engine.get_tensor_shape(name))
    if shape[-2:] not in ([size, size], [-1, -1]):
        print(f'wrong size: {path} takes {shape}, detect_resolution is {size}')
        return 1
    print(f'ok: {path} loads with tensorrt {trt.__version__} (input {name} {shape})')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--onnx', help='ONNX export to build from (required unless --check)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--check', action='store_true', help='only test that --out loads here — no build')
    ap.add_argument('--size', type=int, default=518, help='input H=W (must match detect_resolution)')
    ap.add_argument('--fp32', action='store_true', help='build without fp16')
    ap.add_argument('--workspace-gb', type=int, default=4)
    a = ap.parse_args()
    if a.check:
        sys.exit(check(a.out, a.size))
    if not a.onnx:
        ap.error('--onnx is required to build')
    import tensorrt as trt
    print(f'tensorrt {trt.__version__} — onnx {a.onnx} → {a.out} ({a.size}x{a.size}, {"fp32" if a.fp32 else "fp16"})')
    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, logger)
    with open(a.onnx, 'rb') as f:
        if not parser.parse(f.read()):
            for i in range(parser.num_errors):
                print('onnx parse error:', parser.get_error(i), file=sys.stderr)
            sys.exit(2)
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, a.workspace_gb << 30)
    if not a.fp32:
        config.set_flag(trt.BuilderFlag.FP16)
    inp = network.get_input(0)
    shape = list(inp.shape)
    print('onnx input', inp.name, shape)
    if any(d < 0 for d in shape):
        profile = builder.create_optimization_profile()
        fixed = [1 if shape[0] < 0 else shape[0], 3, a.size, a.size]
        profile.set_shape(inp.name, fixed, fixed, fixed)
        config.add_optimization_profile(profile)
        print('pinned dynamic input to', fixed)
    t0 = time.time()
    blob = builder.build_serialized_network(network, config)
    if blob is None:
        sys.exit('engine build failed')
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    # write beside, then rename: a build that dies mid-write never replaces a working engine
    with open(a.out + '.part', 'wb') as f:
        f.write(memoryview(blob))
    os.replace(a.out + '.part', a.out)
    print(f'ok: {a.out} ({blob.nbytes / 1e6:.1f} MB) in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
