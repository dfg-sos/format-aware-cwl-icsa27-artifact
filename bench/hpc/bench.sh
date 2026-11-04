#!/bin/bash
# The overhead evaluation (RQ2, RQ3) and the Sympolis CRS scenario on one exclusive HPC node: the format service
# (Apptainer) and cwltool side by side, sharing node-local scratch. Details and settings: bench/hpc/README.md.
#
#   bash bench/hpc/bench.sh prepare              # once, on a node with internet access (login node or salloc)
#   sbatch -p <partition> bench/hpc/bench.sh     # from the repository root; SETS=... etc. in front of sbatch
#
#   Sets (SETS, run in the given order)        paper       result directories in bench/results/hpc-<job>/
#   ---------------------------------------------------------------------------------------------------------
#   sympolis   Sympolis on SYMPOLIS_INPUT    RQ2(a)      rq1-sympolis
#   concrete   copy chains, concrete formats RQ2(b)      rq2-<format>-<N>MB-concrete   (per FORMATS x SIZES)
#   abstract   copy chains, abstract formats RQ2(c)      rq3-<format>-<N>MB-abstract
#   crs        Sympolis with a wrong CRS     RQ1         crs-utm, crs-control
# The result directories keep the repository's original numbering (rq1-3), which bench/load_results.py reads.
# Every set gets a freshly started service; bench/run.py drops WARMUP repetitions and verifies the runs.
#
#SBATCH --job-name=ffs-bench
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --exclusive
#SBATCH --time=24:00:00
#SBATCH --output=ffs-bench-%j.out

set -euo pipefail

# --- settings (environment variables, see bench/hpc/README.md) -------------------------------------
SETS="${SETS:-sympolis concrete abstract crs}"
SIZES="${SIZES:-1 10 100 1000}"                     # copy-chain input sizes in MB
FORMATS="${FORMATS:-geotiff geopackage fastq}"     # copy-chain formats
CHAIN_REPEAT="${CHAIN_REPEAT:-10}"                 # measured runs per variant, concrete and abstract
ABSTRACT_TRANSFERS="${ABSTRACT_TRANSFERS:-local}"
SYMPOLIS_INPUT="${SYMPOLIS_INPUT:-Kahama.gpkg}"    # GeoPackage in Sympolis' data/input/
SYMPOLIS_DEPTH="${SYMPOLIS_DEPTH:-2}"              # partitionDepth: 4^depth tiles in parallel
SYMPOLIS_REPEAT="${SYMPOLIS_REPEAT:-10}"
CRS_REPEAT="${CRS_REPEAT:-10}"
CRS_TARGET="${CRS_TARGET:-EPSG:32736}"             # WGS 84 / UTM 36S, the zone of Kahama
WARMUP="${WARMUP:-1}"
NUMA_NODES="${NUMA_NODES-4}"                       # empty: skip the check
PORT="${PORT:-8000}"
BENCH_HOME="${BENCH_HOME:-$HOME/ffs-bench}"        # persistent: image, ontologies, Node.js, Sympolis, Singularity cache
# file-format-service-eo 0.4.0 (format-validator 0.5.0 with the plug-in format-validator-eo 0.1.0) with the plug-in
# format-validator-bio (FASTA, FASTQ): ghcr.io/dfg-sos/file-format-service-eo-bio:0.4.0, the image of the RQ1 scenarios
FFS_IMAGE="${FFS_IMAGE:-docker://ghcr.io/dfg-sos/file-format-service-eo-bio@sha256:b52a7190e24a2d28f8bcceaef7ba94072af42a3fc311738305acc69a5a059a82}"

