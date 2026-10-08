"""Validacao no computador. NumPy/OpenCV nao sao dependencias do codigo C."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE = ROOT / "nios_software/build/lane_detect"
sys.path.insert(0, str(ROOT / "python"))
from ransac import PolynomialRegressor, RANSAC, extract_lane_points  # noqa: E402


def run(rgb, width, height, prefix, *options, success=True):
    process = subprocess.run(
        [str(EXECUTABLE), str(rgb), str(width), str(height), str(prefix), *map(str, options)],
        capture_output=True, text=True,
    )
    assert (process.returncode == 0) == success, process.stdout + process.stderr
    return process


def validate_outputs(original, prefix, expected_found, thickness=3):
    h, w = original.shape[:2]
    model = json.loads(Path(f"{prefix}_model.json").read_text())
    assert (model["height"], model["width"]) == (h, w)
    assert model["thickness"] == thickness and model["found"] == expected_found
    raw = np.fromfile(f"{prefix}_mask.bin", dtype=np.uint8)
    assert raw.size == w * h and np.all((raw == 0) | (raw == 1))
    raw = raw.reshape(h, w)
    debug = cv2.imread(f"{prefix}_debug.ppm")
    assert debug.shape == original.shape
    if expected_found:
        assert raw.sum() > 0 and model["inliers"] >= 50
        ys, _ = np.nonzero(raw)
        assert ys.min() >= model["y_min"] and ys.max() <= model["y_max"]
        assert np.all(debug[raw == 1] == (0, 0, 255))
        assert np.max(raw.sum(axis=1)) <= thickness
    else:
        assert not raw.any() and model["poly"] is None
        assert np.array_equal(debug, original)
    return model


def compare_python(original, model, name):
    _, _, points = extract_lane_points(original)
    assert abs(len(points) - model["points"]) <= max(3, 0.01 * len(points))
    reference = RANSAC(n=3, k=1000, t=1.0, d=50, model=PolynomialRegressor())
    reference.fit(points[:, [1]], points[:, 0])
    assert reference.best_fit is not None
    print(f"{name}: C {model['inliers']}/{model['points']}; "
          f"Python {reference.best_score}/{len(points)} inliers")
    return reference


def main():
    with tempfile.TemporaryDirectory(prefix="ransac-c-") as directory:
        folder = Path(directory)
        for image in sorted((ROOT / "python/test_images").glob("*.jpg")):
            original = cv2.imread(str(image))
            h, w = original.shape[:2]
            rgb = folder / f"{image.stem}.rgb"
            cv2.cvtColor(original, cv2.COLOR_BGR2RGB).tofile(rgb)
            prefix = folder / image.stem
            run(rgb, w, h, prefix)
            model = validate_outputs(original, prefix, True)
            compare_python(original, model, image.name)
            before = (Path(f"{prefix}_mask.bin").read_bytes(),
                      Path(f"{prefix}_model.json").read_bytes())
            run(rgb, w, h, prefix)
            assert before == (Path(f"{prefix}_mask.bin").read_bytes(),
                              Path(f"{prefix}_model.json").read_bytes())

        blank = np.zeros((64, 96, 3), dtype=np.uint8)
        rgb = folder / "blank.rgb"
        blank.tofile(rgb)
        run(rgb, 96, 64, folder / "blank")
        validate_outputs(blank, folder / "blank", False)

        synthetic = np.zeros((480, 640, 3), dtype=np.uint8)
        for y in range(290, 460):
            x = round(0.002 * y * y - 0.8 * y + 380)
            synthetic[y, x - 2:x + 3] = 255
        rgb = folder / "synthetic.rgb"
        cv2.cvtColor(synthetic, cv2.COLOR_BGR2RGB).tofile(rgb)
        prefix = folder / "synthetic"
        run(rgb, 640, 480, prefix)
        model = validate_outputs(synthetic, prefix, True)
        reference = compare_python(synthetic, model, "synthetic")
        y = np.arange(290, 460, dtype=float)
        poly = model["poly"]
        predicted = poly["a"] * y**2 + poly["b"] * y + poly["c"]
        assert np.max(np.abs(predicted - (0.002 * y**2 - 0.8 * y + 380))) < 0.5
        assert np.max(np.abs(predicted - reference.best_fit.predict(y))) < 0.5

        for thickness in [1, 2, 5, 7, 10]:
            run(rgb, 640, 480, prefix, "--thickness", thickness)
            thick_model = validate_outputs(synthetic, prefix, True, thickness)
            assert model["poly"] == thick_model["poly"]
            raw = np.fromfile(f"{prefix}_mask.bin", dtype=np.uint8)
            assert raw.sum() == thickness * (model["y_max"] - model["y_min"] + 1)

        run(rgb, 640, 480, folder / "none", "--min-inliers", 100000)
        validate_outputs(synthetic, folder / "none", False)
        run(folder / "missing.rgb", 640, 480, folder / "bad", success=False)
        corrupt = folder / "corrupt.rgb"
        for data in [b"", b"bad rgb", b"\0" * (640 * 480 * 3 + 1)]:
            corrupt.write_bytes(data)
            run(corrupt, 640, 480, folder / "bad", success=False)
        run(rgb, 640, 480, folder / "absent" / "bad", success=False)
        run(rgb, 0, 480, folder / "bad", success=False)
        run(rgb, 2147483648, 480, folder / "bad", success=False)
        for option, value in [("--threshold", "nan"), ("--threshold", "0"),
                              ("--threshold", "inf"), ("--threshold", "1e308"),
                              ("--threshold", "1e-300"),
                              ("--iterations", "0"), ("--min-inliers", "2"),
                              ("--seed", "4294967296"), ("--seed", "-1"),
                              ("--thickness", "0"), ("--unknown", "10")]:
            run(rgb, 640, 480, folder / "bad", option, value, success=False)
        assert not list(folder.glob("*.png"))
    print("OK: RGB, referencia Python, espessura, determinismo e erros de E/S/CLI.")


if __name__ == "__main__":
    main()
