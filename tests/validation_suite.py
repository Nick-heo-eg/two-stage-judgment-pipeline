#!/usr/bin/env python3
"""
Comprehensive Validation Suite for Two-Stage Judgment Pipeline

Tests:
1. Multiple images with different protrusion counts
2. Negative control (noise image)
3. Reproducibility across images
4. Ground truth comparison
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.two_stage_judgment_pipeline import (
    TwoStageJudgmentPipeline,
    ObservationRecord
)

# Import OpenCV processing from examples
sys.path.insert(0, str(Path(__file__).parent.parent / "examples"))
try:
    import cv2
    import numpy as np
except ImportError:
    print("Error: opencv-python not installed")
    print("Run: pip install opencv-python")
    sys.exit(1)


def process_image_to_observation(image_path: str) -> ObservationRecord:
    """Process image through OpenCV to create observation record"""

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Failed to load image: {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Apply threshold
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        # No contours found - return zero observation
        return ObservationRecord(
            record_id=f"OBS_{Path(image_path).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            estimated_protrusions=0,
            convexity_defects=0,
            contour_area=0,
            hull_points=0,
            bbox_width=0,
            bbox_height=0,
            aspect_ratio=0,
            image_path=image_path,
            processing_method="opencv_convexity_defects"
        )

    # Get largest contour
    contour = max(contours, key=cv2.contourArea)

    # Calculate convex hull
    hull = cv2.convexHull(contour, returnPoints=False)

    # Calculate convexity defects
    defects = cv2.convexityDefects(contour, hull)

    # Count significant defects (depth > threshold)
    depth_threshold = 20
    significant_defects = 0
    if defects is not None:
        for i in range(defects.shape[0]):
            s, e, f, d = defects[i, 0]
            depth = d / 256.0
            if depth > depth_threshold:
                significant_defects += 1

    # Estimate protrusions (defects + 1 for gaps between protrusions)
    estimated_protrusions = significant_defects + 1 if significant_defects > 0 else 0

    # Get bounding box
    x, y, w, h = cv2.boundingRect(contour)
    aspect_ratio = float(w) / h if h > 0 else 0

    # Create observation record
    return ObservationRecord(
        record_id=f"OBS_{Path(image_path).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        timestamp=datetime.now().isoformat(),
        estimated_protrusions=estimated_protrusions,
        convexity_defects=significant_defects,
        contour_area=cv2.contourArea(contour),
        hull_points=len(hull),
        bbox_width=w,
        bbox_height=h,
        aspect_ratio=aspect_ratio,
        image_path=image_path,
        processing_method="opencv_convexity_defects"
    )


def run_validation_suite():
    """Run comprehensive validation tests"""

    print("=" * 80)
    print("COMPREHENSIVE VALIDATION SUITE")
    print("=" * 80)
    print()

    # Test cases with ground truth
    test_cases = [
        {
            "name": "3-finger hand (OK gesture)",
            "path": "/tmp/hand_3fingers.png",
            "expected_range": (2, 4),  # OpenCV might detect 2-4
            "description": "OK hand emoji - should detect ~3 protrusions"
        },
        {
            "name": "5-finger splayed hand",
            "path": "/tmp/hand_5fingers.png",
            "expected_range": (4, 6),  # OpenCV might detect 4-6
            "description": "Splayed hand emoji - should detect ~5 protrusions"
        },
        {
            "name": "6-finger hand (original test)",
            "path": "examples/fingers2.jpg",
            "expected_range": (5, 7),  # Known to detect 6
            "description": "6-finger emoji - should detect ~6 protrusions"
        },
        {
            "name": "Random noise (negative control)",
            "path": "/tmp/noise.png",
            "expected_range": None,  # Should be STOP or INDETERMINATE
            "description": "Random noise - should fail gracefully"
        }
    ]

    # Initialize pipeline
    pipeline = TwoStageJudgmentPipeline()

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}/{len(test_cases)}: {test_case['name']}")
        print(f"{'=' * 80}")
        print(f"Description: {test_case['description']}")
        print()

        try:
            # Process image to observation
            print("Step 1: Processing image through OpenCV...")
            observation = process_image_to_observation(test_case['path'])
            print(f"  Detected: {observation.estimated_protrusions} protrusions")
            print(f"  Defects: {observation.convexity_defects}")
            print()

            # Run pipeline
            print("Step 2: Running two-stage pipeline...")
            result = pipeline.execute(observation)

            # Analyze result
            print()
            print("RESULTS:")
            print(f"  Stage 1 State: {result.final_state}")
            print(f"  Stage 1 Value: {result.final_value}")

            if result.stage2_result:
                print(f"  Stage 2 Prior Intrusion: {result.prior_intrusion_detected}")

            # Check against expected range
            success = False
            if test_case['expected_range'] is None:
                # Negative control - should be STOP or INDETERMINATE
                success = result.final_state in ["STOP", "INDETERMINATE"]
                expected_msg = "STOP or INDETERMINATE"
            else:
                # Should extract VALUE in expected range
                if result.final_state == "VALUE" and result.final_value is not None:
                    min_val, max_val = test_case['expected_range']
                    success = min_val <= result.final_value <= max_val
                    expected_msg = f"{min_val}-{max_val}"
                else:
                    success = False
                    expected_msg = f"{test_case['expected_range'][0]}-{test_case['expected_range'][1]}"

            status = "✅ PASS" if success else "❌ FAIL"
            print(f"\n  Expected: {expected_msg}")
            print(f"  Status: {status}")

            results.append({
                "test_name": test_case['name'],
                "opencv_detection": observation.estimated_protrusions,
                "pipeline_state": result.final_state,
                "pipeline_value": result.final_value,
                "expected": expected_msg,
                "success": success,
                "prior_intrusion": result.prior_intrusion_detected if result.stage2_result else None
            })

        except Exception as e:
            print(f"\n  ❌ ERROR: {e}")
            results.append({
                "test_name": test_case['name'],
                "error": str(e),
                "success": False
            })

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r.get('success', False))
    total = len(results)

    print(f"\nTests Passed: {passed}/{total} ({100*passed//total}%)")
    print("\nDetailed Results:")
    print()

    for r in results:
        status = "✅" if r.get('success', False) else "❌"
        if 'error' in r:
            print(f"  {status} {r['test_name']}: ERROR - {r['error']}")
        else:
            print(f"  {status} {r['test_name']}")
            print(f"      OpenCV: {r['opencv_detection']} | Pipeline: {r['pipeline_state']}={r['pipeline_value']}")

    # Save results
    output_file = Path("validation_results.json")
    with output_file.open("w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": total - passed
            },
            "results": results
        }, f, indent=2)

    print(f"\n✅ Results saved to: {output_file}")
    print()

    return passed == total


if __name__ == "__main__":
    success = run_validation_suite()
    sys.exit(0 if success else 1)
