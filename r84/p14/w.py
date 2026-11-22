"""Single worker entry into the pinned runner."""
import json
import sys

if __name__ == '__main__':
    source, bundle, build, out, seconds, seed, deadline, review = sys.argv[1:]
    sys.path.insert(0, source)
    import run_experiment as runner

    from pathlib import Path
    admission = json.loads(Path(review).read_text()) if review else None
    raise SystemExit(runner.run(bundle, build, out, int(seconds), int(seed), '2', 6000,
                                float(deadline), production_admission=admission))
