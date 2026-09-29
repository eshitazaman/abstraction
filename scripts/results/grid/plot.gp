reset

# ============================================================
# Terminal
# ============================================================

EXPORT = 1

if (EXPORT) {

    # For a one-column figure.
    # Adjust 3.35in if your template has a slightly different
    # column width.
    set terminal tikz \
        color \
        tightboundingbox \
        size 3.3in,1.5in


    set output "grid_nb_runtime_memory.tex"

} else {

    set terminal qt \
        size 1400,750 \
        font "Sans,12"
}

# ============================================================
# Data
# ============================================================

set datafile separator comma

N_NB     = 4
N_NBS    = 2
N_GROUPS = N_NB + N_NBS

array files[N_GROUPS] = [ \
    "grid_5_5_nb_summary.csv", \
    "grid_10_20_nb_summary.csv", \
    "grid_15_30_nb_summary.csv", \
    "grid_20_40_nb_summary.csv", \
    "grid_5_5_nbs_summary.csv", \
    "grid_10_20_nbs_summary.csv" \
]

array configs[N_GROUPS] = [ \
    "$5^2/5$", \
    "$10^2/20$", \
    "$15^2/30$", \
    "$20^2/40$", \
    "$5^2/5$", \
    "$10^2/20$" \
]

# MiB -> MB
mb(x) = x * 1.048576


# ============================================================
# X positions
# ============================================================

# Distance between P and NP
class_sep = 0.4

# Distance between consecutive configurations
group_sep = 1.0

# Runtime/memory separation within one classification
dx = 0.055

class_offset(s) = (s eq "has plan" ? 0 : class_sep)

xpos(i, s)     = (i - 1) * group_sep + class_offset(s)
xruntime(i, s) = xpos(i, s) - dx
xmemory(i, s)  = xpos(i, s) + dx

# Center of a complete configuration group
group_center(i) = (i - 1) * group_sep + class_sep / 2.0


# ============================================================
# X axis
# ============================================================

set xrange [ \
    -0.20 : \
    (N_GROUPS - 1) * group_sep + class_sep + 0.20 \
]


# ------------------------------------------------------------
# First row: P / NP
# ------------------------------------------------------------

unset xtics

do for [i=1:N_GROUPS] {
    base = (i - 1) * group_sep

    set xtics add ( \
        "$\\mathrm{P}$"  base, \
        "$\\mathrm{NP}$" base + class_sep \
    )
}


# ------------------------------------------------------------
# Second row: grid configuration
# ------------------------------------------------------------

config_label_y = -0.16

do for [i=1:N_GROUPS] {
    set label i configs[i] \
        at first group_center(i), graph config_label_y \
        center
}


# ------------------------------------------------------------
# Third row: NB / NBS
# ------------------------------------------------------------

mode_label_y = -0.23

# NB spans groups 1 ... N_NB
nb_center = \
    (group_center(1) + group_center(N_NB)) / 2.0

# NBS spans groups N_NB+1 ... N_GROUPS
nbs_center = \
    (group_center(N_NB + 1) + group_center(N_GROUPS)) / 2.0

set label 100 "$\\mathrm{NB}$" \
    at first nb_center, graph mode_label_y \
    center

set label 101 "$\\mathrm{NBS}$" \
    at first nbs_center, graph mode_label_y \
    center


# ============================================================
# Axes
# ============================================================

# ------------------------------------------------------------
# Left axis: runtime
# ------------------------------------------------------------

set autoscale y
set logscale y 10

set ylabel "Runtime (s)" \
    textcolor rgb "#011993" \
    offset 2.5,0

set ytics \
    textcolor rgb "#011993" \
    nomirror \
    offset 1.5, 0

set format y "$10^{%L}$"


# ------------------------------------------------------------
# Right axis: peak memory
# ------------------------------------------------------------

set autoscale y2
set logscale y2 10

set y2label "Peak Memory (MB)" \
    textcolor rgb "#ff7962" \
    offset -2.5,0

set y2tics \
    textcolor rgb "#ff7962" \
    nomirror \
    offset -1.5, 0

set format y2 "$10^{%L}$"

unset xlabel


# ============================================================
# Layout
# ============================================================

unset title
unset key

# Major horizontal grid lines only
set grid ytics \
    lc rgb "#dddddd" \
    lw 0.7

# Bottom + left + right borders, no top border
unset border
set border 11

set tics nomirror

set bmargin 0
set lmargin 3
set rmargin 3
set tmargin 1

# Error-bar cap width
set errorbars 1


# ============================================================
# Configuration separators
# ============================================================

