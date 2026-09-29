import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, stdev

CLASSIFICATIONS = (
    "has plan",
    "does not have plan",
)

STATISTICS = (
    "min",
    "max",
    "avg",
)


@dataclass(frozen=True)
class Run:
    classification: str
    nfa_states: int
    nfa_transitions: int
    dfa_p1_states: int
    dfa_p1_transitions: int
    nfa_p2_states: int
    nfa_p2_transitions: int
    runtime_seconds: float
    run_peak_rss_mib: float


def parse_run(row: dict[str, str], row_number: int) -> Run:
    classification = row["classification"].strip()

    if classification not in CLASSIFICATIONS:
        raise ValueError(
            f"Row {row_number}: unknown classification " f"{classification!r}"
        )

    if row["error"].strip():
        raise ValueError(f"Row {row_number}: run contains an error: " f"{row['error']}")

    try:
        run = Run(
            classification=classification,
            nfa_states=int(row["nfa_states"]),
            nfa_transitions=int(row["nfa_states_transitions"]),
            dfa_p1_states=int(row["dfa_p1_states"]),
            dfa_p1_transitions=int(row["dfa_p1_transitions"]),
            nfa_p2_states=int(row["nfa_p2_states"]),
            nfa_p2_transitions=int(row["nfa_p2_transitions"]),
            runtime_seconds=float(row["runtime_seconds"]),
            run_peak_rss_mib=float(row["run_peak_rss_mib"]),
        )
    except ValueError as exc:
        raise ValueError(f"Row {row_number}: invalid numeric value") from exc

    if run.runtime_seconds < 0:
        raise ValueError(f"Row {row_number}: runtime cannot be negative")

    if run.run_peak_rss_mib < 0:
        raise ValueError(f"Row {row_number}: peak RSS cannot be negative")

    return run


def load_runs(path: Path) -> list[Run]:
    runs = []

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        if reader.fieldnames is None:
            raise ValueError("CSV file has no header")

        for row_number, row in enumerate(reader, start=2):
            runs.append(parse_run(row, row_number))

    if not runs:
        raise ValueError("CSV file contains no runs")

    return runs


def aggregate(values: list[int | float], statistic: str) -> float:
    if statistic == "min":
        return min(values)

    if statistic == "max":
        return max(values)

    if statistic == "avg":
        return fmean(values)

    raise ValueError(f"Unknown statistic: {statistic}")


def summarize(runs: list[Run],) -> list[dict[str, str | int | float]]:
    rows = []

    for classification in CLASSIFICATIONS:
        category_runs = [run for run in runs if run.classification == classification]

        if not category_runs:
            raise ValueError(f"No runs found for classification " f"{classification!r}")

        runtimes = [run.runtime_seconds for run in category_runs]
        peak_memory = [run.run_peak_rss_mib for run in category_runs]

        runtime_std = stdev(runtimes)
        memory_std = stdev(peak_memory)

        for statistic in STATISTICS:
            rows.append(
                {
                    "classification": classification,
                    "statistic": statistic,
                    "nfa_states": aggregate(
                        [run.nfa_states for run in category_runs],
                        statistic,
                    ),
                    "nfa_transitions": aggregate(
                        [run.nfa_transitions for run in category_runs],
                        statistic,
                    ),
                    "dfa_p1_states": aggregate(
                        [run.dfa_p1_states for run in category_runs],
                        statistic,
                    ),
                    "dfa_p1_transitions": aggregate(
                        [run.dfa_p1_transitions for run in category_runs],
                        statistic,
                    ),
                    "nfa_p2_states": aggregate(
                        [run.nfa_p2_states for run in category_runs],
                        statistic,
                    ),
                    "nfa_p2_transitions": aggregate(
                        [run.nfa_p2_transitions for run in category_runs],
                        statistic,
                    ),
                    "runtime_seconds": aggregate(
                        [run.runtime_seconds for run in category_runs],
                        statistic,
                    ),
                    "runtime_std": (runtime_std if statistic == "avg" else ""),
                    "run_peak_rss_mib": aggregate(
                        [run.run_peak_rss_mib for run in category_runs],
                        statistic,
                    ),
                    "run_peak_rss_mib_std": (memory_std if statistic == "avg" else "")
                }
            )

    return rows


def write_summary(
    rows: list[dict[str, str | int | float]],
    path: Path,
) -> None:
    fieldnames = [
        "classification",
        "statistic",
        "nfa_states",
        "nfa_transitions",
        "dfa_p1_states",
        "dfa_p1_transitions",
        "nfa_p2_states",
        "nfa_p2_transitions",
        "runtime_seconds",
        "runtime_std",
        "run_peak_rss_mib",
        "run_peak_rss_mib_std"
    ]

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize experiment results.")

    parser.add_argument(
        "input",
        type=Path,
        help="Input CSV file",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV file",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    output_path = args.output

    if output_path is None:
        output_path = args.input.with_name(f"{args.input.stem}_summary.csv")

    runs = load_runs(args.input)
    summary = summarize(runs)
    write_summary(summary, output_path)

    print(f"Summary written to {output_path}")


if __name__ == "__main__":
    main()
