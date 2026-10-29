#!/bin/bash
# Run the evaluation on one dedicated HPC node: the format service (Apptainer) and cwltool side by side.
#
#   bash bench/hpc/bench.sh prepare      # once, on a node with internet access (login node or salloc)
#   sbatch -p <partition> bench/hpc/bench.sh   # from the repository root
#
# RQ1  overhead on a real workflow: Sympolis (jobs/default.yml with RQ1_INPUT, RQ1_DEPTH), all modes,
#      upload and local transfer, RQ1_REPEAT runs per variant, containers via --singularity, steps --parallel
# RQ2  impact of file size: copy chains over FORMATS (GeoTIFF, GeoPackage, FASTQ) of SIZES MB, concrete
#      formats, all modes, upload and local transfer, RQ2_REPEAT runs per variant
# RQ3  abstract (eo:Raster / eo:Vector / EDAM sequence record format) instead of concrete formats on the RQ2
#      inputs, validated modes, RQ3_TRANSFERS, RQ2_REPEAT runs per variant (compare with the concrete runs of RQ2)
# Every run.py call (one set) gets a freshly started service, drops WARMUP repetitions and verifies its
# runs (see bench/run.py). All workflows load the ontology from a local copy, so runs make no network calls.
#
# Settings (environment variables, all optional):
#   RQS="1 2 3"  SIZES="1 10 100 1000"  FORMATS="geotiff geopackage fastq"  RQ1_REPEAT=10  RQ2_REPEAT=10
#   WARMUP=1  RQ3_TRANSFERS=local
#   RQ1_INPUT=Kahama.gpkg   GeoPackage in Sympolis' data/input/ (Kahama_Small.gpkg for a quick check)
#   RQ1_DEPTH=2   partitionDepth: 4^depth tiles processed in parallel (default.yml has 1)
#   BENCH_HOME=$HOME/ffs-bench   persistent: service image, Singularity cache, Node.js, Sympolis checkout, ontologies
#   BENCH_WORK=$TMPDIR/ffs-bench-<job>   node-local scratch shared with the service: inputs and cwltool
#                                        working dirs (needs ~4x the largest size per format, ~15 GB for 1000 MB)
#   FFS_IMAGE=docker://ghcr.io/dfg-sos/file-format-service-eo-bio@sha256:…   PORT=8000
#     the service image with the validator plug-in (plugins/format-validator-bio); anything `apptainer build`
#     accepts, e.g. docker-archive://<file>.tar for a `docker save` of a local build
# Results: bench/results/hpc-<job id>/ (one directory and service-<set>.log per run.py call, all_runs.csv, env.txt).
#
#SBATCH --job-name=ffs-bench
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --exclusive
#SBATCH --time=24:00:00
#SBATCH --output=ffs-bench-%j.out

set -euo pipefail

REPO="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
BENCH_HOME="${BENCH_HOME:-$HOME/ffs-bench}"
# file-format-service 0.2.0 (format-validator 0.3.0) with the plug-in format-validator-bio (FASTA, FASTQ):
# ghcr.io/dfg-sos/file-format-service-eo-bio:0.2.0, pinned to the image the RQ1 scenarios ran on
FFS_IMAGE="${FFS_IMAGE:-docker://ghcr.io/dfg-sos/file-format-service-eo-bio@sha256:cafddc3febdec3264e640b4b0b9be98d4b1b46150968c5738505bd7e09f8b059}"
SYMPOLIS_URL=https://github.com/dfg-sos/sympolis.git
SYMPOLIS_TAG=v1.2.0
# its tools pull ghcr.io/dfg-sos/sympolis:latest; pinned to the image of the release
SYMPOLIS_IMAGE=ghcr.io/dfg-sos/sympolis:1.2.0
# Sympolis' $schemas entry; the same file is used for the copy chains
ONTOLOGY=https://dfg-sos.github.io/ontologies/releases/eo-formats/1.0.0/eo-formats.owl
# EDAM in the version of mappings/edam-formats.json, for the FASTQ copy chains
EDAM_ONTOLOGY=http://edamontology.org/EDAM_1.25.owl
PORT="${PORT:-8000}"
RQS="${RQS:-1 2 3}"
SIZES="${SIZES:-1 10 100 1000}"
FORMATS="${FORMATS:-geotiff geopackage fastq}"
RQ1_REPEAT="${RQ1_REPEAT:-10}"
RQ1_INPUT="${RQ1_INPUT:-Kahama.gpkg}"
RQ1_DEPTH="${RQ1_DEPTH:-2}"
RQ2_REPEAT="${RQ2_REPEAT:-10}"
WARMUP="${WARMUP:-1}"
RQ3_TRANSFERS="${RQ3_TRANSFERS:-local}"