# --- fixed versions --------------------------------------------------------------------------------
SYMPOLIS_URL=https://github.com/dfg-sos/sympolis.git
SYMPOLIS_TAG=v1.2.0
SYMPOLIS_IMAGE=ghcr.io/dfg-sos/sympolis:1.2.0   # its tools pull :latest; pinned to the image of the release
# Sympolis' $schemas entry, also used for the copy chains; EDAM in the version of mappings/edam-formats.json
ONTOLOGY=https://dfg-sos.github.io/ontologies/releases/eo-formats/1.0.0/eo-formats.owl
EDAM_ONTOLOGY=http://edamontology.org/EDAM_1.25.owl

REPO="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export UV_PYTHON=3.13  # fiona (vector inputs) has no wheels for 3.14 yet
export CWL_SINGULARITY_CACHE="$BENCH_HOME/singularity"
export PATH="$BENCH_HOME/node/bin:$PATH"

die() { echo "$*" >&2; exit 1; }

check_settings() {
    local old new
    for old in RQS:SETS RQ1_INPUT:SYMPOLIS_INPUT RQ1_DEPTH:SYMPOLIS_DEPTH RQ1_REPEAT:SYMPOLIS_REPEAT \
        RQ2_REPEAT:CHAIN_REPEAT RQ3_TRANSFERS:ABSTRACT_TRANSFERS; do
        new=${old#*:} old=${old%%:*}
        [ -z "${!old+set}" ] || die "$old was renamed to $new (RQS: 1 -> sympolis, 2 -> concrete, 3 -> abstract)"
    done
    local set
    for set in $SETS; do
        case $set in sympolis | concrete | abstract | crs) ;; *) die "unknown set in SETS: $set" ;; esac
    done
}

has_set() { [[ " $SETS " == *" $1 "* ]]; }

load_modules() {
    command -v module >/dev/null || return 0
    module load apptainer 2>/dev/null || true
    module load squashfs 2>/dev/null || true
    # compute nodes may lack git and libatomic (needed by the prebuilt Node.js)
    module load git 2>/dev/null || true
    module load gcc 2>/dev/null || true
}

