"""
Step 3 Test: CLIP encode frame → 512-dim vector
Uses saved frame from Step 2
"""
import cv2
import numpy as np
import time
import subprocess

def ram_usage():
    r = subprocess.run(['free', '-h'], capture_output=True, text=True)
    lines = r.stdout.strip().split('\n')
    return lines[1]  # Mem: line

print("RAM before CLIP load:", ram_usage())

from clip_encoder import CLIPEncoder
import logging
logging.basicConfig(level=logging.INFO)

# Load frame from Step 2
frame = cv2.imread('/tmp/nexus_test_frame.png')
if frame is None:
    print("No saved frame — using random")
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
else:
    print(f"Loaded frame: {frame.shape}")

# Load CLIP
encoder = CLIPEncoder()
encoder.load()
print("RAM after CLIP load:", ram_usage())

# Encode frame
print("\n--- Encoding frame ---")
t0 = time.time()
vec = encoder.encode_frame(frame)
t1 = time.time()

print(f"Vector shape : {vec.shape}")          # (512,)
print(f"Vector norm  : {np.linalg.norm(vec):.4f}")  # ~1.0
print(f"Inference time: {(t1-t0)*1000:.0f}ms")

# Text similarity test
print("\n--- Similarity scores ---")
queries = [
    "factory floor with robot",
    "yellow marker on ground",
    "red marker on floor",
    "empty room",
    "outdoor scene with trees",
]
for q in queries:
    sim = encoder.similarity(frame, q)
    print(f"  {sim:.4f}  '{q}'")

# Top labels test
print("\n--- Top label ranking ---")
labels = ["marker", "floor", "robot", "wall", "box", "person"]
ranked = encoder.top_labels(frame, labels)
for label, score in ranked:
    print(f"  {score:.4f}  {label}")

print("\nRAM after inference:", ram_usage())
print("\n✅ CLIP Step 3 COMPLETE")