export UV_PYTHON=3.13  # fiona (vector inputs) has no wheels for 3.14 yet
export CWL_SINGULARITY_CACHE="$BENCH_HOME/singularity"
export PATH="$BENCH_HOME/node/bin:$PATH"
mkdir -p "$BENCH_HOME" "$CWL_SINGULARITY_CACHE"

if command -v module >/dev/null; then
    module load apptainer 2>/dev/null || true
    module load squashfs 2>/dev/null || true
    # compute nodes may lack git and libatomic (needed by the prebuilt Node.js)
    module load git 2>/dev/null || true
    module load gcc 2>/dev/null || true
fi
cd "$REPO"
[ -f pyproject.toml ] && [ -f bench/run.py ] || { echo "run from the repository root ($REPO)"; exit 1; }

if [ "${1:-}" = prepare ]; then
    command -v uv >/dev/null || { echo "uv is missing: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
    uv sync --frozen
    apptainer build --force "$BENCH_HOME/ffs.sif" "$FFS_IMAGE"
    curl -sSf -o "$BENCH_HOME/eo-formats.owl" "$ONTOLOGY"
    curl -sSfL -o "$BENCH_HOME/EDAM.owl" "$EDAM_ONTOLOGY"
    # cwltool evaluates the workflows' JavaScript with Node.js
    command -v node >/dev/null || uvx nodeenv --prebuilt "$BENCH_HOME/node"
    rm -rf "$BENCH_HOME/sympolis"
    git clone -q "$SYMPOLIS_URL" "$BENCH_HOME/sympolis"
    git -C "$BENCH_HOME/sympolis" checkout -q "$SYMPOLIS_TAG"
    sed -i "s|dockerPull: ghcr.io/dfg-sos/sympolis:latest|dockerPull: $SYMPOLIS_IMAGE|" "$BENCH_HOME"/sympolis/cwl/*.cwl
    # One unvalidated run pulls the workflow's images into $CWL_SINGULARITY_CACHE
    tmp=$(mktemp -d)
    uv run --frozen cwl-format-aware-runner --format-validation off --singularity --outdir "$tmp" \
        "$BENCH_HOME/sympolis/Sympolis.cwl" "$BENCH_HOME/sympolis/jobs/default.yml" >/dev/null
    rm -rf "$tmp"
    echo "prepared $BENCH_HOME; now: sbatch bench/hpc/bench.sh"
    exit 0
fi

[ -f "$BENCH_HOME/ffs.sif" ] && [ -f "$BENCH_HOME/eo-formats.owl" ] && [ -f "$BENCH_HOME/EDAM.owl" ] && [ -d "$BENCH_HOME/sympolis" ] || { echo "run 'bash bench/hpc/bench.sh prepare' first"; exit 1; }
command -v node >/dev/null || { echo "Node.js is missing, run prepare"; exit 1; }
JOB="${SLURM_JOB_ID:-$$}"
WORK="${BENCH_WORK:-${TMPDIR:-/tmp}/ffs-bench-$JOB}"
RESULTS="$REPO/bench/results/hpc-$JOB"
URL="http://127.0.0.1:$PORT"
mkdir -p "$WORK/tmp" "$WORK/service-tmp" "$RESULTS"

# --- environment record ------------------------------------------------------------------------
{
    echo "date: $(date -Is)"; echo "host: $(hostname)"; echo "job: $JOB"; echo "work: $WORK"
    echo "repo: $(git rev-parse HEAD)$(git diff --quiet || echo ' (dirty)')"
    # the runner is a pinned dependency (pyproject.toml / uv.lock): record the exact revision installed
    echo "runner: $(uv run --frozen python -c 'from importlib.metadata import distribution as d; print(d("format-aware-cwl-runner").read_text("direct_url.json"))')"
    echo "sympolis: $SYMPOLIS_TAG ($(git -C "$BENCH_HOME/sympolis" rev-parse HEAD)), image $SYMPOLIS_IMAGE"; echo "service image: $FFS_IMAGE"
    echo "settings: RQS='$RQS' SIZES='$SIZES' FORMATS='$FORMATS' RQ1_REPEAT=$RQ1_REPEAT RQ2_REPEAT=$RQ2_REPEAT WARMUP=$WARMUP RQ3_TRANSFERS=$RQ3_TRANSFERS"
    apptainer --version; node --version; uv --version
    apptainer inspect "$BENCH_HOME/ffs.sif" 2>/dev/null || true
    # identify the exact images and ontology used
    sha256sum "$BENCH_HOME/ffs.sif" "$BENCH_HOME/eo-formats.owl" "$BENCH_HOME/EDAM.owl" "$CWL_SINGULARITY_CACHE"/* || true
    lscpu; free -g; df -h "$WORK"
} >"$RESULTS/env.txt" 2>&1
# --- service -------------------------------------------------------------------------------------
SERVICE=
stop_service() {
    [ -n "$SERVICE" ] || return 0
    kill "$SERVICE" 2>/dev/null || true
    wait "$SERVICE" 2>/dev/null || true
    SERVICE=
}
start_service() {  # start_service <log file>: a fresh process, so no state carries over between sets
    stop_service
    rm -rf "$WORK/service-tmp" && mkdir -p "$WORK/service-tmp"
    # all mappings (EO formats, EDAM): the image has the validator plug-in for EDAM
    apptainer exec --cleanenv --containall --writable-tmpfs --pwd /app \
        --bind "$REPO/mappings:/app/mappings:ro" --bind "$WORK" --bind "$WORK/service-tmp:/tmp" \
        --env "SOS_FFS_SHARED_DIRS=$WORK" \
        "$BENCH_HOME/ffs.sif" uvicorn main:app --app-dir src --host 127.0.0.1 --port "$PORT" \
        >"$1" 2>&1 &
    SERVICE=$!
    for _ in $(seq 120); do curl -sf "$URL/health" >/dev/null && return 0; sleep 1; done
    echo "service did not start, see $1"
    exit 1
}
# a default (per-job) work dir is removed at the end, a given BENCH_WORK is kept
trap 'stop_service; [ -n "${BENCH_WORK:-}" ] || rm -rf "$WORK"' EXIT

# --- inputs --------------------------------------------------------------------------------------
cp -r "$BENCH_HOME/sympolis" "$WORK/sympolis"
# point Sympolis' $schemas at the local copy (the only change to the workflow)
{ grep -rl "$ONTOLOGY" "$WORK/sympolis" --include='*.cwl' || true; } | xargs -r sed -i "s|$ONTOLOGY|file://$BENCH_HOME/eo-formats.owl|"
# the RQ1 job: default.yml with RQ1_INPUT and RQ1_DEPTH, next to it so the relative input path still resolves
[ -f "$WORK/sympolis/data/input/$RQ1_INPUT" ] || { echo "RQ1_INPUT not found: data/input/$RQ1_INPUT"; exit 1; }
sed -e "s|/Kahama_Small\.gpkg|/$RQ1_INPUT|" -e "s|^partitionDepth: .*|partitionDepth: $RQ1_DEPTH|" "$WORK/sympolis/jobs/default.yml" >"$WORK/sympolis/jobs/bench.yml"
# shellcheck disable=SC2086
uv run --frozen bench/make_inputs.py --out "$WORK/inputs" --formats "${FORMATS// /,}" \
    --schema "file://$BENCH_HOME/eo-formats.owl" --edam-schema "file://$BENCH_HOME/EDAM.owl" $SIZES >"$RESULTS/inputs.txt"

FAILED=()
bench() {  # bench <name> <run.py args...>; a failed verification is recorded, the rest still runs
    echo "=== $1 $(date -Is)"
    start_service "$RESULTS/service-$1.log"
    uv run --frozen python bench/run.py --out "$RESULTS" --name "$@" --service-url "$URL" --warmup "$WARMUP" \
        "--tmpdir-prefix=$WORK/tmp/" "--tmp-outdir-prefix=$WORK/tmp/" || FAILED+=("$1")
}

for rq in $RQS; do
    case $rq in
    1)
        bench rq1-sympolis "$WORK/sympolis/Sympolis.cwl" "$WORK/sympolis/jobs/bench.yml" \
            --repeat "$RQ1_REPEAT" --transfers upload,local --singularity --parallel
        ;;
    2 | 3)
        if [ "$rq" = 2 ]; then
            label=concrete args=(--transfers upload,local)
        else
            label=abstract args=(--modes basic,structural,full --transfers "$RQ3_TRANSFERS")
        fi
        for fmt in $FORMATS; do
            for mb in $SIZES; do
                bench "rq$rq-$fmt-${mb}MB-$label" "$WORK/inputs/${fmt}_${label}_chain.cwl" \
                    "$WORK/inputs/${fmt}_${mb}MB_$label.yml" --repeat "$RQ2_REPEAT" "${args[@]}"
            done
        done
        ;;
    esac
done

# one table over all calls, the run.py directory as first column
awk -F, 'FNR == 1 { if (NR == 1) print "name," $0; next } { n = FILENAME; sub(/\/runs.csv$/, "", n); sub(/.*\//, "", n); print n "," $0 }' \
    "$RESULTS"/*/runs.csv >"$RESULTS/all_runs.csv"
echo "results: $RESULTS"
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "verification failed: ${FAILED[*]} (see */verify.txt)"
    exit 1
fi