# Light separator between each configuration
do for [i=1:N_GROUPS-1] {

    base = (i - 1) * group_sep

    # Midpoint between NP of group i and P of group i+1
    sep = base + (class_sep + group_sep) / 2.0

    set arrow i \
        from first sep, graph 0 \
        to first sep, graph 1 \
        nohead \
        dt 2 \
        lw 0.8 \
        lc rgb "#dddddd"
}


# ------------------------------------------------------------
# Stronger separator between NB and NBS
# ------------------------------------------------------------

nb_last_np = \
    (N_NB - 1) * group_sep + class_sep

nbs_first_p = \
    N_NB * group_sep

nb_nbs_sep = \
    (nb_last_np + nbs_first_p) / 2.0

set arrow 100 \
    from first nb_nbs_sep, graph 0 \
    to first nb_nbs_sep, graph 1 \
    nohead \
    dt 1 \
    lw 1.2 \
    lc rgb "#999999"


# ============================================================
# Styles
# ============================================================

# Runtime mean + SD
# Circle
set style line 1 \
    lc rgb "#011993" \
    lw 2 \
    pt 7 \
    ps 0.8


# Runtime min/max
# X
set style line 2 \
    lc rgb "#011993" \
    lw 1.5 \
    pt 2 \
    ps 0.8


# Memory mean + SD
# Square
set style line 3 \
    lc rgb "#ff7962" \
    lw 2 \
    pt 5 \
    ps 0.8


# Memory min/max
# X
set style line 4 \
    lc rgb "#ff7962" \
    lw 1.5 \
    pt 2 \
    ps 0.8


# ============================================================
# Plot
# ============================================================

# Lower limit used for runtime error bars that cross zero.
# Since zero cannot be represented on a logarithmic axis,
# these bars are drawn down to this value without a lower cap.
runtime_floor = 1e-4
cap_width = 0.05

runtime_lower(mean, std) = mean - std
runtime_upper(mean, std) = mean + std

plot \
    \
    for [i=1:N_GROUPS] files[i] using \
        (xruntime(i, strcol(1))):\
        (strcol(2) eq "avg" && runtime_lower($9,$10) > runtime_floor ? $9 : 1/0):\
        (strcol(2) eq "avg" && runtime_lower($9,$10) > runtime_floor ? $10 : 1/0) \
        axes x1y1 \
        with yerrorbars ls 1 \
        notitle, \
    \
    for [i=1:N_GROUPS] files[i] using \
        (xruntime(i, strcol(1))):\
        (strcol(2) eq "avg" && runtime_lower($9,$10) <= runtime_floor ? runtime_floor : 1/0):\
        (0):\
        (strcol(2) eq "avg" && runtime_lower($9,$10) <= runtime_floor \
            ? runtime_upper($9,$10) - runtime_floor : 1/0) \
        axes x1y1 \
        with vectors nohead ls 1 \
        notitle, \
    \
    for [i=1:N_GROUPS] files[i] using \
        (strcol(2) eq "avg" && runtime_lower($9,$10) <= runtime_floor \
            ? xruntime(i, strcol(1)) - cap_width : 1/0):\
        (runtime_upper($9,$10)):\
        (2.0 * cap_width):\
        (0) \
        axes x1y1 \
        with vectors nohead ls 1 \
        notitle, \
    \
    \
    for [i=1:N_GROUPS] files[i] using \
        (xruntime(i, strcol(1))):\
        (strcol(2) eq "avg" ? $9 : 1/0) \
        axes x1y1 \
        with points ls 1 \
        notitle, \
    \
    for [i=1:N_GROUPS] files[i] using \
        (xruntime(i, strcol(1))):\
        ((strcol(2) eq "min" || strcol(2) eq "max") ? $9 : 1/0) \
        axes x1y1 \
        with points ls 2 \
        notitle, \
    \
    \
    for [i=1:N_GROUPS] files[i] using \
        (xmemory(i, strcol(1))):\
        (strcol(2) eq "avg" ? mb($11) : 1/0):\
        (strcol(2) eq "avg" ? mb($12) : 1/0) \
        axes x1y2 \
        with yerrorbars ls 3 \
        notitle, \
    \
    for [i=1:N_GROUPS] files[i] using \
        (xmemory(i, strcol(1))):\
        (strcol(2) eq "avg" ? mb($11) : 1/0) \
        axes x1y2 \
        with points ls 3 \
        notitle, \
    \
    for [i=1:N_GROUPS] files[i] using \
        (xmemory(i, strcol(1))):\
        ((strcol(2) eq "min" || strcol(2) eq "max") ? mb($11) : 1/0) \
        axes x1y2 \
        with points ls 4 \
        notitle


# ============================================================
# Finish output
# ============================================================

if (EXPORT) {
    set output
}