# --- prepare: everything that needs the network ------------------------------------------------------
prepare() {
    command -v uv >/dev/null || die "uv is missing: https://docs.astral.sh/uv/getting-started/installation/"
    uv sync --frozen
    apptainer build --force "$BENCH_HOME/ffs.sif" "$FFS_IMAGE"
    echo "$FFS_IMAGE" >"$BENCH_HOME/ffs.sif.image"  # what ffs.sif was built from, checked before every job
    curl -sSf -o "$BENCH_HOME/eo-formats.owl" "$ONTOLOGY"
    curl -sSfL -o "$BENCH_HOME/EDAM.owl" "$EDAM_ONTOLOGY"
    # cwltool evaluates the workflows' JavaScript with Node.js
    command -v node >/dev/null || uvx nodeenv --prebuilt "$BENCH_HOME/node"
    rm -rf "$BENCH_HOME/sympolis"
    git clone -q "$SYMPOLIS_URL" "$BENCH_HOME/sympolis"
    git -C "$BENCH_HOME/sympolis" checkout -q "$SYMPOLIS_TAG"
    sed -i "s|dockerPull: ghcr.io/dfg-sos/sympolis:latest|dockerPull: $SYMPOLIS_IMAGE|" "$BENCH_HOME"/sympolis/cwl/*.cwl
    # one unvalidated run pulls the workflow's images into $CWL_SINGULARITY_CACHE
    local tmp
    tmp=$(mktemp -d)
    uv run --frozen cwl-format-aware-runner --format-validation off --singularity --outdir "$tmp" \
        "$BENCH_HOME/sympolis/Sympolis.cwl" "$BENCH_HOME/sympolis/jobs/default.yml" >/dev/null
    rm -rf "$tmp"
    echo "prepared $BENCH_HOME; now: sbatch bench/hpc/bench.sh"
}

check_prepared() {
    local f
    for f in ffs.sif eo-formats.owl EDAM.owl sympolis; do
        [ -e "$BENCH_HOME/$f" ] || die "$BENCH_HOME/$f is missing, run 'bash bench/hpc/bench.sh prepare' first"
    done
    command -v node >/dev/null || die "Node.js is missing, run prepare"
    # env.txt records FFS_IMAGE: the service must run the image it names, not one prepared for another FFS_IMAGE
    [ "$(cat "$BENCH_HOME/ffs.sif.image" 2>/dev/null)" = "$FFS_IMAGE" ] ||
        die "$BENCH_HOME/ffs.sif was not built from $FFS_IMAGE, run prepare (or set FFS_IMAGE/BENCH_HOME)"
    # the HPDA2 nodes look identical to Slurm, but some run with another NUMA layout and measure slower
    if [ -n "$NUMA_NODES" ]; then
        local numa
        numa=$(lscpu | awk -F: '/^NUMA node\(s\)/ {gsub(/ /, "", $2); print $2}')
        [ "$numa" = "$NUMA_NODES" ] || die "$(hostname) has $numa NUMA nodes, not $NUMA_NODES (NUMA_NODES= to skip)"
    fi
}

record_env() {  # node, versions and checksums of everything a run depends on
    echo "date: $(date -Is)"; echo "host: $(hostname)"; echo "job: $JOB"; echo "work: $WORK"
    echo "repo: $(git rev-parse HEAD)$(git diff --quiet || echo ' (dirty)')"
    # the runner is a pinned dependency (pyproject.toml / uv.lock): the exact revision installed
    echo "runner: $(uv run --frozen python -c 'from importlib.metadata import distribution as d; print(d("format-aware-cwl-runner").read_text("direct_url.json"))')"
    echo "sympolis: $SYMPOLIS_TAG ($(git -C "$BENCH_HOME/sympolis" rev-parse HEAD)), image $SYMPOLIS_IMAGE"
    echo "service image: $FFS_IMAGE"
    echo "settings: SETS='$SETS' SIZES='$SIZES' FORMATS='$FORMATS' CHAIN_REPEAT=$CHAIN_REPEAT" \
        "ABSTRACT_TRANSFERS=$ABSTRACT_TRANSFERS SYMPOLIS_INPUT=$SYMPOLIS_INPUT SYMPOLIS_DEPTH=$SYMPOLIS_DEPTH" \
        "SYMPOLIS_REPEAT=$SYMPOLIS_REPEAT CRS_REPEAT=$CRS_REPEAT CRS_TARGET=$CRS_TARGET WARMUP=$WARMUP"
    apptainer --version; node --version; uv --version
    apptainer inspect "$BENCH_HOME/ffs.sif" 2>/dev/null || true
    sha256sum "$BENCH_HOME/ffs.sif" "$BENCH_HOME/eo-formats.owl" "$BENCH_HOME/EDAM.owl" "$CWL_SINGULARITY_CACHE"/* || true
    lscpu; free -g; df -h "$WORK"
}

# --- service -----------------------------------------------------------------------------------------
SERVICE=
stop_service() {
    [ -n "$SERVICE" ] || return 0
    kill "$SERVICE" 2>/dev/null || true
    wait "$SERVICE" 2>/dev/null || true
    SERVICE=
}

start_service() {  # start_service <set name>: a fresh process, so no state carries over between sets
    local name=$1 log="$RESULTS/service-$1.log"
    stop_service
    rm -rf "$WORK/service-tmp" && mkdir -p "$WORK/service-tmp"
    local maps=(--bind "$REPO/mappings/eo-formats.json:/app/mappings/eo-formats.json:ro")
    # the EDAM mapping only for the FASTQ chains: the service does not start with it on an image without the
    # validator plug-in for EDAM
    [[ $name == *-fastq-* ]] && maps+=(--bind "$REPO/mappings/edam-formats.json:/app/mappings/edam-formats.json:ro")
    apptainer exec --cleanenv --containall --writable-tmpfs --pwd /app \
        "${maps[@]}" --bind "$WORK" --bind "$WORK/service-tmp:/tmp" \
        --env "SOS_FFS_SHARED_DIRS=$WORK" \
        "$BENCH_HOME/ffs.sif" uvicorn main:app --app-dir src --host 127.0.0.1 --port "$PORT" \
        >"$log" 2>&1 &
    SERVICE=$!
    for _ in $(seq 120); do curl -sf "$URL/health" >/dev/null && return 0; sleep 1; done
    die "service did not start, see $log"
}

# --- inputs ------------------------------------------------------------------------------------------
prepare_sympolis() {  # $WORK/sympolis with jobs/bench.yml: default.yml with SYMPOLIS_INPUT and SYMPOLIS_DEPTH
    cp -r "$BENCH_HOME/sympolis" "$WORK/sympolis"
    # point Sympolis' $schemas at the local copy (the only change to the workflow)
    { grep -rl "$ONTOLOGY" "$WORK/sympolis" --include='*.cwl' || true; } |
        xargs -r sed -i "s|$ONTOLOGY|file://$BENCH_HOME/eo-formats.owl|"
    [ -f "$WORK/sympolis/data/input/$SYMPOLIS_INPUT" ] || die "SYMPOLIS_INPUT not found: data/input/$SYMPOLIS_INPUT"
    # next to default.yml, so the relative input path still resolves
    sed -e "s|/Kahama_Small\.gpkg|/$SYMPOLIS_INPUT|" -e "s|^partitionDepth: .*|partitionDepth: $SYMPOLIS_DEPTH|" \
        "$WORK/sympolis/jobs/default.yml" >"$WORK/sympolis/jobs/bench.yml"
}

prepare_chains() {  # $WORK/inputs: the copy-chain workflows and inputs of every format and size
    # shellcheck disable=SC2086
    uv run --frozen bench/make_inputs.py --out "$WORK/inputs" --formats "${FORMATS// /,}" \
        --schema "file://$BENCH_HOME/eo-formats.owl" --edam-schema "file://$BENCH_HOME/EDAM.owl" $SIZES \
        >"$RESULTS/inputs.txt"
}

# --- sets --------------------------------------------------------------------------------------------
FAILED=()
run_set() {  # run_set <name> <bench/run.py args...>; a failed verification is recorded, the other sets still run
    local name=$1
    shift
    echo "=== $name $(date -Is)"
    start_service "$name"
    uv run --frozen python bench/run.py --out "$RESULTS" --name "$name" --service-url "$URL" --warmup "$WARMUP" \
        "--tmpdir-prefix=$WORK/tmp/" "--tmp-outdir-prefix=$WORK/tmp/" "$@" || FAILED+=("$name")
}

set_sympolis() {
    run_set rq1-sympolis "$WORK/sympolis/Sympolis.cwl" "$WORK/sympolis/jobs/bench.yml" \
        --repeat "$SYMPOLIS_REPEAT" --transfers upload,local --singularity --parallel
}

set_chains() {  # set_chains concrete|abstract: one set per format and size
    local label=$1 prefix args fmt mb
    # shellcheck disable=SC2054  # the commas separate run.py's lists, not array elements
    if [ "$label" = concrete ]; then
        prefix=rq2 args=(--transfers upload,local)
    else
        prefix=rq3 args=(--modes basic,metadata,content --transfers "$ABSTRACT_TRANSFERS")
    fi
    for fmt in $FORMATS; do
        for mb in $SIZES; do
            run_set "$prefix-$fmt-${mb}MB-$label" "$WORK/inputs/${fmt}_${label}_chain.cwl" \
                "$WORK/inputs/${fmt}_${mb}MB_$label.yml" --repeat "$CHAIN_REPEAT" "${args[@]}"
        done
    done
}

set_crs() {  # the Sympolis workflow with sos:expectedCRS on every vector port, and its input reprojected
    local dir="$WORK/sympolis-crs" utm="${SYMPOLIS_INPUT%.gpkg}_${CRS_TARGET#EPSG:}.gpkg"
    rm -rf "$dir" && cp -r "$WORK/sympolis" "$dir"
    uv run --frozen python bench/crs_scenario.py annotate "$dir" >"$RESULTS/crs-annotate.txt"
    uv run --frozen python bench/crs_scenario.py reproject "$dir/data/input/$SYMPOLIS_INPUT" \
        "$dir/data/input/$utm" --crs "$CRS_TARGET" >>"$RESULTS/crs-annotate.txt"
    sed "s|/$SYMPOLIS_INPUT|/$utm|" "$dir/jobs/bench.yml" >"$dir/jobs/bench-crs.yml"
    # metadata and content must stop on the wrong CRS; off and basic complete
    run_set crs-utm "$dir/Sympolis.cwl" "$dir/jobs/bench-crs.yml" --repeat "$CRS_REPEAT" \
        --transfers upload,local --expect-stop metadata,content --keep-outputs --singularity --parallel
    # the original input: metadata must complete, no false positive at any annotated port
    run_set crs-control "$dir/Sympolis.cwl" "$dir/jobs/bench.yml" --repeat 1 --modes off,metadata \
        --transfers local --keep-outputs --singularity --parallel
    # one feature per settlement cluster; the outputs (~80 MB per run) are not kept in the results
    local outs
    shopt -s nullglob
    outs=("$RESULTS"/crs-*/outputs/*/*_Sympolis.gpkg)
    shopt -u nullglob
    [ ${#outs[@]} -eq 0 ] ||
        uv run --frozen python bench/crs_scenario.py count "${outs[@]}" | sed "s|$RESULTS/||" >"$RESULTS/crs-clusters.txt"
    rm -rf "$RESULTS"/crs-*/outputs
}

