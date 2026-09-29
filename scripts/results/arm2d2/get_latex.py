import csv
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Metric:
    model: str
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

def parse_metric(row: dict[str, str]) -> Metric:
    model_file = row["model"].strip()
    parsed = re.findall('arm2d2.(r\\d+)_(goal-[^_]+)_(border-[^_]+)*', model_file)[0]

    def get_model_name(parsed):
        mov = parsed[0]
        goal = parsed[1]
        action = parsed[2]
        name = ""

        # Movement length
        match mov:
            case "r10":
                name += "$30^\circ\pm10^\circ$ "
            case "r5":
                name += "$15^\circ\pm5^\circ$ "
            case "r4":
                name += "$12^\circ\pm4^\circ$ "
            case "r3":
                name += "$9^\circ\pm3^\circ$ "

        # Goal placement
        if "right" in goal:
            name += "\\emph{(i)} "
        elif "center" in goal:
            name += "\\emph{(ii)} "

        # Action mode
        if "clamp" in action:
            name += "\\emph{(l)}"
        elif "block" in action:
            name += "\\emph{(b)}"
        elif "action" in action:
            name += "\\emph{(d)}"

        return name

    model = get_model_name(parsed)

    metric = Metric(
        model=model,
        has_plan="Yes" if row["classification"] == "has plan" else "No",
        nfa_states=fmt(row["nfa_states"]),
        nfa_transitions=fmt(row["nfa_states_transitions"]),
        dfa_p1_states=fmt(row["dfa_p1_states"]),
        dfa_p1_transitions=fmt(row["dfa_p1_transitions"]),
        nfa_p2_states=fmt(row["nfa_p2_states"]),
        nfa_p2_transitions=fmt(row["nfa_p2_transitions"]),
        runtime_seconds=fmt(row["runtime_seconds"], 4),
        run_peak_rss_mb=fmt(str(float(row["run_peak_rss_mib"]) * 1.048576), 2),
    )

    return metric

with open('arm2d2.csv', newline='') as csv_file:
    reader = csv.DictReader(csv_file)
    
    if reader.fieldnames is None:
        raise ValueError("CSV file has no header")

    for row_number, row in enumerate(reader, start=2):
        metrics.append(parse_metric(row))



    for metric in metrics:
        print(f"{metric.model} & {metric.nfa_states} & {metric.nfa_transitions} & {metric.dfa_p1_states} & {metric.dfa_p1_transitions} & {metric.nfa_p2_states} & {metric.nfa_p2_transitions} & {metric.runtime_seconds} & {metric.run_peak_rss_mb}\\\\")
        print("\\hline")
