import csv
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Metric:
    stat: str
    has_plan: str
    nfa_states: str
    nfa_transitions: str
    dfa_p1_states: str
    dfa_p1_transitions: str
    nfa_p2_states: str
    nfa_p2_transitions: str
    runtime_seconds: str
    run_peak_rss_mb: str

metrics = []

def fmt(value: str, decimals: int = 2) -> str:
    return f"{float(value):.{decimals}f}".rstrip("0").rstrip(".")

def parse_metric(row: dict[str, str], action_mode: str) -> Metric:
    run = row["statistic"].strip()

    metric = Metric(
        stat=run,
        has_plan="Yes" if row["classification"] == "has plan" else "No",
        nfa_states=fmt(row["nfa_states"]),
        nfa_transitions=fmt(row["nfa_transitions"]),
        dfa_p1_states=fmt(row["dfa_p1_states"]),
        dfa_p1_transitions=fmt(row["dfa_p1_transitions"]),
        nfa_p2_states=fmt(row["nfa_p2_states"]),
        nfa_p2_transitions=fmt(row["nfa_p2_transitions"]),
        runtime_seconds=fmt(row["runtime_seconds"], 4),
        run_peak_rss_mb=fmt(str(float(row["run_peak_rss_mib"]) * 1.048576), 2),
    )

    return metric

with open('grid_10_20_nbs_summary.csv', newline='') as csv_file:
    reader = csv.DictReader(csv_file)
    name = csv_file.name
    parsed = re.findall('grid_(\\d+)_(\\d+)_([^_]+)_.*', name)

    grid_size = parsed[0][0]
    obs_count = parsed[0][1]

    if parsed[0][2] == "nb":
        action_mode = "AB"
    else:
        action_mode = "AB+S"

    model = f"${grid_size}^2/{obs_count}\\ {action_mode}$"
    
    if reader.fieldnames is None:
        raise ValueError("CSV file has no header")

    for row_number, row in enumerate(reader, start=2):
        metrics.append(parse_metric(row, action_mode))

    curr_line = 1

    for metric in metrics:
        if curr_line == 1:
            print(f"\\multirow{{6}}{{*}}{{\\rotatebox[origin=c]{{90}}{{{model}}}}} & \\multirow{{3}}{{*}}{{Yes}} & {metric.stat} & {metric.nfa_states} & {metric.nfa_transitions} & {metric.dfa_p1_states} & {metric.dfa_p1_transitions} & {metric.nfa_p2_states} & {metric.nfa_p2_transitions} & {metric.runtime_seconds} & {metric.run_peak_rss_mb}\\\\")
            print("\\cline{3-11}")
        elif curr_line == 4:
            print(f"& \\multirow{{3}}{{*}}{{No}} & {metric.stat} & {metric.nfa_states} & {metric.nfa_transitions} & {metric.dfa_p1_states} & {metric.dfa_p1_transitions} & {metric.nfa_p2_states} & {metric.nfa_p2_transitions} & {metric.runtime_seconds} & {metric.run_peak_rss_mb}\\\\")
            print("\\cline{3-11}")
        else:
            print(f"& & {metric.stat} & {metric.nfa_states} & {metric.nfa_transitions} & {metric.dfa_p1_states} & {metric.dfa_p1_transitions} & {metric.nfa_p2_states} & {metric.nfa_p2_transitions} & {metric.runtime_seconds} & {metric.run_peak_rss_mb}\\\\")
            if curr_line == 2 or curr_line == 5:
                print("\\cline{3-11}")
            elif curr_line == 3:
                print("\\cline{2-11}")
            elif curr_line == 6:
                print("\\hline")

        curr_line += 1