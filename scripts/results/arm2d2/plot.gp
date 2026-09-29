reset

# ============================================================
# Data
# ============================================================

set datafile separator ","
set datafile columnheaders

file = "arm2d2.csv"

# MiB -> GB
gb(x) = (x * 1.048576) / 1000


# ============================================================
# X positions
# ============================================================

# Distance between the two goal configurations within each r group
class_sep = 0.5

# Distance between consecutive r groups
group_sep = 1.2

# Horizontal separation between Action / Block / Clamp
method_sep = 0.1

# Position of configuration n:
#
# n = 0 -> r10 center-tight
# n = 1 -> r10 right
# n = 2 -> r5  center-tight
# ...
xpos(n) = int(n / 2) * group_sep + (int(n) % 2) * class_sep

xaction(n) = xpos(n) - method_sep
xblock(n)  = xpos(n)
xclamp(n)  = xpos(n) + method_sep


# ============================================================
# Terminal
# ============================================================

EXPORT = 1

if (EXPORT) {
    set terminal tikz color size 3.3in,1in
    set output "arm2d2_runtime_memory.tex"
} else {
    set terminal qt size 1400,800 font "Sans,12"
}


# ============================================================
# Axes
# ============================================================

set xrange [-0.25:4.5]


# ------------------------------------------------------------
# Left axis: runtime
# ------------------------------------------------------------

set autoscale y
set logscale y 10

set ylabel "Runtime (s)" \
    textcolor rgb "#011993" \
    offset 2.75,0

set ytics \
    textcolor rgb "#011993" \
    nomirror \
    offset 1, 0

set format y "$10^{%L}$"


# ------------------------------------------------------------
# Right axis: peak memory
# ------------------------------------------------------------

set autoscale y2
set logscale y2 10

set y2label "Peak Memory (GB)" \
    textcolor rgb "#ff7962" \
    offset -2.5,0

set y2tics \
    textcolor rgb "#ff7962" \
    nomirror \
    offset -1, 0

set format y2 "%g"


# ============================================================
# X ticks
# ============================================================

set xtics font ",11"

set xtics ( \
    "$\\mathrm{i}$" 0.0, \
    "$\\mathrm{ii}$"        0.5, \
    "$\\mathrm{i}$" 1.2, \
    "$\\mathrm{ii}$"        1.7, \
    "$\\mathrm{i}$"  2.4, \
    "$\\mathrm{ii}$"        2.9, \
    "$\\mathrm{i}$"  3.6, \
    "$\\mathrm{ii}$"        4.1 \
)


# ============================================================
# Group labels
# ============================================================

group_label_y = -0.25

set label 1 "$30^\\circ\\pm 10^\\circ$" \
    at first 0.25, graph group_label_y \
    center

set label 2 "$15^\\circ\\pm 5^\\circ$" \
    at first 1.45, graph group_label_y \
    center

set label 3 "$12^\\circ\\pm 4^\\circ$" \
    at first 2.65, graph group_label_y \
    center

set label 4 "$9^\\circ\\pm 3^\\circ$" \
    at first 3.85, graph group_label_y \
    center


# ============================================================
# Group separators
# ============================================================

# Separators are automatically positioned halfway between groups.

n_groups = 4

do for [i=1:n_groups-1] {
    base = (i - 1) * group_sep
    separator = base + (class_sep + group_sep) / 2.0

    set arrow i \
        from first separator, graph 0 \
        to first separator, graph 1 \
        nohead \
        dt 2 \
        lw 0.8 \
        lc rgb "#dddddd"
}


# ============================================================
# Layout
# ============================================================

# Bottom + left + right borders
set border 11 back lw 1.2

set tics nomirror

# Horizontal grid based only on runtime axis
set grid ytics back \
    lc rgb "#dddddd" \
    lw 0.7

set bmargin 0
set lmargin 3
set rmargin 3
set tmargin 1


# ============================================================
# Legend
# ============================================================

set key inside top left
set key samplen 0.01
set key font ",8"


# ============================================================
# Styles
# ============================================================

# ------------------------------------------------------------
# Runtime
# Filled markers
# ------------------------------------------------------------

# Action: filled circle
set style line 1 \
    lc rgb "#011993" \
    pt 7 \
    ps 0.8

# Block: filled square
set style line 2 \
    lc rgb "#011993" \
    pt 5 \
    ps 0.8

# Clamp: filled triangle
set style line 3 \
    lc rgb "#011993" \
    pt 9 \
    ps 0.8


# ------------------------------------------------------------
# Peak memory
# Hollow markers
# ------------------------------------------------------------

# Action: hollow circle
set style line 4 \
    lc rgb "#ff7962" \
    pt 7 \
    ps 1.2

# Block: hollow square
set style line 5 \
    lc rgb "#ff7962" \
    pt 5 \
    ps 1.2

# Clamp: hollow triangle
set style line 6 \
    lc rgb "#ff7962" \
    pt 9 \
    ps 1.2


# ============================================================
# Plot
# ============================================================

plot \
    \
    file every 3::0 \
        using (xaction($0)):(column("runtime_seconds")) \
        axes x1y1 \
        with points ls 1 \
        title "\\emph{(d)}", \
    \
    "" every 3::1 \
        using (xblock($0)):(column("runtime_seconds")) \
        axes x1y1 \
        with points ls 2 \
        title "\\emph{(b)}", \
    \
    "" every 3::2 \
        using (xclamp($0)):(column("runtime_seconds")) \
        axes x1y1 \
        with points ls 3 \
        title "\\emph{(l)}", \
    \
    \
    file every 3::0 \
        using (xaction($0)):(gb(column("run_peak_rss_mib"))) \
        axes x1y2 \
        with points ls 4 \
        notitle, \
    \
    "" every 3::1 \
        using (xblock($0)):(gb(column("run_peak_rss_mib"))) \
        axes x1y2 \
        with points ls 5 \
        notitle, \
    \
    "" every 3::2 \
        using (xclamp($0)):(gb(column("run_peak_rss_mib"))) \
        axes x1y2 \
        with points ls 6 \
        notitle


# ============================================================
# Finish
# ============================================================

if (EXPORT) {
    set output
}