merge_runs() {  # all_runs.csv: every set's runs.csv, with the set name as first column
    awk -F, 'FNR == 1 { if (NR == 1) print "name," $0; next }
             { n = FILENAME; sub(/\/runs.csv$/, "", n); sub(/.*\//, "", n); print n "," $0 }' \
        "$RESULTS"/*/runs.csv >"$RESULTS/all_runs.csv"
}

# --- main --------------------------------------------------------------------------------------------
check_settings
mkdir -p "$BENCH_HOME" "$CWL_SINGULARITY_CACHE"
load_modules
cd "$REPO"
[ -f pyproject.toml ] && [ -f bench/run.py ] || die "run from the repository root ($REPO)"
if [ "${1:-}" = prepare ]; then
    prepare
    exit 0
fi
check_prepared

JOB="${SLURM_JOB_ID:-$$}"
WORK="${BENCH_WORK:-${TMPDIR:-/tmp}/ffs-bench-$JOB}"  # node-local scratch, shared with the service
RESULTS="$REPO/bench/results/hpc-$JOB"
URL="http://127.0.0.1:$PORT"
mkdir -p "$WORK/tmp" "$WORK/service-tmp" "$RESULTS"
# a default (per-job) work dir is removed at the end, a given BENCH_WORK is kept
trap 'stop_service; [ -n "${BENCH_WORK:-}" ] || rm -rf "$WORK"' EXIT
record_env >"$RESULTS/env.txt" 2>&1

if has_set sympolis || has_set crs; then prepare_sympolis; fi  # crs copies the sympolis set's workflow
if has_set concrete || has_set abstract; then prepare_chains; fi
for set in $SETS; do
    case $set in
    sympolis) set_sympolis ;;
    concrete | abstract) set_chains "$set" ;;
    crs) set_crs ;;
    esac
done

merge_runs
echo "results: $RESULTS"
[ ${#FAILED[@]} -eq 0 ] || die "verification failed: ${FAILED[*]} (see */verify.txt)"
