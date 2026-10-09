#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单的人物关键点检测测试"""

import sys

print("Python version:", sys.version)

try:
    import cv2

    print("✓ OpenCV loaded")
except Exception as e:
    print(f"✗ OpenCV error: {e}")
    sys.exit(1)

try:
    import mediapipe as mp

    print("✓ MediaPipe loaded")
except Exception as e:
    print(f"✗ MediaPipe error: {e}")
    sys.exit(1)

# 读取图片
img_path = "test.jpg"
print(f"\n📷 Loading image: {img_path}")
img = cv2.imread(img_path)
if img is None:
    print(f"✗ Failed to load image")
    sys.exit(1)
print(f"✓ Image loaded: {img.shape}")

# 检测人体姿态
print("\n🦴 Detecting pose...")
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
results = pose.process(img_rgb)

if results.pose_landmarks:
    print(f"✓ Detected {len(results.pose_landmarks.landmark)} landmarks")
    for i, lm in enumerate(results.pose_landmarks.landmark):
        x = int(lm.x * img.shape[1])
        y = int(lm.y * img.shape[0])
        print(f"  [{i:2d}] ({x:4d}, {y:4d}) vis={lm.visibility:.2f}")

    # 保存结果
    mp.solutions.drawing_utils.draw_landmarks(
        img, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
    cv2.imwrite("output_pose.jpg", img)
    print("\n✓ Saved result to output_pose.jpg")
else:
    print("✗ No pose detected")

pose.close()
print("\n✅ Done!")