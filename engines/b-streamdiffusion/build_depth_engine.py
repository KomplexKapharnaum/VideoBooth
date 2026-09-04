#!/usr/bin/env python3
"""build_depth_engine.py — build the Depth Anything V2 (small) TensorRT engine that the
fork's `depth_tensorrt` preprocessor needs, from an ONNX export.

Run inside the Engine B venv (TensorRT installed by setup/10_engine_b.sh):
  .engines/StreamDiffusion/.venv/bin/python engines/b-streamdiffusion/build_depth_engine.py \
      --onnx /ai/data/models/tensorrt/depth-anything/depth_anything_v2_vits.onnx \
      --out  /ai/VideoBooth/.engines/trt/depth_anything_v2_vits-fp16.engine

TensorRT engines are bound to the TensorRT version + GPU: rebuild after any TensorRT
upgrade. Input is 1x3xHxW with H=W=518 for the ComfyUI-Depth-Anything-TensorRT exports
(the ONNX may carry a dynamic batch/size; an optimization profile pins 518).
"""
import argparse, os, sys, time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--onnx', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--size', type=int, default=518, help='input H=W (must match detect_resolution)')
    ap.add_argument('--fp32', action='store_true', help='build without fp16')
    ap.add_argument('--workspace-gb', type=int, default=4)
    a = ap.parse_args()
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
    with open(a.out, 'wb') as f:
        f.write(memoryview(blob))
    print(f'ok: {a.out} ({blob.nbytes / 1e6:.1f} MB) in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
