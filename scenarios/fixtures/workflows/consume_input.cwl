# F2.1/F2.2/F2.3/F5.1/F5.2/OK.1: the fault is in a workflow input file, labelled GeoTIFF by the job, not by a tool.
# Vanilla cwltool runs consume. The runner stops at consume's input check, so consume never runs:
# F2.1 (roads.geojson) in basic mode, F2.2 (GeoJSON content named .tif) and F5.1 (truncated GeoTIFF) in metadata mode, F5.2 (truncated pixel data) only in content;
# F2.3 (missing file) stops in cwltool before any step.
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: Workflow
inputs:
  raster: {type: File, format: eo:GeoTIFF}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: ../tools/consume_geotiff.cwl, in: {data: raster}, out: [size]}
