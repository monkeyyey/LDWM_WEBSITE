from __future__ import annotations

from pathlib import Path

from runtimes import sfwmark_lite


def main() -> None:
    out = Path(__file__).resolve().parent / "storage" / "outputs" / "smoke-test"
    result = sfwmark_lite.generate(
        prompt="a clean product photo of a ceramic mug on a desk",
        message="HSQR",
        seed=42,
        output_dir=out,
    )
    print("status:", "ok" if result.image_path else "failed")
    print("image:", result.image_path)
    print("score:", result.detection_score)
    print("payload:", result.recovered_payload)
    print("logs:")
    for line in result.logs:
        print(line)


if __name__ == "__main__":
    main()
